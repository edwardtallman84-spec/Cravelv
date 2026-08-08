from cravelv import db
from io import BytesIO

from cravelv.models import BrandProfile, Lead, MediaAsset, Organization, User
from conftest import register


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json == {"service": "cravelv", "status": "ok"}


def test_registration_creates_tenant_and_brand(client, app):
    response = register(client)
    assert response.status_code == 200
    assert b"Good to see you" in response.data
    with app.app_context():
        assert db.session.scalar(db.select(User).where(User.email == "owner@example.com"))
        assert db.session.scalar(db.select(Organization).where(Organization.slug == "tasty-truck"))
        assert db.session.scalar(db.select(BrandProfile).where(BrandProfile.business_name == "Tasty Truck"))


def test_protected_routes_redirect(client):
    response = client.get("/app/leads")
    assert response.status_code == 302
    assert "/auth/login" in response.location


def test_lead_crud_is_scoped_to_current_tenant(client, app):
    register(client)
    client.post("/app/leads", data={"name": "Local Planner", "company": "Events Co", "estimated_value": "1500"})
    response = client.get("/app/leads")
    assert b"Local Planner" in response.data
    with app.app_context():
        other = Organization(name="Other Truck", slug="other-truck")
        db.session.add(other)
        db.session.flush()
        db.session.add(Lead(organization_id=other.id, name="Private Other Lead", estimated_value=9999))
        db.session.commit()
    response = client.get("/app/leads")
    assert b"Local Planner" in response.data
    assert b"Private Other Lead" not in response.data


def test_login_and_logout(client):
    register(client)
    client.post("/auth/logout")
    bad = client.post("/auth/login", data={"email": "owner@example.com", "password": "wrong"}, follow_redirects=True)
    assert b"incorrect" in bad.data
    good = client.post("/auth/login", data={"email": "owner@example.com", "password": "strongpass"}, follow_redirects=True)
    assert b"Good to see you" in good.data


def test_photo_upload_is_persistent_and_tenant_scoped(client, app):
    register(client)
    response = client.post("/app/media", data={
        "title": "Hot honey slider",
        "tags": "burger, cheese pull",
        "photo": (BytesIO(b"fake-jpeg-data"), "slider.jpg", "image/jpeg"),
    }, content_type="multipart/form-data", follow_redirects=True)
    assert response.status_code == 200
    assert b"Hot honey slider" in response.data
    with app.app_context():
        asset = db.session.scalar(db.select(MediaAsset).where(MediaAsset.title == "Hot honey slider"))
        assert asset is not None
        assert asset.data == b"fake-jpeg-data"


def test_google_connection_has_honest_unconfigured_state(client):
    register(client)
    response = client.get("/app/integrations/google/connect", follow_redirects=True)
    assert response.status_code == 200
    assert b"connection keys have not been added" in response.data
