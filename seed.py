"""
Seed script — creates initial admin user and sample talent profiles.
Updated for:
  - UserRole enum (Fix #11)
  - Skills M2M relationship (Fix #1)
  - Timezone-aware datetimes (Fix #5)

Run: python seed.py
"""
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)

from app import create_app, db
from app.models import User, TalentProfile, UserRole

app = create_app("development")

SAMPLE_TALENTS = [
    {
        "name": "Alice Johnson",
        "title": "Full Stack Developer",
        "skills": ["Python", "Flask", "React", "PostgreSQL", "Docker"],
        "bio": "Alice is a full stack developer passionate about clean APIs and great UX.",
        "experience_years": 6,
        "location": "San Francisco, CA",
        "portfolio_url": "https://alicejohnson.dev",
        "github_url": "https://github.com/alicejohnson",
    },
    {
        "name": "Bob Martinez",
        "title": "Data Scientist",
        "skills": ["Python", "Pandas", "scikit-learn", "TensorFlow", "SQL"],
        "bio": "Bob turns raw data into actionable insights using ML and statistical modelling.",
        "experience_years": 5,
        "location": "New York, NY",
        "github_url": "https://github.com/bobmartinez",
    },
    {
        "name": "Carol Lee",
        "title": "UI/UX Designer",
        "skills": ["Figma", "Adobe XD", "CSS", "HTML", "Sketch"],
        "bio": "Carol crafts intuitive and accessible user experiences.",
        "experience_years": 4,
        "location": "Austin, TX",
        "portfolio_url": "https://carollee.design",
        "linkedin_url": "https://linkedin.com/in/carollee",
    },
    {
        "name": "David Kim",
        "title": "DevOps Engineer",
        "skills": ["AWS", "Kubernetes", "Docker", "Terraform", "CI/CD"],
        "bio": "David automates infrastructure so developers can focus on code.",
        "experience_years": 7,
        "location": "Seattle, WA",
        "github_url": "https://github.com/davidkim",
    },
    {
        "name": "Eva Patel",
        "title": "Mobile Developer",
        "skills": ["Flutter", "Dart", "Firebase", "Android", "iOS"],
        "bio": "Eva builds cross-platform mobile apps that feel native on every device.",
        "experience_years": 3,
        "location": "Chicago, IL",
        "portfolio_url": "https://evapatel.io",
        "github_url": "https://github.com/evapatel",
    },
]


def seed():
    with app.app_context():
        db.create_all()

        # ── Admin user ────────────────────────────────────────────────────────
        if not User.query.filter_by(email="admin@talent.com").first():
            admin = User(
                username="admin",
                email="admin@talent.com",
                role=UserRole.ADMIN,   # Fix #11 — use enum
            )
            admin.set_password("Admin1234")
            db.session.add(admin)
            db.session.flush()

            admin_profile = TalentProfile(
                user_id=admin.id,
                full_name="Portal Admin",
                title="Platform Administrator",
                bio="I manage the TalentPortal platform and ensure everything runs smoothly.",
                experience_years=8,
                location="Remote",
                is_public=True,
            )
            db.session.add(admin_profile)
            db.session.flush()
            admin_profile.set_skills_from_list(["Flask", "PostgreSQL", "Python", "DevOps"])
            print("✓ Admin created: admin@talent.com / Admin1234")

        # ── Sample talent users ───────────────────────────────────────────────
        for i, talent in enumerate(SAMPLE_TALENTS, start=1):
            email = f"talent{i}@example.com"
            if not User.query.filter_by(email=email).first():
                user = User(username=f"talent{i}", email=email, role=UserRole.USER)
                user.set_password("Talent1234")
                db.session.add(user)
                db.session.flush()

                profile = TalentProfile(
                    user_id=user.id,
                    full_name=talent["name"],
                    title=talent["title"],
                    bio=talent["bio"],
                    experience_years=talent["experience_years"],
                    location=talent["location"],
                    portfolio_url=talent.get("portfolio_url"),
                    github_url=talent.get("github_url"),
                    linkedin_url=talent.get("linkedin_url"),
                    is_public=True,
                )
                db.session.add(profile)
                db.session.flush()
                # Fix #1 — set skills via M2M helper
                profile.set_skills_from_list(talent["skills"])
                print(f"✓ Created: {talent['name']} ({email})")

        db.session.commit()
        print("\n── Seeding complete! ─────────────────────────────────")
        print("  Admin login : admin@talent.com / Admin1234")
        print("  Sample login: talent1@example.com / Talent1234")


if __name__ == "__main__":
    seed()
