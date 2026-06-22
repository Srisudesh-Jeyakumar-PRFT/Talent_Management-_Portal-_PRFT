#for external/programmatic access, reuse, integration, and also testing not directly a impact in our ui i built it to resue and test my logical ability.
import logging
from functools import wraps
from flask import Blueprint, jsonify, request, current_app
from app.models import TalentProfile, Skill, User
from app.utils import build_profile_search_query
from app import db, csrf

logger = logging.getLogger(__name__)
api_bp = Blueprint("api", __name__)


def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        key = request.headers.get("X-API-Key", "")
        if not key or key != current_app.config.get("API_SECRET_KEY", ""):
            logger.warning("Rejected API request — bad or missing X-API-Key from %s", request.remote_addr)
            return jsonify({"error": "Unauthorized. Provide a valid X-API-Key header."}), 401
        return f(*args, **kwargs)
    return decorated


@api_bp.before_request
def exempt_csrf():
    pass


#  GET to see all talents

@api_bp.route("/talents", methods=["GET"])
@require_api_key
def list_talents():
    page = request.args.get("page", 1, type=int)
    limit = min(request.args.get("limit", 12, type=int), 50)
    search = request.args.get("q", "").strip()

    query = build_profile_search_query(search)
    pagination = query.order_by(TalentProfile.updated_at.desc()).paginate(
        page=page, per_page=limit, error_out=False
    )

    return jsonify({
        "page": pagination.page,
        "pages": pagination.pages,
        "total": pagination.total,
        "per_page": pagination.per_page,
        "has_next": pagination.has_next,
        "has_prev": pagination.has_prev,
        "results": [p.to_dict() for p in pagination.items],
    })


#  GET see one talent skill per user id 

@api_bp.route("/talents/<int:user_id>", methods=["GET"])
@require_api_key
def get_talent(user_id: int):
    user = db.session.get(User, user_id)
    if not user or not user.profile or not user.profile.is_public:
        return jsonify({"error": "Profile not found or is private."}), 404
    return jsonify(user.profile.to_dict())


#  GET see all skills per user from talent profile

@api_bp.route("/skills", methods=["GET"])
@require_api_key
def list_skills():
    
    skills = (
        db.session.query(Skill.name)
        .join(Skill.profiles)                          # join via M2M
        .filter(TalentProfile.is_public == True)       # noqa: E712
        .distinct()
        .order_by(Skill.name)
        .all()
    )
    return jsonify([s.name for s in skills])
