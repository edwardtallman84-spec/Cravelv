from datetime import datetime, timezone
from urllib.parse import urlencode

from flask import current_app

from . import db
from .crypto import decrypt_json, encrypt_json
from .http import get_json, post_form
from .models import CalendarEvent, GoogleConnection, utcnow

SCOPES = "openid https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/calendar.readonly"


def configured():
    return bool(current_app.config["GOOGLE_CLIENT_ID"] and current_app.config["GOOGLE_CLIENT_SECRET"])


def authorization_url(redirect_uri, state):
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode({
        "client_id": current_app.config["GOOGLE_CLIENT_ID"],
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
        "state": state,
    })


def exchange_code(code, redirect_uri):
    payload = post_form("https://oauth2.googleapis.com/token", {
        "code": code,
        "client_id": current_app.config["GOOGLE_CLIENT_ID"],
        "client_secret": current_app.config["GOOGLE_CLIENT_SECRET"],
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    })
    payload["expires_at"] = utcnow().timestamp() + payload.get("expires_in", 3600) - 60
    return payload


def refresh(credentials):
    if credentials.get("expires_at", 0) > utcnow().timestamp():
        return credentials
    payload = post_form("https://oauth2.googleapis.com/token", {
        "refresh_token": credentials["refresh_token"],
        "client_id": current_app.config["GOOGLE_CLIENT_ID"],
        "client_secret": current_app.config["GOOGLE_CLIENT_SECRET"],
        "grant_type": "refresh_token",
    })
    credentials["access_token"] = payload["access_token"]
    credentials["expires_at"] = utcnow().timestamp() + payload.get("expires_in", 3600) - 60
    return credentials


def save_connection(organization_id, credentials):
    user = get_json("https://www.googleapis.com/oauth2/v2/userinfo", headers={"Authorization": f"Bearer {credentials['access_token']}"})
    connection = db.session.execute(db.select(GoogleConnection).where(GoogleConnection.organization_id == organization_id)).scalar_one_or_none()
    if not connection:
        connection = GoogleConnection(organization_id=organization_id, encrypted_credentials="")
        db.session.add(connection)
    connection.email = user.get("email", "")
    connection.encrypted_credentials = encrypt_json(credentials)
    db.session.commit()
    return connection


def parse_google_time(value):
    raw = value.get("dateTime")
    if raw:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)
    return datetime.fromisoformat(value["date"]).replace(tzinfo=timezone.utc)


def sync_events(connection, days=90):
    credentials = refresh(decrypt_json(connection.encrypted_credentials))
    result = get_json(f"https://www.googleapis.com/calendar/v3/calendars/{connection.calendar_id}/events", params={
        "timeMin": utcnow().isoformat(),
        "maxResults": 250,
        "singleEvents": "true",
        "orderBy": "startTime",
    }, headers={"Authorization": f"Bearer {credentials['access_token']}"})
    for raw in result.get("items", []):
        external_id = raw.get("id")
        if not external_id or raw.get("status") == "cancelled":
            continue
        event = db.session.execute(db.select(CalendarEvent).where(CalendarEvent.organization_id == connection.organization_id, CalendarEvent.external_id == external_id)).scalar_one_or_none()
        if not event:
            event = CalendarEvent(organization_id=connection.organization_id, external_id=external_id, title="")
            db.session.add(event)
        event.title = raw.get("summary", "Truck event")
        event.location = raw.get("location", "")
        event.description = raw.get("description", "")
        event.start_at = parse_google_time(raw["start"])
        event.end_at = parse_google_time(raw["end"]) if raw.get("end") else None
        event.source_url = raw.get("htmlLink", "")
    connection.encrypted_credentials = encrypt_json(credentials)
    connection.last_synced_at = utcnow()
    db.session.commit()
    return len(result.get("items", []))

