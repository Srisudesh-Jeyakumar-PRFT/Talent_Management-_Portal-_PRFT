import logging
from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request, current_app, jsonify,
)
from flask_login import login_user, logout_user, login_required, current_user
from pydantic import ValidationError
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from datetime import datetime, timezone, timedelta

from app import db, limiter
from app.models import User
from app.utils import is_safe_url
from app.services.mail_service import send_password_reset_email, send_test_email
from app.validators import (
    RegisterSchema, LoginSchema,
    PasswordResetRequestSchema, PasswordResetSchema,
    collect_pydantic_errors,
)

logger = logging.getLogger(__name__)
auth_bp = Blueprint("auth", __name__)


def _get_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"]) #ensures tokens are created and not fake or tampered tokens are used with


#  Registration 

@auth_bp.route("/register", methods=["GET", "POST"])
@limiter.limit("20 per hour")
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    errors, form_data = [], {}

    if request.method == "POST": #get the form data to server to verify for errors
        form_data = {
            "username": request.form.get("username", "").strip(),
            "email":    request.form.get("email", "").strip(),
            "password": request.form.get("password", ""),
            "confirm_password": request.form.get("confirm_password", ""),
        }
        try:
            validated = RegisterSchema(**form_data) #pydantic validation

            if User.query.filter_by(username=validated.username).first():
                errors.append("username: Username is already taken.")
            if User.query.filter_by(email=validated.email).first():
                errors.append("email: Email is already registered.")

            if not errors:
                user = User(username=validated.username, email=validated.email)
                user.set_password(validated.password) #hash the password
                db.session.add(user)
                db.session.commit()
                logger.info("New user registered: %s", validated.email)
                flash("Registration successful! Please log in.", "success")
                return redirect(url_for("auth.login"))

        except ValidationError as e:
            errors = collect_pydantic_errors(e)

    return render_template("auth/register.html", errors=errors, form_data=form_data)


#  Login 

@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    errors, form_data = [], {}

    if request.method == "POST":
        form_data = {
            "email":    request.form.get("email", "").strip(),
            "password": request.form.get("password", ""),
        }
        try:
            validated = LoginSchema(**form_data)
            user = User.query.filter_by(email=validated.email).first()

            if user and user.check_password(validated.password): #check the hashed password
                if not user.is_active:
                    errors.append("Your account has been deactivated. Contact support.")
                else:
                    login_user(user, remember=request.form.get("remember") == "on")
                    next_page = request.args.get("next")
                    if next_page and not is_safe_url(next_page):
                        logger.warning("Blocked unsafe redirect to: %s", next_page)
                        next_page = None
                    logger.info("User logged in: %s", user.email)
                    flash(f"Welcome back, {user.username}!", "success")
                    return redirect(next_page or url_for("main.dashboard"))
            else:
                errors.append("Invalid email or password.")
                logger.warning("Failed login attempt for: %s", form_data.get("email"))

        except ValidationError as e:
            errors = collect_pydantic_errors(e)

    return render_template("auth/login.html", errors=errors, form_data=form_data)


#  Logout 

@auth_bp.route("/logout")
@login_required
def logout():
    logger.info("User logged out: %s", current_user.email)
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


#  Password Reset: Request 
#   User submits their email address.
#   App generates a signed token, stores it in DB, sends the email.

@auth_bp.route("/reset-password", methods=["GET", "POST"])
@limiter.limit("5 per hour", methods=["POST"])
def reset_password_request():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    errors = []
    sent = False
    console_mode = current_app.config.get("MAIL_USE_CONSOLE", True)

    if request.method == "POST":
        form_data = {"email": request.form.get("email", "").strip()}
        try:
            validated = PasswordResetRequestSchema(**form_data)
            user = User.query.filter_by(email=validated.email).first()

            if user:
                # Generate a signed, time-limited token from the user's email
                s = _get_serializer()
                token = s.dumps(user.email, salt="password-reset")

                # Build the full reset URL the user clicks in their email
                reset_url = url_for(
                    "auth.reset_password", token=token, _external=True
                )

                # Store token + expiry in DB so we can invalidate it after use
                user.reset_token        = token
                user.reset_token_expiry = datetime.now(timezone.utc) + timedelta(hours=1)
                db.session.commit()

                # Send email (or print to console in dev mode)
                email_sent = send_password_reset_email(user, reset_url)

                if not email_sent and not console_mode:
                    flash(
                        "Could not send the reset email. "
                        "Check your MAIL_USERNAME / MAIL_PASSWORD in .env.",
                        "danger",
                    )
                    return render_template(
                        "auth/reset_password_request.html",
                        errors=errors,
                        sent=False,
                        console_mode=console_mode,
                    )

            sent = True
            if console_mode:
                flash(
                    "Running in console mode — check the terminal window "
                    "where you ran 'python run.py' for the reset link.",
                    "info",
                )
            else:
                flash(
                    "If that email is registered, a password reset link "
                    "has been sent. Check your inbox (and spam folder).",
                    "info",
                )

        except ValidationError as e:
            errors = collect_pydantic_errors(e)
        except Exception:
            logger.exception("Unexpected error during password reset request")
            flash("An unexpected error occurred. Please try again.", "danger")

    return render_template(
        "auth/reset_password_request.html",
        errors=errors,
        sent=sent,
        console_mode=console_mode,
    )


