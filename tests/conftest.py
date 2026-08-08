import pytest

from cravelv import create_app, db


@pytest.fixture()
def app(tmp_path):
    app = create_app({"TESTING": True, "SECRET_KEY": "test", "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'test.db'}", "WTF_CSRF_ENABLED": False})
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def register(client, email="owner@example.com", business="Tasty Truck"):
    return client.post("/auth/register", data={"name": "Test Owner", "email": email, "business": business, "password": "strongpass"}, follow_redirects=True)

