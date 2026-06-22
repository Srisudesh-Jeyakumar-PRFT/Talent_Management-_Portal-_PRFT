"""
Shared utilities used across multiple blueprints.
"""
import logging
from urllib.parse import urlparse, urljoin
from flask import request
from app import db
from app.models import TalentProfile, Skill, User

logger = logging.getLogger(__name__)


# ── Fix #2: Safe redirect helper ──────────────────────────────────────────────

def is_safe_url(target: str) -> bool:
    """
    Verify that a redirect target stays on the same host.
    Prevents open-redirect attacks via the ?next= parameter.
    """
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return (
        test_url.scheme in ("http", "https")
        and ref_url.netloc == test_url.netloc
    )


# ── Fix #6: Shared profile search query builder ───────────────────────────────

def build_profile_search_query(search: str):
    
    query = TalentProfile.query.filter_by(is_public=True)

    if search:
        like = f"%{search}%"
        # Join User for username search, join skills M2M for exact skill matching
        query = (
            query
            .join(User, TalentProfile.user_id == User.id)
            .outerjoin(TalentProfile.skills)
            .filter(
                db.or_(
                    TalentProfile.full_name.ilike(like),
                    TalentProfile.title.ilike(like),
                    User.username.ilike(like),
                    Skill.name.ilike(like),   # Fix #20: searches the skills table, not a text blob
                )
            )
            .distinct()   # outerjoin can produce duplicate rows
        )

    return query
