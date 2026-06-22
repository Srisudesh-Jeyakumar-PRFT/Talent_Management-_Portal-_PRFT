import enum
from datetime import datetime, timezone
from app import db, login_manager
from flask_login import UserMixin
import bcrypt


# ── Many-to-many join table: talent_profiles <-> skills ───────────────────────
talent_skills = db.Table(
    "talent_skills",
    db.Column("profile_id", db.Integer, db.ForeignKey("talent_profiles.id"), primary_key=True),
    db.Column("skill_id", db.Integer, db.ForeignKey("skills.id"), primary_key=True),
)


class UserRole(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"


def utcnow():
    return datetime.now(timezone.utc)


class Skill(db.Model):
    __tablename__ = "skills"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)

    def __repr__(self):
        return f"<Skill {self.name}>"


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum(UserRole), default=UserRole.USER, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)
    reset_token = db.Column(db.String(255), nullable=True)
    reset_token_expiry = db.Column(db.DateTime(timezone=True), nullable=True)

    profile = db.relationship(
        "TalentProfile", backref="user", uselist=False, cascade="all, delete-orphan"
    )

    def set_password(self, password: str):
        salt = bcrypt.gensalt()
        self.password_hash = bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    def check_password(self, password: str) -> bool:
        return bcrypt.checkpw(
            password.encode("utf-8"), self.password_hash.encode("utf-8")
        )

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    def __repr__(self):
        return f"<User {self.username}>"


class TalentProfile(db.Model):
    __tablename__ = "talent_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True)

    full_name = db.Column(db.String(120), nullable=False)
    title = db.Column(db.String(120), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    experience_years = db.Column(db.Integer, nullable=True)
    location = db.Column(db.String(120), nullable=True)
    portfolio_url = db.Column(db.String(255), nullable=True)
    github_url = db.Column(db.String(255), nullable=True)
    linkedin_url = db.Column(db.String(255), nullable=True)
    photo_filename = db.Column(db.String(255), nullable=True)
    is_public = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    skills = db.relationship(
        "Skill",
        secondary=talent_skills,
        lazy="subquery",
        backref=db.backref("profiles", lazy=True),

    )
    experiences = db.relationship(
        "Experience", backref="profile", cascade="all, delete-orphan",
        order_by="Experience.order", lazy="select",
    )
    educations = db.relationship(
        "Education", backref="profile", cascade="all, delete-orphan",
        order_by="Education.order", lazy="select",
    )

    @property
    def skills_list(self) -> list[str]:
        """Return skill names as a sorted list."""
        return sorted([s.name for s in self.skills])

    @property
    def completeness(self) -> int:
        fields = {
            "photo": bool(self.photo_filename),
            "bio": bool(self.bio),
            "title": bool(self.title),
            "skills": bool(self.skills),
            "location": bool(self.location),
            "experience": self.experience_years is not None,
            "portfolio": bool(self.portfolio_url or self.github_url or self.linkedin_url),
        }
        filled = sum(fields.values())
        return int((filled / len(fields)) * 100)

    def set_skills_from_list(self, skill_names: list[str]):
        """
        Sync the M2M skills relationship from a list of name strings.
        Creates Skill rows that don't yet exist; removes ones no longer listed.
        """
        new_skills = []
        for name in skill_names:
            name = name.strip()
            if not name:
                continue
            skill = Skill.query.filter(
                db.func.lower(Skill.name) == name.lower()
            ).first()
            if not skill:
                skill = Skill(name=name)
                db.session.add(skill)
            new_skills.append(skill)
        self.skills = new_skills

    def to_dict(self) -> dict:
        """Serialize profile to dict for API responses."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "username": self.user.username if self.user else None,
            "full_name": self.full_name,
            "title": self.title,
            "bio": self.bio,
            "skills": self.skills_list,
            "experience_years": self.experience_years,
            "location": self.location,
            "portfolio_url": self.portfolio_url,
            "github_url": self.github_url,
            "linkedin_url": self.linkedin_url,
            "photo_url": f"/static/uploads/{self.photo_filename}" if self.photo_filename else None,
            "is_public": self.is_public,
            "completeness": self.completeness,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<TalentProfile {self.full_name}>"


class Experience(db.Model):
    __tablename__ = "experience"

    id          = db.Column(db.Integer, primary_key=True)
    profile_id  = db.Column(db.Integer, db.ForeignKey("talent_profiles.id", ondelete="CASCADE"), nullable=False)
    company     = db.Column(db.String(200), nullable=False)
    job_title   = db.Column(db.String(200), nullable=False)
    start_date  = db.Column(db.String(20),  nullable=False)
    end_date    = db.Column(db.String(20),  nullable=True)
    is_current  = db.Column(db.Boolean, default=False)
    description = db.Column(db.Text, nullable=True)
    order       = db.Column(db.Integer, default=0)

    def date_range(self) -> str:
        end = "Present" if self.is_current or not self.end_date else self.end_date
        return f"{self.start_date} – {end}"


class Education(db.Model):
    __tablename__ = "education"

    id          = db.Column(db.Integer, primary_key=True)
    profile_id  = db.Column(db.Integer, db.ForeignKey("talent_profiles.id", ondelete="CASCADE"), nullable=False)
    institution = db.Column(db.String(200), nullable=False)
    degree      = db.Column(db.String(200), nullable=False)
    field       = db.Column(db.String(200), nullable=True)
    start_year  = db.Column(db.String(10),  nullable=True)
    end_year    = db.Column(db.String(10),  nullable=True)
    order       = db.Column(db.Integer, default=0)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))
