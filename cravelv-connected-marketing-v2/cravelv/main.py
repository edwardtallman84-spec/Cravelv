from datetime import datetime, timedelta, timezone

from flask import Blueprint, abort, current_app, flash, g, jsonify, redirect, render_template, request, send_file, url_for
from flask_login import login_required
from io import BytesIO
from werkzeug.utils import secure_filename

from . import db
from .models import CalendarEvent, ContentItem, Engagement, GoogleConnection, Lead, MediaAsset, MetaConnection, Publication
from .tenant import tenant_required

main_bp = Blueprint("main", __name__)


def scoped(model):
    return db.select(model).where(model.organization_id == g.organization.id)


@main_bp.get("/")
def landing():
    return render_template("landing.html")


@main_bp.get("/health")
def health():
    return jsonify(status="ok", service="cravelv"), 200


@main_bp.get("/app")
@login_required
@tenant_required
def dashboard():
    content = db.session.execute(scoped(ContentItem).order_by(ContentItem.scheduled_for.asc())).scalars().all()
    leads = db.session.execute(scoped(Lead).order_by(Lead.created_at.desc())).scalars().all()
    engagements = db.session.execute(scoped(Engagement).order_by(Engagement.created_at.desc())).scalars().all()
    pipeline = sum(lead.estimated_value for lead in leads if lead.stage not in {"won", "lost"})
    return render_template("app/dashboard.html", content=content, leads=leads, engagements=engagements, pipeline=pipeline)


@main_bp.route("/app/brand", methods=["GET", "POST"])
@login_required
@tenant_required
def brand():
    profile = g.organization.brand_profile
    if request.method == "POST":
        for field in ("business_name", "tagline", "cuisine", "city", "audience", "voice", "primary_color", "instagram", "website"):
            setattr(profile, field, request.form.get(field, "").strip())
        g.organization.name = profile.business_name
        db.session.commit()
        flash("Brand profile saved.", "success")
        return redirect(url_for("main.brand"))
    return render_template("app/brand.html", profile=profile)


@main_bp.route("/app/studio", methods=["GET", "POST"])
@login_required
@tenant_required
def studio():
    generated = None
    selected_media = None
    selected_event = None
    if request.method == "POST":
        topic = request.form.get("topic", "today's special").strip()
        offer = request.form.get("offer", "").strip()
        media_id = request.form.get("media_id", type=int)
        event_id = request.form.get("event_id", type=int)
        if media_id:
            selected_media = db.session.execute(scoped(MediaAsset).where(MediaAsset.id == media_id)).scalar_one_or_none()
        if event_id:
            selected_event = db.session.execute(scoped(CalendarEvent).where(CalendarEvent.id == event_id)).scalar_one_or_none()
        profile = g.organization.brand_profile
        moment = selected_event.title if selected_event else topic
        location = f" at {selected_event.location}" if selected_event and selected_event.location else ""
        timing = selected_event.start_at.strftime("%A, %B %-d at %-I:%M %p") if selected_event else "today"
        visual = f" featuring {selected_media.title or selected_media.tags or 'one of our favorites'}" if selected_media else ""
        hook = f"{profile.city}, come hungry — {moment} is calling."
        generated = f"{hook}\n\nCatch {profile.business_name}{location} {timing}{visual}. Fresh, bold, and made for people who know great {profile.cuisine or 'food'}. {offer}\n\nSave this post, tag your food-truck partner, and come hungry.\n\n#FoodTruck #SupportLocal #{profile.city.replace(' ', '')}Eats"
    drafts = db.session.execute(scoped(ContentItem).where(ContentItem.status == "draft").order_by(ContentItem.created_at.desc())).scalars().all()
    media = db.session.execute(scoped(MediaAsset).order_by(MediaAsset.created_at.desc())).scalars().all()
    events = db.session.execute(scoped(CalendarEvent).where(CalendarEvent.start_at >= datetime.now(timezone.utc)).order_by(CalendarEvent.start_at.asc()).limit(20)).scalars().all()
    return render_template("app/studio.html", generated=generated, drafts=drafts, media=media, events=events, selected_media=selected_media, selected_event=selected_event)


@main_bp.post("/app/studio/save")
@login_required
@tenant_required
def save_content():
    caption = request.form.get("caption", "").strip()
    if caption:
        platforms = request.form.getlist("platforms") or [request.form.get("channel", "Instagram").lower()]
        scheduled = request.form.get("scheduled_for")
        when = datetime.fromisoformat(scheduled).replace(tzinfo=timezone.utc) if scheduled else None
        media_id = request.form.get("media_id", type=int)
        media = db.session.execute(scoped(MediaAsset).where(MediaAsset.id == media_id)).scalar_one_or_none() if media_id else None
        content = ContentItem(organization_id=g.organization.id, title=request.form.get("title", "New campaign"), caption=caption, channel=", ".join(p.title() for p in platforms), status="scheduled" if when else "draft", scheduled_for=when)
        db.session.add(content)
        db.session.flush()
        if media:
            for platform in platforms:
                if platform in {"facebook", "instagram"}:
                    db.session.add(Publication(organization_id=g.organization.id, content_item_id=content.id, media_asset_id=media.id, platform=platform, status="scheduled" if when else "draft", scheduled_for=when))
        db.session.commit()
        flash("Campaign saved to your publishing queue.", "success")
    return redirect(url_for("main.studio"))


