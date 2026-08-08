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

