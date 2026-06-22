import os
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Always load .env from project root regardless of working directory
load_dotenv(os.path.join(BASE_DIR, ".env"), override=True)


class Config:
    # ── Core ──────────────────────────────────────────────────────────────────
    SECRET_KEY = os.environ.get("SECRET_KEY", "fallback-secret-key-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "postgresql://postgres:password@localhost:5432/talent_portal"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ── Uploads ───────────────────────────────────────────────────────────────
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "app", "static", "uploads")
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", 5 * 1024 * 1024))
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

    # ── CSRF ──────────────────────────────────────────────────────────────────
    WTF_CSRF_ENABLED = True

    # ── Password reset token expiry (seconds) ─────────────────────────────────
    PASSWORD_RESET_EXPIRY = 3600  # 1 hour

    # ── Rate limiting ─────────────────────────────────────────────────────────
    RATELIMIT_STORAGE_URI = "memory://"
    RATELIMIT_DEFAULT = "200 per day;50 per hour"

    # ── Mail ──────────────────────────────────────────────────────────────────
    # MAIL_USE_CONSOLE=true  → prints reset link to terminal (no real email)
    # MAIL_USE_CONSOLE=false → sends real email via Gmail SMTP
    MAIL_USE_CONSOLE = os.environ.get("MAIL_USE_CONSOLE", "true").lower() == "true"
    MAIL_SERVER     = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT       = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS    = os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USE_SSL    = False   # TLS on 587 — not SSL on 465
    MAIL_USERNAME   = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD   = os.environ.get("MAIL_PASSWORD", "")
    # Flask-Mail reads MAIL_DEFAULT_SENDER as (name, address) tuple or plain string
    MAIL_DEFAULT_SENDER = os.environ.get(
        "MAIL_DEFAULT_SENDER",
        os.environ.get("MAIL_USERNAME", "noreply@talentportal.com"),
    )

    # ── API ───────────────────────────────────────────────────────────────────
    API_SECRET_KEY = os.environ.get("API_SECRET_KEY", "tp-api-key-change-me")


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    WTF_CSRF_ENABLED = True
    MAIL_USE_CONSOLE = False   # Always send real emails in production


class TestingConfig(Config):
    """
    In-process SQLite database; CSRF, rate-limiting and real mail all disabled.
    The fixture overrides SQLALCHEMY_DATABASE_URI and UPLOAD_FOLDER at runtime
    so each test gets its own temp directory.
    """
    TESTING = True
    DEBUG = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    RATELIMIT_ENABLED = False
    RATELIMIT_STORAGE_URI = "memory://"
    MAIL_USE_CONSOLE = True
    PASSWORD_RESET_EXPIRY = 3600
    SERVER_NAME = "localhost"
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "app", "static", "uploads")


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}
