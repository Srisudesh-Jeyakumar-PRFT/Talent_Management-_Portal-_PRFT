"""
Pydantic v2 validators for all form inputs.
Fix #8 — password strength logic defined once, reused everywhere.
"""
from pydantic import BaseModel, EmailStr, field_validator, model_validator
from typing import Optional
import re


# ── Fix #8: single shared password validator ──────────────────────────────────

def _check_password_strength(v: str) -> str:
    """Shared password strength rule used by Register and PasswordReset schemas."""
    if len(v) < 8:
        raise ValueError("Password must be at least 8 characters.")
    if not re.search(r"[A-Z]", v):
        raise ValueError("Password must contain at least one uppercase letter.")
    if not re.search(r"[0-9]", v):
        raise ValueError("Password must contain at least one digit.")
    return v


# ── Schemas ───────────────────────────────────────────────────────────────────

class RegisterSchema(BaseModel):
    username: str
    email: EmailStr
    password: str
    confirm_password: str

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3:
            raise ValueError("Username must be at least 3 characters.")
        if len(v) > 64:
            raise ValueError("Username must be at most 64 characters.")
        if not re.match(r"^[a-zA-Z0-9_.-]+$", v):
            raise ValueError(
                "Username may only contain letters, numbers, dots, dashes, and underscores."
            )
        return v

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _check_password_strength(v)

    @model_validator(mode="after")
    def passwords_match(self):
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match.")
        return self


class LoginSchema(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Password cannot be empty.")
        return v


class ProfileSchema(BaseModel):
    full_name: str
    title: Optional[str] = None
    bio: Optional[str] = None
    # skills is now a comma-separated string from the form, parsed into a list
    skills_raw: Optional[str] = None
    experience_years: Optional[int] = None
    location: Optional[str] = None
    portfolio_url: Optional[str] = None
    github_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    is_public: Optional[bool] = True

    @field_validator("full_name")
    @classmethod
    def full_name_valid(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Full name must be at least 2 characters.")
        if len(v) > 120:
            raise ValueError("Full name must be at most 120 characters.")
        return v

    @field_validator("experience_years", mode="before")
    @classmethod
    def experience_valid(cls, v):
        if v is None or v == "":
            return None
        try:
            v = int(v)
        except (ValueError, TypeError):
            raise ValueError("Experience years must be a whole number.")
        if v < 0 or v > 60:
            raise ValueError("Experience years must be between 0 and 60.")
        return v

    @field_validator("portfolio_url", "github_url", "linkedin_url", mode="before")
    @classmethod
    def url_optional(cls, v):
        if not v or v.strip() == "":
            return None
        v = v.strip()
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v

    @field_validator("bio", mode="before")
    @classmethod
    def bio_length(cls, v):
        if not v:
            return None
        if len(v) > 2000:
            raise ValueError("Bio must be at most 2000 characters.")
        return v.strip()

    @field_validator("skills_raw", mode="before")
    @classmethod
    def skills_raw_clean(cls, v):
        if not v:
            return None
        return v.strip()

    @property
    def skills_list(self) -> list[str]:
        """Parse the comma-separated skills_raw string into a clean list."""
        if not self.skills_raw:
            return []
        return [s.strip() for s in self.skills_raw.split(",") if s.strip()]


class PasswordResetRequestSchema(BaseModel):
    email: EmailStr


class PasswordResetSchema(BaseModel):
    password: str
    confirm_password: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        # Fix #8 — reuse shared validator, not a copy
        return _check_password_strength(v)

    @model_validator(mode="after")
    def passwords_match(self):
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match.")
        return self


# ── Error message helper ──────────────────────────────────────────────────────

def collect_pydantic_errors(exc) -> list[str]:
    """Extract human-readable error messages from a Pydantic ValidationError."""
    messages = []
    for error in exc.errors():
        loc = error.get("loc", ())
        # Map internal field names to friendly names
        field_map = {"skills_raw": "skills", "full_name": "full name"}
        field = field_map.get(str(loc[-1]), str(loc[-1])) if loc else "form"
        msg = error["msg"].replace("Value error, ", "")
        messages.append(f"{field}: {msg}")
    return messages
