from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from . import db


def utcnow():
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class User(UserMixin, TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    memberships = db.relationship("Membership", back_populates="user", cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Organization(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    plan = db.Column(db.String(30), default="founder", nullable=False)
    memberships = db.relationship("Membership", back_populates="organization", cascade="all, delete-orphan")
    brand_profile = db.relationship("BrandProfile", back_populates="organization", uselist=False, cascade="all, delete-orphan")
    content_items = db.relationship("ContentItem", back_populates="organization", cascade="all, delete-orphan")
    leads = db.relationship("Lead", back_populates="organization", cascade="all, delete-orphan")
    engagements = db.relationship("Engagement", back_populates="organization", cascade="all, delete-orphan")
    media_assets = db.relationship("MediaAsset", back_populates="organization", cascade="all, delete-orphan")
    calendar_events = db.relationship("CalendarEvent", back_populates="organization", cascade="all, delete-orphan")
    publications = db.relationship("Publication", back_populates="organization", cascade="all, delete-orphan")


class Membership(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    organization_id = db.Column(db.Integer, db.ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    role = db.Column(db.String(30), default="owner", nullable=False)
    user = db.relationship("User", back_populates="memberships")
    organization = db.relationship("Organization", back_populates="memberships")
    __table_args__ = (db.UniqueConstraint("user_id", "organization_id"),)


class BrandProfile(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organization.id", ondelete="CASCADE"), unique=True, nullable=False)
    business_name = db.Column(db.String(150), nullable=False)
    tagline = db.Column(db.String(200), default="")
    cuisine = db.Column(db.String(120), default="")
    city = db.Column(db.String(120), default="Las Vegas")
    audience = db.Column(db.Text, default="")
    voice = db.Column(db.String(120), default="Bold, friendly, local")
    primary_color = db.Column(db.String(20), default="#ff5c35")
    instagram = db.Column(db.String(120), default="")
    website = db.Column(db.String(255), default="")
    organization = db.relationship("Organization", back_populates="brand_profile")


class ContentItem(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organization.id", ondelete="CASCADE"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    caption = db.Column(db.Text, nullable=False)
    channel = db.Column(db.String(40), default="Instagram", nullable=False)
    status = db.Column(db.String(30), default="draft", nullable=False)
    scheduled_for = db.Column(db.DateTime(timezone=True), nullable=True, index=True)
    organization = db.relationship("Organization", back_populates="content_items")


class Lead(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organization.id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(150), nullable=False)
    company = db.Column(db.String(150), default="")
    email = db.Column(db.String(255), default="")
    phone = db.Column(db.String(50), default="")
    source = db.Column(db.String(80), default="Website")
    stage = db.Column(db.String(40), default="new", nullable=False)
    estimated_value = db.Column(db.Integer, default=0)
    notes = db.Column(db.Text, default="")
    organization = db.relationship("Organization", back_populates="leads")


class Engagement(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organization.id", ondelete="CASCADE"), nullable=False, index=True)
    platform = db.Column(db.String(40), default="Instagram")
    contact_name = db.Column(db.String(120), nullable=False)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(30), default="open", nullable=False)
    sentiment = db.Column(db.String(20), default="positive")
    organization = db.relationship("Organization", back_populates="engagements")


class MediaAsset(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organization.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = db.Column(db.String(255), nullable=False)
    mime_type = db.Column(db.String(80), nullable=False)
    byte_size = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(160), default="", nullable=False)
    tags = db.Column(db.String(300), default="", nullable=False)
    data = db.Column(db.LargeBinary, nullable=False)
    organization = db.relationship("Organization", back_populates="media_assets")


class GoogleConnection(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organization.id", ondelete="CASCADE"), unique=True, nullable=False)
    email = db.Column(db.String(255), default="", nullable=False)
    calendar_id = db.Column(db.String(255), default="primary", nullable=False)
    encrypted_credentials = db.Column(db.Text, nullable=False)
    last_synced_at = db.Column(db.DateTime(timezone=True), nullable=True)


class CalendarEvent(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organization.id", ondelete="CASCADE"), nullable=False, index=True)
    external_id = db.Column(db.String(255), nullable=False)
    title = db.Column(db.String(240), nullable=False)
    location = db.Column(db.String(300), default="", nullable=False)
    description = db.Column(db.Text, default="", nullable=False)
    start_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    end_at = db.Column(db.DateTime(timezone=True), nullable=True)
    source_url = db.Column(db.String(500), default="", nullable=False)
    organization = db.relationship("Organization", back_populates="calendar_events")
    __table_args__ = (db.UniqueConstraint("organization_id", "external_id", name="uq_calendar_event_org_external"),)


class MetaConnection(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organization.id", ondelete="CASCADE"), unique=True, nullable=False)
    page_id = db.Column(db.String(80), nullable=False)
    page_name = db.Column(db.String(180), nullable=False)
    instagram_account_id = db.Column(db.String(80), default="", nullable=False)
    instagram_username = db.Column(db.String(180), default="", nullable=False)
    encrypted_page_token = db.Column(db.Text, nullable=False)


class Publication(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organization.id", ondelete="CASCADE"), nullable=False, index=True)
    content_item_id = db.Column(db.Integer, db.ForeignKey("content_item.id", ondelete="CASCADE"), nullable=False)
    media_asset_id = db.Column(db.Integer, db.ForeignKey("media_asset.id", ondelete="CASCADE"), nullable=False)
    platform = db.Column(db.String(30), nullable=False)
    status = db.Column(db.String(30), default="draft", nullable=False, index=True)
    scheduled_for = db.Column(db.DateTime(timezone=True), nullable=True, index=True)
    published_at = db.Column(db.DateTime(timezone=True), nullable=True)
    provider_post_id = db.Column(db.String(160), default="", nullable=False)
    error_message = db.Column(db.Text, default="", nullable=False)
    organization = db.relationship("Organization", back_populates="publications")
    content_item = db.relationship("ContentItem")
    media_asset = db.relationship("MediaAsset")

