import logging
from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app import db
from app.models import User, TalentProfile

logger = logging.getLogger(__name__)
admin_bp = Blueprint("admin", __name__)


def admin_required(f):
    
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_admin: # is_admin comes from User model property
            abort(403)
        return f(*args, **kwargs)
    return decorated


#  Admin Dashboard 

@admin_bp.route("/")
@admin_required
def admin_dashboard():
    total_users = User.query.count()
    total_profiles = TalentProfile.query.count()

    page = request.args.get("page", 1, type=int)
    pagination = (
        User.query
        .order_by(User.created_at.desc())
        .paginate(page=page, per_page=15, error_out=False) #15 users per page in descending order so that latest can be shown
    )
    return render_template(
        "admin/dashboard.html",
        total_users=total_users,
        total_profiles=total_profiles,
        recent_users=pagination.items,
        pagination=pagination,
    )


#  User Management 

@admin_bp.route("/users")
@admin_required
def list_users():
    page = request.args.get("page", 1, type=int)
    search = request.args.get("q", "").strip()
    query = User.query
    if search:
        like = f"%{search}%" #for wildcard matching
        query = query.filter(
            db.or_(User.username.ilike(like), User.email.ilike(like)) #ilike is case insesitive search
        ) #db.or_ is match either condition either mail or name
    pagination = query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    return render_template(
        "admin/users.html",
        users=pagination.items,
        pagination=pagination,
        search=search,
    )


@admin_bp.route("/users/<int:user_id>/toggle-active", methods=["POST"]) #turn user account on or off
@admin_required
def toggle_user_active(user_id: int):
    user = db.session.get(User, user_id) #fetch user by primary key
    if not user:
        abort(404)
    if user.id == current_user.id:
        flash("You cannot deactivate your own account.", "warning") #since current user is admin and the user that is to be deactivated also admin not possible
        return redirect(url_for("admin.list_users"))
    user.is_active = not user.is_active
    db.session.commit()
    state = "activated" if user.is_active else "deactivated"
    logger.info("Admin %s %s user %s", current_user.username, state, user.username)
    flash(f"User {user.username} has been {state}.", "success")
    return redirect(url_for("admin.list_users"))


@admin_bp.route("/users/<int:user_id>/toggle-role", methods=["POST"]) #chage user role from admin to user
@admin_required
def toggle_user_role(user_id: int):
    from app.models import UserRole #import userrole which shows either admin or user
    user = db.session.get(User, user_id)
    if not user:
        abort(404)
    if user.id == current_user.id:
        flash("You cannot change your own role.", "warning")
        return redirect(url_for("admin.list_users"))
    user.role = UserRole.ADMIN if user.role == UserRole.USER else UserRole.USER
    db.session.commit()
    logger.info("Admin %s changed role of %s to %s", current_user.username, user.username, user.role)
    flash(f"User {user.username} is now a {user.role.value}.", "success")
    return redirect(url_for("admin.list_users"))


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"]) #to delete the user profile
@admin_required
def delete_user(user_id: int):
    user = db.session.get(User, user_id)
    if not user:
        abort(404)
    if user.id == current_user.id:
        flash("You cannot delete your own account.", "danger")
        return redirect(url_for("admin.list_users"))
    username = user.username
    db.session.delete(user)
    db.session.commit()
    logger.info("Admin %s deleted user %s", current_user.username, username)
    flash(f"User {username} deleted.", "success")
    return redirect(url_for("admin.list_users"))


#  Profile Management 

@admin_bp.route("/profiles")
@admin_required
def list_profiles():
    page = request.args.get("page", 1, type=int)
    search = request.args.get("q", "").strip()
    from app.models import Skill
    query = TalentProfile.query.join(User)# each profile belongs to a user, so this join allows to access via username
    if search:
        like = f"%{search}%"
        query = (
            query
            .outerjoin(TalentProfile.skills) #join skills to talent  profile, outerjoin shows user without skills too
            .filter(db.or_(
                TalentProfile.full_name.ilike(like),
                User.username.ilike(like),
                Skill.name.ilike(like),   
            ))
            .distinct() #removes duplicates otherwise there could be duplicate rows due to matching skills
        )
    pagination = query.order_by(TalentProfile.updated_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    return render_template(
        "admin/profiles.html",
        profiles=pagination.items,
        pagination=pagination,
        search=search,
    )


@admin_bp.route("/profiles/<int:profile_id>/toggle-public", methods=["POST"])
@admin_required
def toggle_profile_public(profile_id: int):
    profile = db.session.get(TalentProfile, profile_id)
    if not profile:
        abort(404)
    profile.is_public = not profile.is_public
    db.session.commit()
    state = "public" if profile.is_public else "private"
    flash(f"Profile for {profile.full_name} is now {state}.", "success")
    return redirect(url_for("admin.list_profiles"))


@admin_bp.route("/profiles/<int:profile_id>/delete", methods=["POST"])
@admin_required
def delete_profile(profile_id: int):
    profile = db.session.get(TalentProfile, profile_id)
    if not profile:
        abort(404)
    
    if profile.user_id == current_user.id:
        flash(
            "You cannot delete your own profile as an admin. "
            "Transfer admin rights to another user first.",
            "danger",
        )
        return redirect(url_for("admin.list_profiles"))
    name = profile.full_name
    db.session.delete(profile)
    db.session.commit()
    logger.info("Admin %s deleted profile for %s", current_user.username, name)
    flash(f"Profile for {name} deleted.", "success")
    return redirect(url_for("admin.list_profiles"))
