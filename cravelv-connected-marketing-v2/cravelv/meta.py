import time
from urllib.parse import urlencode

from flask import current_app

from .crypto import decrypt_json, encrypt_json
from .http import get_json, post_form, post_multipart


def configured():
    return bool(current_app.config["META_APP_ID"] and current_app.config["META_APP_SECRET"])


def graph_url(path):
    version = current_app.config["META_GRAPH_VERSION"].strip("/")
    return f"https://graph.facebook.com/{version}/{path.lstrip('/')}"


def authorization_url(redirect_uri, state):
    scopes = ",".join(["pages_show_list", "pages_read_engagement", "pages_manage_posts", "instagram_basic", "instagram_content_publish"])
    return f"https://www.facebook.com/{current_app.config['META_GRAPH_VERSION']}/dialog/oauth?" + urlencode({"client_id": current_app.config["META_APP_ID"], "redirect_uri": redirect_uri, "state": state, "scope": scopes, "response_type": "code"})


def exchange_code(code, redirect_uri):
    return get_json(graph_url("oauth/access_token"), params={"client_id": current_app.config["META_APP_ID"], "client_secret": current_app.config["META_APP_SECRET"], "redirect_uri": redirect_uri, "code": code})["access_token"]


def page_accounts(user_token):
    return get_json(graph_url("me/accounts"), params={"access_token": user_token, "fields": "id,name,access_token,instagram_business_account{id,username}"}).get("data", [])


def publish_facebook(connection, media, caption):
    token = decrypt_json(connection.encrypted_page_token)["token"]
    payload = post_multipart(graph_url(f"{connection.page_id}/photos"), {"caption": caption, "access_token": token}, media.filename, media.mime_type, media.data)
    return payload.get("post_id") or payload.get("id", "")


def publish_instagram(connection, media_url, caption):
    if not connection.instagram_account_id:
        raise ValueError("The connected Facebook Page does not have an Instagram professional account attached.")
    token = decrypt_json(connection.encrypted_page_token)["token"]
    container_id = post_form(graph_url(f"{connection.instagram_account_id}/media"), {"image_url": media_url, "caption": caption, "access_token": token})["id"]
    for _ in range(5):
        code = get_json(graph_url(container_id), params={"fields": "status_code", "access_token": token}).get("status_code")
        if code == "FINISHED": break
        if code == "ERROR": raise ValueError("Instagram could not process the selected image.")
        time.sleep(2)
    return post_form(graph_url(f"{connection.instagram_account_id}/media_publish"), {"creation_id": container_id, "access_token": token}).get("id", "")


def encrypted_page_token(token):
    return encrypt_json({"token": token})