#  Password Reset : Verify token + set new password 


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token: str):
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    errors = []

    # Validate the cryptographic signature and expiry 
    try:
        s = _get_serializer()
        email = s.loads(
            token,
            salt="password-reset",
            max_age=current_app.config.get("PASSWORD_RESET_EXPIRY", 3600),
        )
    except SignatureExpired:
        flash(
            "This reset link has expired (links are valid for 1 hour). "
            "Please request a new one.",
            "danger",
        )
        return redirect(url_for("auth.reset_password_request"))
    except BadSignature:
        flash("This reset link is invalid or has already been used.", "danger")
        return redirect(url_for("auth.reset_password_request"))

    user = User.query.filter_by(email=email).first()
    if not user:
        flash("Account not found.", "danger")
        return redirect(url_for("auth.reset_password_request"))

    if user.reset_token != token:
        flash(
            "This reset link has already been used or superseded by a newer request. "
            "Please request a fresh link.",
            "warning",
        )
        return redirect(url_for("auth.reset_password_request"))

    # Check DB-stored expiry as a second line of defence 
    if user.reset_token_expiry:
        expiry = user.reset_token_expiry
        # Make expiry timezone-aware if it isn't (old rows)
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expiry:
            # Clear stale token
            user.reset_token        = None
            user.reset_token_expiry = None
            db.session.commit()
            flash("This reset link has expired. Please request a new one.", "danger")
            return redirect(url_for("auth.reset_password_request"))

    if request.method == "POST":
        form_data = {
            "password":         request.form.get("password", ""),
            "confirm_password": request.form.get("confirm_password", ""),
        }
        try:
            validated = PasswordResetSchema(**form_data)
            user.set_password(validated.password)
            # Invalidate the token so the link cannot be reused
            user.reset_token        = None
            user.reset_token_expiry = None
            db.session.commit()
            logger.info("Password reset completed for: %s", email)
            flash(
                "Your password has been reset successfully. You can now log in.",
                "success",
            )
            return redirect(url_for("auth.login"))
        except ValidationError as e:
            errors = collect_pydantic_errors(e)

    return render_template("auth/reset_password.html", errors=errors, token=token)


#  Change Password (logged-in users only) 


@auth_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    errors = []

    if request.method == "POST":
        current_pw  = request.form.get("current_password", "")
        new_pw      = request.form.get("new_password", "")
        confirm_pw  = request.form.get("confirm_password", "")

        if not current_user.check_password(current_pw):
            errors.append("Current password is incorrect.")

        if not errors:
            from app.validators import PasswordResetSchema, collect_pydantic_errors
            from pydantic import ValidationError as PydanticValidationError
            try:
                PasswordResetSchema(password=new_pw, confirm_password=confirm_pw)
            except PydanticValidationError as e:
                errors = collect_pydantic_errors(e)

        # make sure new password is different
        if not errors and current_user.check_password(new_pw):
            errors.append("new_password: New password must be different from the current one.")

        if not errors:
            current_user.set_password(new_pw)
            db.session.commit()
            logger.info("Password changed by user: %s", current_user.email)
            flash("Password changed successfully!", "success")
            return redirect(url_for("main.dashboard"))

    return render_template("auth/change_password.html", errors=errors)


#  Test Email Route (development only) 

#   Visit /auth/test-email in your browser to verify Gmail SMTP is working.
#   Only works when DEBUG=True.

@auth_bp.route("/test-email")
def test_email():
    if not current_app.debug:
        return "Not available in production.", 403

    recipient = request.args.get("to", "")
    if not recipient:
        return (
            "<h3>TalentPortal — Email Test</h3>"
            "<p>Add <code>?to=your@email.com</code> to the URL to send a test email.</p>"
            "<p>Example: <code>/auth/test-email?to=you@gmail.com</code></p>"
            "<p>Make sure <code>MAIL_USE_CONSOLE=false</code> and Gmail credentials "
            "are set in <code>.env</code> first.</p>",
            200,
        )

    console_mode = current_app.config.get("MAIL_USE_CONSOLE", True)
    if console_mode:
        return (
            "<h3>Console mode is ON</h3>"
            "<p>Set <code>MAIL_USE_CONSOLE=false</code> in <code>.env</code> "
            "and restart the app to send a real test email.</p>",
            200,
        )

    ok = send_test_email(recipient)
    if ok:
        return jsonify({
            "status": "sent",
            "message": f"Test email sent to {recipient}. Check your inbox.",
        })
    return jsonify({
        "status": "failed",
        "message": "SMTP error — check terminal logs and your .env credentials.",
    }), 500