@main_bp.route("/app/calendar", methods=["GET", "POST"])
@login_required
@tenant_required
def calendar():
    if request.method == "POST":
        scheduled = request.form.get("scheduled_for")
        when = datetime.fromisoformat(scheduled).replace(tzinfo=timezone.utc) if scheduled else None
        item = ContentItem(organization_id=g.organization.id, title=request.form.get("title", "Scheduled post"), caption=request.form.get("caption", ""), channel=request.form.get("channel", "Instagram"), status="scheduled" if when else "draft", scheduled_for=when)
        db.session.add(item)
        db.session.commit()
        flash("Content added to the calendar.", "success")
        return redirect(url_for("main.calendar"))
    items = db.session.execute(scoped(ContentItem).order_by(ContentItem.scheduled_for.asc(), ContentItem.created_at.desc())).scalars().all()
    events = db.session.execute(scoped(CalendarEvent).where(CalendarEvent.start_at >= datetime.now(timezone.utc)).order_by(CalendarEvent.start_at.asc()).limit(30)).scalars().all()
    publications = db.session.execute(scoped(Publication).order_by(Publication.created_at.desc())).scalars().all()
    google = db.session.execute(db.select(GoogleConnection).where(GoogleConnection.organization_id == g.organization.id)).scalar_one_or_none()
    return render_template("app/calendar.html", items=items, events=events, publications=publications, google=google)


@main_bp.route("/app/media", methods=["GET", "POST"])
@login_required
@tenant_required
def media_library():
    allowed = {"image/jpeg", "image/png", "image/webp"}
    if request.method == "POST":
        upload = request.files.get("photo")
        if not upload or upload.mimetype not in allowed:
            flash("Upload a JPG, PNG, or WebP food photo.", "error")
            return redirect(url_for("main.media_library"))
        data = upload.read()
        if not data or len(data) > 10 * 1024 * 1024:
            flash("Photos must be smaller than 10 MB.", "error")
            return redirect(url_for("main.media_library"))
        asset = MediaAsset(organization_id=g.organization.id, filename=secure_filename(upload.filename) or "food-photo.jpg", mime_type=upload.mimetype, byte_size=len(data), title=request.form.get("title", "").strip(), tags=request.form.get("tags", "").strip(), data=data)
        db.session.add(asset)
        db.session.commit()
        flash("Photo uploaded and ready for content creation.", "success")
        return redirect(url_for("main.media_library"))
    assets = db.session.execute(scoped(MediaAsset).order_by(MediaAsset.created_at.desc())).scalars().all()
    return render_template("app/media.html", assets=assets)


@main_bp.get("/app/media/<int:asset_id>")
@login_required
@tenant_required
def media_file(asset_id):
    asset = db.session.execute(scoped(MediaAsset).where(MediaAsset.id == asset_id)).scalar_one_or_none()
    if not asset:
        abort(404)
    return send_file(BytesIO(asset.data), mimetype=asset.mime_type, download_name=asset.filename, max_age=3600)


@main_bp.get("/app/integrations")
@login_required
@tenant_required
def integrations():
    google = db.session.execute(db.select(GoogleConnection).where(GoogleConnection.organization_id == g.organization.id)).scalar_one_or_none()
    meta = db.session.execute(db.select(MetaConnection).where(MetaConnection.organization_id == g.organization.id)).scalar_one_or_none()
    return render_template("app/integrations.html", google=google, meta=meta, google_ready=bool(current_app.config["GOOGLE_CLIENT_ID"]), meta_ready=bool(current_app.config["META_APP_ID"]))


@main_bp.route("/app/leads", methods=["GET", "POST"])
@login_required
@tenant_required
def leads():
    if request.method == "POST":
        lead = Lead(organization_id=g.organization.id, name=request.form.get("name", "").strip(), company=request.form.get("company", "").strip(), email=request.form.get("email", "").strip(), phone=request.form.get("phone", "").strip(), source=request.form.get("source", "Website"), stage=request.form.get("stage", "new"), estimated_value=int(request.form.get("estimated_value") or 0), notes=request.form.get("notes", "").strip())
        if lead.name:
            db.session.add(lead)
            db.session.commit()
            flash("Lead added to the pipeline.", "success")
        return redirect(url_for("main.leads"))
    rows = db.session.execute(scoped(Lead).order_by(Lead.created_at.desc())).scalars().all()
    return render_template("app/leads.html", leads=rows)


@main_bp.post("/app/leads/<int:lead_id>/stage")
@login_required
@tenant_required
def lead_stage(lead_id):
    lead = db.session.execute(scoped(Lead).where(Lead.id == lead_id)).scalar_one_or_none()
    if not lead:
        return jsonify(error="not found"), 404
    lead.stage = request.form.get("stage", lead.stage)
    db.session.commit()
    return redirect(url_for("main.leads"))


@main_bp.route("/app/engagement", methods=["GET", "POST"])
@login_required
@tenant_required
def engagement():
    if request.method == "POST":
        item = Engagement(organization_id=g.organization.id, platform=request.form.get("platform", "Instagram"), contact_name=request.form.get("contact_name", "Guest"), message=request.form.get("message", ""), sentiment=request.form.get("sentiment", "positive"))
        db.session.add(item)
        db.session.commit()
        return redirect(url_for("main.engagement"))
    items = db.session.execute(scoped(Engagement).order_by(Engagement.created_at.desc())).scalars().all()
    return render_template("app/engagement.html", engagements=items)


@main_bp.post("/app/engagement/<int:item_id>/close")
@login_required
@tenant_required
def close_engagement(item_id):
    item = db.session.execute(scoped(Engagement).where(Engagement.id == item_id)).scalar_one_or_none()
    if not item:
        return jsonify(error="not found"), 404
    item.status = "closed"
    db.session.commit()
    return redirect(url_for("main.engagement"))
