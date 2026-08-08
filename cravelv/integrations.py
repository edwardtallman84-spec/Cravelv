import secrets
from io import BytesIO

from flask import Blueprint, abort, current_app, flash, g, redirect, request, send_file, session, url_for
from flask_login import login_required

from . import db
from .google_calendar import authorization_url as google_authorization_url, configured as google_configured, exchange_code as google_exchange_code, save_connection, sync_events
from .meta import authorization_url, configured as meta_configured, encrypted_page_token, exchange_code, page_accounts
from .models import GoogleConnection, MediaAsset, MetaConnection, Publication
from .publisher import publish, verify_media_signature
from .tenant import tenant_required

integrations_bp = Blueprint("integrations", __name__)


def external_url(endpoint):
    base = current_app.config["PUBLIC_BASE_URL"]
    path = url_for(endpoint)
    return f"{base}{path}" if base else url_for(endpoint, _external=True, _scheme="https" if request.is_secure else "http")


@integrations_bp.get("/app/integrations/google/connect")
@login_required
@tenant_required
def google_connect():
    if not google_configured():
        flash("Google Calendar is ready in CraveLV, but the Google connection keys have not been added yet.", "error")
        return redirect(url_for("main.integrations"))
    state = secrets.token_urlsafe(24)
    session["google_oauth_state"] = state
    return redirect(google_authorization_url(external_url("integrations.google_callback"), state))


@integrations_bp.get("/app/integrations/google/callback")
@login_required
@tenant_required
def google_callback():
    if request.args.get("state") != session.pop("google_oauth_state", None):
        abort(400)
    credentials = google_exchange_code(request.args["code"], external_url("integrations.google_callback"))
    save_connection(g.organization.id, credentials)
    flash("Google Calendar connected. Your truck schedule can now sync into CraveLV.", "success")
    return redirect(url_for("main.calendar"))


@integrations_bp.post("/app/integrations/google/sync")
@login_required
@tenant_required
def google_sync():
    connection = db.session.execute(db.select(GoogleConnection).where(GoogleConnection.organization_id == g.organization.id)).scalar_one_or_none()
    if not connection:
        flash("Connect Google Calendar first.", "error")
    else:
        try:
            count = sync_events(connection)
            flash(f"Google Calendar synced. {count} upcoming events checked.", "success")
        except Exception:
            current_app.logger.exception("Google Calendar sync failed")
            flash("Google Calendar could not sync. Reconnect it and try again.", "error")
    return redirect(url_for("main.calendar"))


@integrations_bp.get("/app/integrations/meta/connect")
@login_required
@tenant_required
def meta_connect():
    if not meta_configured():
        flash("Meta publishing is built, but the Meta app connection keys have not been added yet.", "error")
        return redirect(url_for("main.integrations"))
    state = secrets.token_urlsafe(24)
    session["meta_oauth_state"] = state
    return redirect(authorization_url(external_url("integrations.meta_callback"), state))


@integrations_bp.get("/app/integrations/meta/callback")
@login_required
@tenant_required
def meta_callback():
    if request.args.get("state") != session.pop("meta_oauth_state", None):
        abort(400)
    pages = page_accounts(exchange_code(request.args["code"], external_url("integrations.meta_callback")))
    if not pages:
        flash("No Facebook Page was available for this account.", "error")
        return redirect(url_for("main.integrations"))
    page = pages[0]
    instagram = page.get("instagram_business_account") or {}
    connection = db.session.execute(db.select(MetaConnection).where(MetaConnection.organization_id == g.organization.id)).scalar_one_or_none()
    if not connection:
        connection = MetaConnection(organization_id=g.organization.id, page_id="", page_name="", encrypted_page_token="")
        db.session.add(connection)
    connection.page_id = page["id"]
    connection.page_name = page["name"]
    connection.instagram_account_id = instagram.get("id", "")
    connection.instagram_username = instagram.get("username", "")
    connection.encrypted_page_token = encrypted_page_token(page["access_token"])
    db.session.commit()
    flash("Facebook and Instagram connected to the publishing workspace.", "success")
    return redirect(url_for("main.integrations"))


@integrations_bp.post("/app/publications/<int:publication_id>/publish")
@login_required
@tenant_required
def publish_now(publication_id):
    publication = db.session.execute(db.select(Publication).where(Publication.id == publication_id, Publication.organization_id == g.organization.id)).scalar_one_or_none()
    if not publication:
        abort(404)
    publication.status = "publishing"
    db.session.commit()
    try:
        publish(publication)
        flash(f"Published to {publication.platform.title()}.", "success")
    except Exception as exc:
        publication.status = "failed"
        publication.error_message = str(exc)[:500]
        db.session.commit()
        flash(str(exc), "error")
    return redirect(url_for("main.calendar"))


@integrations_bp.get("/media/public/<int:asset_id>")
def public_media(asset_id):
    token = request.args.get("token", "")
    if not verify_media_signature(token, asset_id):
        abort(403)
    media = db.session.get(MediaAsset, asset_id)
    if not media:
        abort(404)
    return send_file(BytesIO(media.data), mimetype=media.mime_type, download_name=media.filename, max_age=3600)
