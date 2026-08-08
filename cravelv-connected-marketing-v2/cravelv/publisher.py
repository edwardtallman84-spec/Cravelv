from datetime import datetime, timezone
from threading import Event, Lock, Thread

from flask import current_app, url_for
from itsdangerous import URLSafeTimedSerializer

from . import db
from .meta import publish_facebook, publish_instagram
from .models import MetaConnection, Publication, utcnow

_scheduler = None
_lock = Lock()


def media_signature(media_id):
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="media-publish").dumps({"media_id": media_id})


def verify_media_signature(token, media_id):
    try:
        data = URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="media-publish").loads(token, max_age=3600)
        return data.get("media_id") == media_id
    except Exception:
        return False


def publish(publication):
    connection = db.session.execute(db.select(MetaConnection).where(MetaConnection.organization_id == publication.organization_id)).scalar_one_or_none()
    if not connection:
        raise ValueError("Connect Facebook and Instagram before publishing.")
    caption = publication.content_item.caption
    if publication.platform == "facebook":
        provider_id = publish_facebook(connection, publication.media_asset, caption)
    elif publication.platform == "instagram":
        base = current_app.config["PUBLIC_BASE_URL"] or ""
        media_path = url_for("integrations.public_media", asset_id=publication.media_asset_id, token=media_signature(publication.media_asset_id))
        provider_id = publish_instagram(connection, f"{base}{media_path}", caption)
    else:
        raise ValueError("Unsupported publishing destination.")
    publication.status = "published"
    publication.provider_post_id = provider_id
    publication.published_at = utcnow()
    publication.error_message = ""
    db.session.commit()


def publish_due(app):
    with app.app_context(), _lock:
        due = db.session.execute(db.select(Publication).where(
            Publication.status == "scheduled",
            Publication.scheduled_for <= datetime.now(timezone.utc),
        ).limit(20)).scalars().all()
        for item in due:
            item.status = "publishing"
            db.session.commit()
            try:
                publish(item)
            except Exception as exc:
                item.status = "failed"
                item.error_message = str(exc)[:500]
                db.session.commit()


def start_scheduler(app):
    global _scheduler
    if _scheduler:
        return
    stop = Event()
    def loop():
        while not stop.wait(60):
            publish_due(app)
    _scheduler = Thread(target=loop, daemon=True, name="cravelv-publisher")
    _scheduler.start()
