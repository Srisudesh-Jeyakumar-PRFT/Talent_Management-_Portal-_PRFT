import logging
from flask import Blueprint, render_template, redirect, url_for, request, abort
from flask_login import login_required, current_user
from app.models import TalentProfile, User
from app.utils import build_profile_search_query  # Fix #6
from app import db

logger = logging.getLogger(__name__)
main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    #Public landing / talent browse page.
    page = request.args.get("page", 1, type=int)
    search = request.args.get("q", "").strip()

    query = build_profile_search_query(search)
    pagination = query.order_by(TalentProfile.updated_at.desc()).paginate(
        page=page, per_page=12, error_out=False
    )

    return render_template(
        "main/index.html",
        profiles=pagination.items,
        pagination=pagination,
        search=search,
    )


@main_bp.route("/dashboard")
@login_required
def dashboard():
    """Post-login dashboard."""
    profile = current_user.profile
    total_public = TalentProfile.query.filter_by(is_public=True).count()
    return render_template(
        "main/dashboard.html",
        profile=profile,
        total_public=total_public,
    )


@main_bp.route("/talent/<int:user_id>")
def view_talent(user_id: int):
    """Public view of a single talent profile."""
    user = db.session.get(User, user_id)
    if not user:
        abort(404)

    profile = user.profile
    if not profile:
        abort(404)

    if not profile.is_public:
        if not current_user.is_authenticated:
            abort(404)   # 404 not 403 — don't reveal that the profile exists
        if current_user.id != user_id and not current_user.is_admin:
            abort(404)

    return render_template("main/talent_detail.html", profile=profile, talent_user=user)
