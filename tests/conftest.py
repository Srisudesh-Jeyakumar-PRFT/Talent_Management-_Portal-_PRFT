"""
Shared pytest fixtures for the talent-portal test suite.

Strategy
--------
We call create_app("testing") so the *real* Flask app is used — Jinja2
therefore finds app/templates/, extensions are wired up in the same order
as production, and all blueprints are registered identically.

The only per-test overrides are the SQLite file path and upload folder,
both placed inside a pytest tmp_path directory so every test is isolated.
"""
import pytest
from types import SimpleNamespace

from app import create_app, db
from app.models import User


@pytest.fixture(scope="function")
def app(tmp_path):
    """
    Per-test isolated Flask application backed by a fresh SQLite database.

    The app context is active for the entire test body via the generator
    yield, so tests can interact with the DB directly using db.session.
    """
    upload_folder = tmp_path / "uploads"
    upload_folder.mkdir()

    flask_app = create_app("testing")
    # Override only the paths that must be unique per test run
    flask_app.config.update(
        SQLALCHEMY_DATABASE_URI=f"sqlite:///{tmp_path / 'test.db'}",
        UPLOAD_FOLDER=str(upload_folder),
    )

    with flask_app.app_context():
        db.create_all()
        yield flask_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Plain test client — no session / logged-out state."""
    return app.test_client()


@pytest.fixture
def user(app):
    """
    A pre-created active user seeded in the test database.

    Returns a SimpleNamespace so the attributes remain accessible after
    the seeding session closes (avoids DetachedInstanceError).
    """
    with app.app_context():
        u = User(username="testuser", email="test@example.com")
        u.set_password("Password1")
        db.session.add(u)
        db.session.commit()
        return SimpleNamespace(id=u.id, username=u.username, email=u.email)


@pytest.fixture
def inactive_user(app):
    """A pre-created user whose is_active flag is False."""
    with app.app_context():
        u = User(username="inactiveuser", email="inactive@example.com", is_active=False)
        u.set_password("Password1")
        db.session.add(u)
        db.session.commit()
        return SimpleNamespace(id=u.id, username=u.username, email=u.email)


@pytest.fixture
def logged_in_client(client, user):
    """
    A test client that already holds an authenticated session for *user*.

    Asserts the redirect immediately so a broken login route produces a
    clear failure here rather than a confusing error inside the test body.
    """
    resp = client.post(
        "/auth/login",
        data={"email": user.email, "password": "Password1"},
        follow_redirects=False,
    )
    assert resp.status_code == 302, (
        f"Login fixture failed — expected 302 but got {resp.status_code}.\n"
        f"Response body (first 500 chars): {resp.data[:500]}"
    )
    return client
