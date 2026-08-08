from datetime import datetime, timedelta, timezone

import click

from . import db
from .models import BrandProfile, ContentItem, Engagement, Lead, Membership, Organization, User


def register_commands(app):
    @app.cli.command("seed-demo")
    def seed_demo():
        """Create a safe, repeatable demo workspace."""
        email = "demo@cravelv.com"
        user = db.session.execute(db.select(User).where(User.email == email)).scalar_one_or_none()
        if user:
            click.echo("Demo workspace already exists.")
            return
        user = User(name="Jasmine Lee", email=email)
        user.set_password("CraveDemo123!")
        org = Organization(name="Streetbird Kitchen", slug="streetbird-kitchen")
        db.session.add_all([user, org])
        db.session.flush()
        db.session.add_all([
            Membership(user_id=user.id, organization_id=org.id, role="owner"),
            BrandProfile(organization_id=org.id, business_name="Streetbird Kitchen", tagline="Big flavor. No shortcuts.", cuisine="Modern comfort food", city="Las Vegas", audience="Downtown lunch crowds, food lovers, and event planners", instagram="@streetbirdkitchen"),
            ContentItem(organization_id=org.id, title="First Friday location", caption="First Friday, we’re bringing the heat downtown. Find the orange truck from 5–10 PM.", channel="Instagram", status="scheduled", scheduled_for=datetime.now(timezone.utc) + timedelta(days=2)),
            ContentItem(organization_id=org.id, title="Brisket bowl spotlight", caption="Low and slow meets ready to go. Our brisket mac bowl is on the window this week.", channel="Facebook", status="draft"),
            Lead(organization_id=org.id, name="Maya Chen", company="Apex Events", email="maya@example.com", source="Website", stage="proposal", estimated_value=1200, notes="Corporate lunch for 75 guests"),
            Lead(organization_id=org.id, name="Daniel Ruiz", company="Desert Makers Market", source="Referral", stage="new", estimated_value=850),
            Engagement(organization_id=org.id, platform="Instagram", contact_name="Kira", message="Will you have the brisket mac bowl at First Friday?", sentiment="positive"),
            Engagement(organization_id=org.id, platform="Facebook", contact_name="Andre", message="Do you cater office lunches for around 50 people?", sentiment="positive"),
        ])
        db.session.commit()
        click.echo("Demo ready: demo@cravelv.com / CraveDemo123!")

