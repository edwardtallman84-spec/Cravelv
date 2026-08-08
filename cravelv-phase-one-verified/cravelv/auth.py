import re

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_user, logout_user

from . import db
from .models import BrandProfile, Membership, Organization, User

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def slugify(value):
    base = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "business"
    slug, index = base, 2
    while db.session.execute(db.select(Organization).where(Organization.slug == slug)).scalar_one_or_none():
        slug, index = f"{base}-{index}", index + 1
    return slug


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        business = request.form.get("business", "").strip()
        password = request.form.get("password", "")
        if not all((name, email, business, password)) or len(password) < 8:
            flash("Complete every field and use at least 8 characters for your password.", "error")
        elif db.session.execute(db.select(User).where(User.email == email)).scalar_one_or_none():
            flash("An account with that email already exists.", "error")
        else:
            user = User(name=name, email=email)
            user.set_password(password)
            org = Organization(name=business, slug=slugify(business))
            db.session.add_all([user, org])
            db.session.flush()
            db.session.add_all([
                Membership(user_id=user.id, organization_id=org.id, role="owner"),
                BrandProfile(organization_id=org.id, business_name=business),
            ])
            db.session.commit()
            login_user(user)
            session["organization_id"] = org.id
            return redirect(url_for("main.dashboard"))
    return render_template("auth/register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = db.session.execute(db.select(User).where(User.email == email)).scalar_one_or_none()
        if user and user.check_password(request.form.get("password", "")):
            login_user(user, remember=bool(request.form.get("remember")))
            if user.memberships:
                session["organization_id"] = user.memberships[0].organization_id
            return redirect(request.args.get("next") or url_for("main.dashboard"))
        flash("Email or password is incorrect.", "error")
    return render_template("auth/login.html")


@auth_bp.post("/logout")
def logout():
    logout_user()
    session.clear()
    return redirect(url_for("main.landing"))

