from datetime import datetime, timedelta, timezone

from flask import Blueprint, flash, g, jsonify, redirect, render_template, request, url_for
from flask_login import login_required

from . import db
from .models import BrandProfile, ContentItem, Engagement, Lead
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
    if request.method == "POST":
        topic = request.form.get("topic", "today's special").strip()
        offer = request.form.get("offer", "").strip()
        profile = g.organization.brand_profile
        hook = f"{profile.city}, come hungry — {topic} is calling."
        generated = f"{hook}\n\nFresh from {profile.business_name}, made for people who know great {profile.cuisine or 'food'}. {offer}\n\nFind us today and bring your appetite.\n\n#FoodTruck #SupportLocal #{profile.city.replace(' ', '')}Eats"
    drafts = db.session.execute(scoped(ContentItem).where(ContentItem.status == "draft").order_by(ContentItem.created_at.desc())).scalars().all()
    return render_template("app/studio.html", generated=generated, drafts=drafts)


@main_bp.post("/app/studio/save")
@login_required
@tenant_required
def save_content():
    caption = request.form.get("caption", "").strip()
    if caption:
        db.session.add(ContentItem(organization_id=g.organization.id, title=request.form.get("title", "New campaign"), caption=caption, channel=request.form.get("channel", "Instagram")))
        db.session.commit()
        flash("Draft saved to your content calendar.", "success")
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
    return render_template("app/calendar.html", items=items)


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

