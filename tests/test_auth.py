from datetime import datetime, timedelta, timezone

import pytest
from itsdangerous import URLSafeTimedSerializer

from app import db
from app.models import User


def make_reset_token(app, email):
    serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"])
    return serializer.dumps(email, salt="password-reset")


def test_register_get_renders_form(client):
    response = client.get("/auth/register")

    assert response.status_code == 200
    assert b"register" in response.data.lower()


def test_register_creates_user_and_redirects_to_login(app, client):
    response = client.post(
        "/auth/register",
        data={
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "Password1",
            "confirm_password": "Password1",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/login")

    with app.app_context():
        created_user = User.query.filter_by(email="newuser@example.com").first()
        assert created_user is not None
        assert created_user.username == "newuser"
        assert created_user.password_hash != "Password1"
        assert created_user.check_password("Password1") is True


def test_register_rejects_duplicate_username_and_email(app, client, user):
    response = client.post(
        "/auth/register",
        data={
            "username": user.username,
            "email": user.email,
            "password": "Password1",
            "confirm_password": "Password1",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Username is already taken" in response.data
    assert b"Email is already registered" in response.data

    with app.app_context():
        assert User.query.count() == 1


def test_register_trims_username_and_email(app, client):
    response = client.post(
        "/auth/register",
        data={
            "username": "  spaced_user  ",
            "email": "  spaced@example.com  ",
            "password": "Password1",
            "confirm_password": "Password1",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302

    with app.app_context():
        created_user = User.query.filter_by(email="spaced@example.com").first()
        assert created_user is not None
        assert created_user.username == "spaced_user"


@pytest.mark.parametrize(
    "payload, expected_error",
    [
        (
            {
                "username": "ab",
                "email": "valid@example.com",
                "password": "Password1",
                "confirm_password": "Password1",
            },
            b"Username must be at least 3 characters",
        ),
        (
            {
                "username": "valid_user",
                "email": "not-an-email",
                "password": "Password1",
                "confirm_password": "Password1",
            },
            b"valid email address",
        ),
        (
            {
                "username": "valid_user",
                "email": "valid@example.com",
                "password": "password1",
                "confirm_password": "password1",
            },
            b"Password must contain at least one uppercase letter",
        ),
        (
            {
                "username": "valid_user",
                "email": "valid@example.com",
                "password": "Password1",
                "confirm_password": "Password2",
            },
            b"Passwords do not match",
        ),
    ],
)
def test_register_validation_errors_do_not_create_user(app, client, payload, expected_error):
    response = client.post("/auth/register", data=payload, follow_redirects=True)

    assert response.status_code == 200
    assert expected_error in response.data

    with app.app_context():
        assert User.query.count() == 0


def test_login_redirects_to_dashboard_on_success(client, user):
    response = client.post(
        "/auth/login",
        data={"email": user.email, "password": "Password1"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard")


def test_login_rejects_wrong_password(client, user):
    response = client.post(
        "/auth/login",
        data={"email": user.email, "password": "WrongPassword1"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Invalid email or password" in response.data


def test_login_rejects_inactive_user(client, inactive_user):
    response = client.post(
        "/auth/login",
        data={"email": inactive_user.email, "password": "Password1"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Your account has been deactivated" in response.data


def test_login_rejects_blank_password(client):
    response = client.post(
        "/auth/login",
        data={"email": "test@example.com", "password": "   "},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Password cannot be empty" in response.data


def test_login_blocks_unsafe_next_redirect(client, user):
    response = client.post(
        "/auth/login?next=https://evil.example/phish",
        data={"email": user.email, "password": "Password1"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard")


def test_login_allows_safe_relative_next_redirect(client, user):
    response = client.post(
        "/auth/login?next=/profile/edit",
        data={"email": user.email, "password": "Password1"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/profile/edit")


def test_logout_requires_login(client):
    response = client.get("/auth/logout", follow_redirects=False)

    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_logout_clears_session(logged_in_client):
    response = logged_in_client.get("/auth/logout", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/login")

    dashboard_response = logged_in_client.get("/dashboard", follow_redirects=False)
    assert dashboard_response.status_code == 302
    assert "/auth/login" in dashboard_response.headers["Location"]


def test_reset_password_request_sets_token_for_existing_user(app, client, user, monkeypatch):
    sent_urls = []

    def fake_send_password_reset_email(target_user, reset_url):
        sent_urls.append((target_user.email, reset_url))
        return True

    monkeypatch.setattr("app.routes.auth.send_password_reset_email", fake_send_password_reset_email)

    response = client.post(
        "/auth/reset-password",
        data={"email": user.email},
        follow_redirects=True,
    )

    assert response.status_code == 200

    with app.app_context():
        refreshed_user = db.session.get(User, user.id)
        assert refreshed_user.reset_token is not None
        assert refreshed_user.reset_token_expiry is not None
        # SQLite drops timezone info; normalise to naive UTC before comparing
        expiry = refreshed_user.reset_token_expiry
        if expiry.tzinfo is not None:
            expiry = expiry.replace(tzinfo=None)
        assert expiry > datetime.now(timezone.utc).replace(tzinfo=None)

    assert sent_urls
    assert sent_urls[0][0] == user.email
    assert "/auth/reset-password/" in sent_urls[0][1]


def test_reset_password_request_does_not_fail_for_unknown_email(app, client, monkeypatch):
    called = False

    def fake_send_password_reset_email(target_user, reset_url):
        nonlocal called
        called = True
        return True

    monkeypatch.setattr("app.routes.auth.send_password_reset_email", fake_send_password_reset_email)

    response = client.post(
        "/auth/reset-password",
        data={"email": "missing@example.com"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert called is False

    with app.app_context():
        assert User.query.count() == 0


def test_reset_password_request_shows_mail_failure_when_not_console_mode(app, client, user, monkeypatch):
    app.config["MAIL_USE_CONSOLE"] = False

    monkeypatch.setattr("app.routes.auth.send_password_reset_email", lambda target_user, reset_url: False)

    response = client.post(
        "/auth/reset-password",
        data={"email": user.email},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Could not send the reset email" in response.data


def test_reset_password_request_handles_unexpected_exception(client, user, monkeypatch):
    def blow_up(*args, **kwargs):
        raise RuntimeError("mail backend unavailable")

    monkeypatch.setattr("app.routes.auth.send_password_reset_email", blow_up)

    response = client.post(
        "/auth/reset-password",
        data={"email": user.email},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"An unexpected error occurred" in response.data


def test_reset_password_rejects_invalid_token(client):
    response = client.get("/auth/reset-password/not-a-valid-token", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/reset-password")


def test_reset_password_rejects_used_or_superseded_token(app, client, user):
    valid_token = make_reset_token(app, user.email)

    with app.app_context():
        refreshed_user = db.session.get(User, user.id)
        refreshed_user.reset_token = "different-token"
        refreshed_user.reset_token_expiry = datetime.now(timezone.utc) + timedelta(minutes=30)
        db.session.commit()

    response = client.get(f"/auth/reset-password/{valid_token}", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/reset-password")


def test_reset_password_clears_expired_db_token(app, client, user):
    expired_token = make_reset_token(app, user.email)

    with app.app_context():
        refreshed_user = db.session.get(User, user.id)
        refreshed_user.reset_token = expired_token
        refreshed_user.reset_token_expiry = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.session.commit()

    response = client.get(f"/auth/reset-password/{expired_token}", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/reset-password")

    with app.app_context():
        refreshed_user = db.session.get(User, user.id)
        assert refreshed_user.reset_token is None
        assert refreshed_user.reset_token_expiry is None


def test_reset_password_accepts_naive_expiry_and_resets_password(app, client, user):
    token = make_reset_token(app, user.email)

    with app.app_context():
        refreshed_user = db.session.get(User, user.id)
        refreshed_user.reset_token = token
        # Store as naive datetime to simulate what SQLite returns for older rows
        refreshed_user.reset_token_expiry = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=30)
        db.session.commit()

    response = client.post(
        f"/auth/reset-password/{token}",
        data={"password": "NewPassword1", "confirm_password": "NewPassword1"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/login")

    with app.app_context():
        refreshed_user = db.session.get(User, user.id)
        assert refreshed_user.check_password("NewPassword1") is True
        assert refreshed_user.reset_token is None
        assert refreshed_user.reset_token_expiry is None


def test_reset_password_rejects_invalid_new_password(app, client, user):
    token = make_reset_token(app, user.email)

    with app.app_context():
        refreshed_user = db.session.get(User, user.id)
        refreshed_user.reset_token = token
        refreshed_user.reset_token_expiry = datetime.now(timezone.utc) + timedelta(minutes=30)
        db.session.commit()

    response = client.post(
        f"/auth/reset-password/{token}",
        data={"password": "short", "confirm_password": "short"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Password must be at least 8 characters" in response.data

    with app.app_context():
        refreshed_user = db.session.get(User, user.id)
        assert refreshed_user.check_password("Password1") is True
        assert refreshed_user.reset_token == token


def test_change_password_requires_login(client):
    response = client.get("/auth/change-password", follow_redirects=False)

    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_change_password_updates_password(logged_in_client, app, user):
    response = logged_in_client.post(
        "/auth/change-password",
        data={
            "current_password": "Password1",
            "new_password": "ChangedPass1",
            "confirm_password": "ChangedPass1",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard")

    with app.app_context():
        refreshed_user = db.session.get(User, user.id)
        assert refreshed_user.check_password("ChangedPass1") is True


def test_change_password_rejects_wrong_current_password(logged_in_client, app, user):
    response = logged_in_client.post(
        "/auth/change-password",
        data={
            "current_password": "WrongPassword1",
            "new_password": "ChangedPass1",
            "confirm_password": "ChangedPass1",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Current password is incorrect" in response.data

    with app.app_context():
        refreshed_user = db.session.get(User, user.id)
        assert refreshed_user.check_password("Password1") is True


def test_change_password_rejects_reusing_current_password(logged_in_client, app, user):
    response = logged_in_client.post(
        "/auth/change-password",
        data={
            "current_password": "Password1",
            "new_password": "Password1",
            "confirm_password": "Password1",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"New password must be different from the current one" in response.data

    with app.app_context():
        refreshed_user = db.session.get(User, user.id)
        assert refreshed_user.check_password("Password1") is True


def test_change_password_rejects_invalid_new_password(logged_in_client, app, user):
    response = logged_in_client.post(
        "/auth/change-password",
        data={
            "current_password": "Password1",
            "new_password": "lowercase1",
            "confirm_password": "lowercase1",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Password must contain at least one uppercase letter" in response.data

    with app.app_context():
        refreshed_user = db.session.get(User, user.id)
        assert refreshed_user.check_password("Password1") is True
