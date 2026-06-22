"""
Mail service for TalentPortal.

WHO IS THE SENDER?

Your Gmail account acts as the sender. The app authenticates to Gmail's
SMTP server using an "App Password" (not your normal Gmail password).
Gmail then delivers the email to the recipient on your behalf.

  Sender  :  your Gmail address  (MAIL_USERNAME in .env)
  Receiver:  the user's registered email
  Via     :  Gmail SMTP → smtp.gmail.com:587

CONSOLE MODE (development):

When MAIL_USE_CONSOLE=true the email is never sent — it is printed to
the terminal so you can copy-paste the reset link directly.
Set MAIL_USE_CONSOLE=false and fill in Gmail credentials to send real emails.
"""
import logging
from flask import current_app
from flask_mail import Message
from app import mail

logger = logging.getLogger(__name__)


#  Internal HTML email template 

def _build_reset_html(username: str, reset_url: str) -> str:
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:#f8f9fb;font-family:'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f8f9fb;padding:40px 0;">
    <tr>
      <td align="center">
        <table width="580" cellpadding="0" cellspacing="0"
               style="background:#ffffff;border-radius:12px;
                      box-shadow:0 2px 12px rgba(0,0,0,0.08);overflow:hidden;">

          <!-- Header -->
          <tr>
            <td style="background:linear-gradient(135deg,#1a73e8,#0d47a1);
                       padding:32px 40px;text-align:center;">
              <h1 style="margin:0;color:#ffffff;font-size:24px;font-weight:700;">
                🔐 TalentPortal
              </h1>
              <p style="margin:6px 0 0;color:#c5dbfa;font-size:14px;">
                Password Reset Request
              </p>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:40px;">
              <p style="margin:0 0 16px;font-size:16px;color:#333;">
                Hi <strong>{username}</strong>,
              </p>
              <p style="margin:0 0 16px;font-size:15px;color:#555;line-height:1.6;">
                We received a request to reset the password for your TalentPortal account.
                Click the button below — this link is valid for <strong>1 hour</strong>.
              </p>

              <!-- CTA Button -->
              <table cellpadding="0" cellspacing="0" style="margin:28px 0;">
                <tr>
                  <td style="border-radius:8px;background:#1a73e8;">
                    <a href="{reset_url}"
                       style="display:inline-block;padding:14px 32px;
                              color:#ffffff;font-size:15px;font-weight:600;
                              text-decoration:none;border-radius:8px;">
                      Reset My Password
                    </a>
                  </td>
                </tr>
              </table>

              <p style="margin:0 0 8px;font-size:13px;color:#888;">
                If the button doesn't work, copy and paste this URL into your browser:
              </p>
              <p style="margin:0 0 24px;word-break:break-all;">
                <a href="{reset_url}" style="color:#1a73e8;font-size:13px;">{reset_url}</a>
              </p>

              <hr style="border:none;border-top:1px solid #eee;margin:24px 0;">

              <p style="margin:0;font-size:13px;color:#aaa;line-height:1.6;">
                If you did not request a password reset, you can safely ignore this email.
                Your password will not be changed.<br><br>
                For security, this link expires in <strong>1 hour</strong> and can
                only be used once.
              </p>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background:#f8f9fb;padding:20px 40px;text-align:center;">
              <p style="margin:0;font-size:12px;color:#bbb;">
                © 2026 TalentPortal &nbsp;|&nbsp; This is an automated message, do not reply.
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""


def _build_reset_text(username: str, reset_url: str) -> str:
    """Plain-text fallback for email clients that don't render HTML."""
    return (
        f"Hi {username},\n\n"
        f"We received a request to reset your TalentPortal password.\n\n"
        f"Click the link below to reset it (valid for 1 hour):\n\n"
        f"{reset_url}\n\n"
        f"If you did not request this, ignore this email — "
        f"your password will not change.\n\n"
        f"— TalentPortal"
    )


#  Public API 

def send_password_reset_email(user, reset_url: str) -> bool:
    """
    Send the password reset email.

    Returns True if sent successfully (or console mode), False on failure.

    In CONSOLE mode  → prints the link to the terminal (no real email).
    In SMTP mode     → sends via Gmail SMTP using credentials in .env.
    """
    use_console = current_app.config.get("MAIL_USE_CONSOLE", True)

    if use_console:
        #  Development: print to terminal 
        border = "=" * 64
        logger.info(
            "\n%s\n"
            "  PASSWORD RESET EMAIL  (MAIL_USE_CONSOLE=true)\n"
            "  To      : %s\n"
            "  Username: %s\n"
            "  Link    : %s\n"
            "  Expires : 1 hour from now\n"
            "%s\n",
            border, user.email, user.username, reset_url, border,
        )
        return True

    #  Production: send via SMTP 
    try:
        sender = current_app.config.get("MAIL_DEFAULT_SENDER") or \
                 current_app.config.get("MAIL_USERNAME")

        msg = Message(
            subject="Reset your TalentPortal password",
            sender=sender,
            recipients=[user.email],
        )
        msg.body = _build_reset_text(user.username, reset_url)
        msg.html = _build_reset_html(user.username, reset_url)

        mail.send(msg)
        logger.info("Password reset email sent to %s", user.email)
        return True

    except Exception:
        logger.exception(
            "Failed to send password reset email to %s. "
            "Check MAIL_USERNAME / MAIL_PASSWORD in .env.",
            user.email,
        )
        return False


def send_test_email(recipient: str) -> bool:
    """
    Sends a simple test email to verify SMTP configuration is working.
    Called from the /auth/test-email development route.
    """
    try:
        sender = current_app.config.get("MAIL_DEFAULT_SENDER") or \
                 current_app.config.get("MAIL_USERNAME")
        msg = Message(
            subject="TalentPortal — SMTP test",
            sender=sender,
            recipients=[recipient],
        )
        msg.body = (
            "This is a test email from TalentPortal.\n"
            "If you received this, your SMTP configuration is working correctly."
        )
        mail.send(msg)
        logger.info("Test email sent to %s", recipient)
        return True
    except Exception:
        logger.exception("Test email failed to %s", recipient)
        return False
