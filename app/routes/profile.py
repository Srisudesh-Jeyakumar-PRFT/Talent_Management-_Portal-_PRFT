import io
import logging
import os
import shutil
import tempfile

from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request, current_app, send_file, abort,
)
from flask_login import login_required, current_user
from pydantic import ValidationError
from werkzeug.utils import secure_filename
from PIL import Image

from app import db
from app.models import TalentProfile, User, Experience, Education
from app.validators import ProfileSchema, collect_pydantic_errors
from app.services.pdf_service import generate_profile_pdf

logger = logging.getLogger(__name__)
profile_bp = Blueprint("profile", __name__)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}


def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _save_photo(file, user_id: int) -> str:
    ext = file.filename.rsplit(".", 1)[1].lower()
    final_filename = secure_filename(f"user_{user_id}_photo.{ext}")
    upload_dir = current_app.config["UPLOAD_FOLDER"]
    final_path = os.path.join(upload_dir, final_filename)

    img = Image.open(file)
    img.verify()
    file.seek(0)
    img = Image.open(file)
    img.thumbnail((400, 400))

    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    tmp_fd, tmp_path = tempfile.mkstemp(suffix=f".{ext}", dir=upload_dir)
    try:
        os.close(tmp_fd)
        img.save(tmp_path, optimize=True, quality=85)
        shutil.move(tmp_path, final_path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise

    return final_filename


def _parse_experience_from_form(form) -> list[dict]:
    """
    Reads repeating experience fields from the POST form.
    Fields are named: exp_company_0, exp_title_0, exp_start_0, etc.
    Returns a list of dicts, one per entry, in submitted order.
    """
    entries = []
    idx = 0
    while True:
        company = form.get(f"exp_company_{idx}", "").strip()
        if not company:
            # Stop when we run out of entries (no company = empty row)
            if form.get(f"exp_title_{idx}") is None:
                break
            idx += 1
            continue
        entries.append({
            "company":    company,
            "job_title":  form.get(f"exp_title_{idx}", "").strip(),
            "start_date": form.get(f"exp_start_{idx}", "").strip(),
            "end_date":   form.get(f"exp_end_{idx}", "").strip(),
            "is_current": form.get(f"exp_current_{idx}") == "on",
            "description": form.get(f"exp_desc_{idx}", "").strip(),
            "order":      idx,
        })
        idx += 1
    return entries


def _parse_education_from_form(form) -> list[dict]:
    """
    Reads repeating education fields from the POST form.
    Fields are named: edu_institution_0, edu_degree_0, etc.
    """
    entries = []
    idx = 0
    while True:
        institution = form.get(f"edu_institution_{idx}", "").strip()
        if not institution:
            if form.get(f"edu_degree_{idx}") is None:
                break
            idx += 1
            continue
        entries.append({
            "institution": institution,
            "degree":      form.get(f"edu_degree_{idx}", "").strip(),
            "field":       form.get(f"edu_field_{idx}", "").strip(),
            "start_year":  form.get(f"edu_start_year_{idx}", "").strip(),
            "end_year":    form.get(f"edu_end_year_{idx}", "").strip(),
            "order":       idx,
        })
        idx += 1
    return entries


def _save_experiences(profile, exp_data: list[dict]):
    """Replace all experience rows for this profile."""
    Experience.query.filter_by(profile_id=profile.id).delete()
    for data in exp_data:
        exp = Experience(
            profile_id  = profile.id,
            company     = data["company"],
            job_title   = data["job_title"],
            start_date  = data["start_date"],
            end_date    = data["end_date"] if not data["is_current"] else None,
            is_current  = data["is_current"],
            description = data["description"],
            order       = data["order"],
        )
        db.session.add(exp)


def _save_educations(profile, edu_data: list[dict]):
    """Replace all education rows for this profile."""
    Education.query.filter_by(profile_id=profile.id).delete()
    for data in edu_data:
        edu = Education(
            profile_id  = profile.id,
            institution = data["institution"],
            degree      = data["degree"],
            field       = data["field"],
            start_year  = data["start_year"],
            end_year    = data["end_year"],
            order       = data["order"],
        )
        db.session.add(edu)


#  View own profile 

@profile_bp.route("/me")
@login_required
def my_profile():
    profile = current_user.profile
    return render_template("profile/view.html", profile=profile, owner=True)


#  Create / Edit Profile 

@profile_bp.route("/edit", methods=["GET", "POST"])
@login_required
def edit_profile():
    profile = current_user.profile
    errors = []
    form_data = {}

    if request.method == "POST":
        form_data = {
            "full_name":      request.form.get("full_name", "").strip(),
            "title":          request.form.get("title", "").strip(),
            "bio":            request.form.get("bio", "").strip(),
            "skills_raw":     request.form.get("skills", "").strip(),
            "experience_years": request.form.get("experience_years", "").strip() or None,
            "location":       request.form.get("location", "").strip(),
            "portfolio_url":  request.form.get("portfolio_url", "").strip(),
            "github_url":     request.form.get("github_url", "").strip(),
            "linkedin_url":   request.form.get("linkedin_url", "").strip(),
            "is_public":      request.form.get("is_public") == "on",
        }

        exp_data = _parse_experience_from_form(request.form)
        edu_data = _parse_education_from_form(request.form)

        try:
            validated = ProfileSchema(**form_data)

            if profile is None:
                
                profile = TalentProfile(
                    user_id   = current_user.id,
                    full_name = validated.full_name,
                    title     = validated.title,
                    bio       = validated.bio,
                    experience_years = validated.experience_years,
                    location  = validated.location,
                    portfolio_url = validated.portfolio_url,
                    github_url    = validated.github_url,
                    linkedin_url  = validated.linkedin_url,
                    is_public     = validated.is_public,
                )
                db.session.add(profile)
                db.session.flush()  
            else:
                profile.full_name        = validated.full_name
                profile.title            = validated.title
                profile.bio              = validated.bio
                profile.experience_years = validated.experience_years
                profile.location         = validated.location
                profile.portfolio_url    = validated.portfolio_url
                profile.github_url       = validated.github_url
                profile.linkedin_url     = validated.linkedin_url
                profile.is_public        = validated.is_public

            profile.set_skills_from_list(validated.skills_list)

            _save_experiences(profile, exp_data)
            _save_educations(profile, edu_data)

            # Handle photo upload
            photo = request.files.get("photo")
            if photo and photo.filename:
                if not _allowed_file(photo.filename):
                    errors.append("photo: File type not allowed. Use PNG, JPG, GIF or WebP.")
                else:
                    try:
                        filename = _save_photo(photo, current_user.id)
                        profile.photo_filename = filename
                    except Exception as exc:
                        logger.exception("Photo save failed for user %s", current_user.id)
                        errors.append(f"photo: Could not process image – {exc}")

            if not errors:
                try:
                    db.session.commit()
                    flash("Profile updated successfully!", "success")
                    return redirect(url_for("profile.my_profile"))
                except Exception:
                    db.session.rollback()
                    logger.exception("DB commit failed during profile save")
                    errors.append("form: A database error occurred. Please try again.")

            form_data["_experiences"] = exp_data
            form_data["_educations"]  = edu_data

        except ValidationError as e:
            errors = collect_pydantic_errors(e)
            form_data["_experiences"] = exp_data
            form_data["_educations"]  = edu_data

    else:
        if profile:
            form_data = {
                "full_name":       profile.full_name or "",
                "title":           profile.title or "",
                "bio":             profile.bio or "",
                "skills":          ", ".join(profile.skills_list),
                "experience_years": profile.experience_years if profile.experience_years is not None else "",
                "location":        profile.location or "",
                "portfolio_url":   profile.portfolio_url or "",
                "github_url":      profile.github_url or "",
                "linkedin_url":    profile.linkedin_url or "",
                "is_public":       profile.is_public,
                "_experiences": [
                    {
                        "company":    e.company,
                        "job_title":  e.job_title,
                        "start_date": e.start_date,
                        "end_date":   e.end_date or "",
                        "is_current": e.is_current,
                        "description": e.description or "",
                    }
                    for e in profile.experiences
                ],
                "_educations": [
                    {
                        "institution": e.institution,
                        "degree":      e.degree,
                        "field":       e.field or "",
                        "start_year":  e.start_year or "",
                        "end_year":    e.end_year or "",
                    }
                    for e in profile.educations
                ],
            }

    return render_template(
        "profile/edit.html",
        errors=errors,
        form_data=form_data,
        profile=profile,
    )


#  Delete Profile Photo 

@profile_bp.route("/delete-photo", methods=["POST"])
@login_required
def delete_photo():
    profile = current_user.profile
    if profile and profile.photo_filename:
        path = os.path.join(current_app.config["UPLOAD_FOLDER"], profile.photo_filename)
        if os.path.exists(path):
            os.remove(path)
        profile.photo_filename = None
        db.session.commit()
        flash("Profile photo removed.", "info")
    return redirect(url_for("profile.edit_profile"))


#  Export Profile as PDF 

@profile_bp.route("/<int:user_id>/pdf")
def download_pdf(user_id: int):
    user = db.session.get(User, user_id)
    if not user:
        abort(404)

    profile = user.profile
    if not profile:
        abort(404)

    if not profile.is_public:
        if not current_user.is_authenticated:
            abort(403)
        if current_user.id != user_id and not current_user.is_admin:
            abort(403)

    pdf_bytes = generate_profile_pdf(profile, user)
    safe_name = profile.full_name.replace(" ", "_")
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"{safe_name}_profile.pdf",
    )