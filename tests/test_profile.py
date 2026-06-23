import io
from pathlib import Path

from werkzeug.datastructures import MultiDict

from app import db
from app.models import Education, Experience, TalentProfile, User, UserRole
from app.routes.profile import (
    _allowed_file,
    _parse_education_from_form,
    _parse_experience_from_form,
)


def login(client, email, password="Password1"):
    response = client.post(
        "/auth/login",
        data={"email": email, "password": password},
        follow_redirects=False,
    )
    assert response.status_code == 302
    return response


def create_user(app, username, email, role=UserRole.USER):
    with app.app_context():
        user = User(username=username, email=email, role=role)
        user.set_password("Password1")
        db.session.add(user)
        db.session.commit()
        return user.id


def create_profile(app, user_id, **overrides):
    defaults = {
        "full_name": "Jane Doe",
        "title": "Engineer",
        "bio": "Builds reliable systems.",
        "experience_years": 5,
        "location": "Chennai",
        "portfolio_url": "https://portfolio.example.com",
        "github_url": "https://github.com/janedoe",
        "linkedin_url": "https://linkedin.com/in/janedoe",
        "is_public": True,
    }
    defaults.update(overrides)

    with app.app_context():
        profile = TalentProfile(user_id=user_id, **defaults)
        db.session.add(profile)
        db.session.commit()
        return profile.id


def test_allowed_file_accepts_expected_extensions_and_rejects_invalid_names():
    assert _allowed_file("avatar.png") is True
    assert _allowed_file("avatar.JPEG") is True
    assert _allowed_file("avatar.webp") is True
    assert _allowed_file("avatar") is False
    assert _allowed_file("avatar.exe") is False
    assert _allowed_file(".bashrc") is False


def test_parse_experience_from_form_skips_incomplete_rows_and_preserves_order():
    form = MultiDict(
        {
            "exp_company_0": "Acme Corp",
            "exp_title_0": "Developer",
            "exp_start_0": "2020",
            "exp_end_0": "2022",
            "exp_desc_0": "Built APIs",
            "exp_title_1": "Missing company should be skipped",
            "exp_company_2": "Beta LLC",
            "exp_title_2": "Lead Engineer",
            "exp_start_2": "2022",
            "exp_current_2": "on",
            "exp_desc_2": "Owns platform",
        }
    )

    entries = _parse_experience_from_form(form)

    assert len(entries) == 2
    assert entries[0]["company"] == "Acme Corp"
    assert entries[0]["order"] == 0
    assert entries[1]["company"] == "Beta LLC"
    assert entries[1]["is_current"] is True
    assert entries[1]["end_date"] == ""
    assert entries[1]["order"] == 2


def test_parse_education_from_form_skips_blank_rows_and_preserves_order():
    form = MultiDict(
        {
            "edu_institution_0": "State University",
            "edu_degree_0": "B.Tech",
            "edu_field_0": "Computer Science",
            "edu_start_year_0": "2015",
            "edu_end_year_0": "2019",
            "edu_degree_1": "Missing institution should be skipped",
            "edu_institution_2": "Tech Institute",
            "edu_degree_2": "M.S.",
            "edu_start_year_2": "2020",
        }
    )

    entries = _parse_education_from_form(form)

    assert len(entries) == 2
    assert entries[0]["institution"] == "State University"
    assert entries[0]["order"] == 0
    assert entries[1]["institution"] == "Tech Institute"
    assert entries[1]["degree"] == "M.S."
    assert entries[1]["order"] == 2


def test_profile_routes_require_login(client):
    response = client.get("/profile/me", follow_redirects=False)

    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_edit_profile_get_prefills_existing_profile(app, logged_in_client, user):
    create_profile(app, user.id, full_name="Alex Example")

    with app.app_context():
        profile = TalentProfile.query.filter_by(user_id=user.id).first()
        profile.set_skills_from_list(["Flask", "Python"])
        profile.experiences.append(
            Experience(
                company="Acme",
                job_title="Developer",
                start_date="2020",
                end_date="2023",
                description="Delivered features",
                order=0,
            )
        )
        profile.educations.append(
            Education(
                institution="State University",
                degree="B.Tech",
                field="CSE",
                start_year="2012",
                end_year="2016",
                order=0,
            )
        )
        db.session.commit()

    response = logged_in_client.get("/profile/edit")

    assert response.status_code == 200
    assert b"Alex Example" in response.data
    assert b"Flask, Python" in response.data or b"Python, Flask" in response.data
    assert b"Acme" in response.data
    assert b"State University" in response.data


def test_edit_profile_post_creates_profile_with_related_records(app, logged_in_client, user):
    response = logged_in_client.post(
        "/profile/edit",
        data={
            "full_name": "  Jane Smith  ",
            "title": "Senior Python Developer",
            "bio": " Builds APIs and internal platforms. ",
            "skills": "Python, Flask, SQLAlchemy",
            "experience_years": "7",
            "location": "Bengaluru",
            "portfolio_url": "https://portfolio.example.com",
            "github_url": "https://github.com/janesmith",
            "linkedin_url": "https://linkedin.com/in/janesmith",
            "is_public": "on",
            "exp_company_0": "Acme Corp",
            "exp_title_0": "Engineer",
            "exp_start_0": "2019",
            "exp_end_0": "2022",
            "exp_desc_0": "Built services",
            "edu_institution_0": "State University",
            "edu_degree_0": "B.Tech",
            "edu_field_0": "Computer Science",
            "edu_start_year_0": "2011",
            "edu_end_year_0": "2015",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/profile/me")

    with app.app_context():
        profile = TalentProfile.query.filter_by(user_id=user.id).first()
        assert profile is not None
        assert profile.full_name == "Jane Smith"
        assert profile.bio == "Builds APIs and internal platforms."
        assert profile.experience_years == 7
        assert profile.location == "Bengaluru"
        assert profile.is_public is True
        assert profile.skills_list == ["Flask", "Python", "SQLAlchemy"]

        experiences = Experience.query.filter_by(profile_id=profile.id).order_by(Experience.order).all()
        educations = Education.query.filter_by(profile_id=profile.id).order_by(Education.order).all()
        assert len(experiences) == 1
        assert experiences[0].company == "Acme Corp"
        assert experiences[0].job_title == "Engineer"
        assert len(educations) == 1
        assert educations[0].institution == "State University"


def test_edit_profile_post_replaces_existing_related_rows(app, logged_in_client, user):
    create_profile(app, user.id, full_name="Jane Doe")

    with app.app_context():
        profile = TalentProfile.query.filter_by(user_id=user.id).first()
        profile.experiences.extend(
            [
                Experience(
                    company="Old Company",
                    job_title="Old Role",
                    start_date="2018",
                    end_date="2019",
                    description="Old work",
                    order=0,
                ),
                Experience(
                    company="Another Old Company",
                    job_title="Another Role",
                    start_date="2019",
                    end_date="2020",
                    description="More old work",
                    order=1,
                ),
            ]
        )
        profile.educations.append(
            Education(
                institution="Old College",
                degree="B.Sc",
                field="Math",
                start_year="2010",
                end_year="2013",
                order=0,
            )
        )
        db.session.commit()

    response = logged_in_client.post(
        "/profile/edit",
        data={
            "full_name": "Jane Doe",
            "title": "Staff Engineer",
            "bio": "Updated bio",
            "skills": "Python, Leadership",
            "experience_years": "10",
            "location": "Pune",
            "portfolio_url": "https://portfolio.example.com",
            "github_url": "https://github.com/janedoe",
            "linkedin_url": "https://linkedin.com/in/janedoe",
            "exp_company_0": "New Company",
            "exp_title_0": "Principal Engineer",
            "exp_start_0": "2021",
            "exp_end_0": "",
            "exp_current_0": "on",
            "exp_desc_0": "Leads architecture",
            "edu_institution_0": "New University",
            "edu_degree_0": "M.Tech",
            "edu_field_0": "Software Engineering",
            "edu_start_year_0": "2014",
            "edu_end_year_0": "2016",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302

    with app.app_context():
        profile = TalentProfile.query.filter_by(user_id=user.id).first()
        experiences = Experience.query.filter_by(profile_id=profile.id).order_by(Experience.order).all()
        educations = Education.query.filter_by(profile_id=profile.id).order_by(Education.order).all()

        assert len(experiences) == 1
        assert experiences[0].company == "New Company"
        assert experiences[0].job_title == "Principal Engineer"
        assert experiences[0].is_current is True
        assert experiences[0].end_date is None
        assert len(educations) == 1
        assert educations[0].institution == "New University"
        assert Experience.query.filter_by(profile_id=profile.id, company="Old Company").count() == 0
        assert Education.query.filter_by(profile_id=profile.id, institution="Old College").count() == 0


def test_edit_profile_validation_error_preserves_dynamic_rows(app, logged_in_client, user):
    response = logged_in_client.post(
        "/profile/edit",
        data={
            "full_name": "A",
            "title": "Engineer",
            "bio": "Short bio",
            "skills": "Python",
            "experience_years": "abc",
            "location": "Remote",
            "portfolio_url": "https://portfolio.example.com",
            "github_url": "https://github.com/example",
            "linkedin_url": "https://linkedin.com/in/example",
            "exp_company_0": "Acme Corp",
            "exp_title_0": "Engineer",
            "exp_start_0": "2021",
            "edu_institution_0": "State University",
            "edu_degree_0": "B.Tech",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"full name: Full name must be at least 2 characters." in response.data
    assert b"experience_years: Experience years must be a whole number." in response.data
    assert b"Acme Corp" in response.data
    assert b"State University" in response.data

    with app.app_context():
        assert TalentProfile.query.filter_by(user_id=user.id).first() is None


def test_edit_profile_invalid_photo_extension_does_not_commit(logged_in_client, monkeypatch):
    def fail_commit():
        raise AssertionError("commit should not be called when photo validation fails")

    monkeypatch.setattr(db.session, "commit", fail_commit)

    response = logged_in_client.post(
        "/profile/edit",
        data={
            "full_name": "Jane Smith",
            "title": "Engineer",
            "skills": "Python",
            "photo": (io.BytesIO(b"not-an-image"), "avatar.txt"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"photo: File type not allowed" in response.data


def test_edit_profile_photo_processing_failure_shows_error_and_skips_commit(logged_in_client, monkeypatch):
    def fail_commit():
        raise AssertionError("commit should not be called when photo processing fails")

    monkeypatch.setattr(db.session, "commit", fail_commit)
    monkeypatch.setattr("app.routes.profile._save_photo", lambda photo, user_id: (_ for _ in ()).throw(ValueError("bad image")))

    response = logged_in_client.post(
        "/profile/edit",
        data={
            "full_name": "Jane Smith",
            "title": "Engineer",
            "skills": "Python",
            "photo": (io.BytesIO(b"fake-png"), "avatar.png"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"photo: Could not process image" in response.data
    assert b"bad image" in response.data


def test_edit_profile_db_commit_failure_rolls_back(app, logged_in_client, user, monkeypatch):
    monkeypatch.setattr(db.session, "commit", lambda: (_ for _ in ()).throw(RuntimeError("db unavailable")))

    response = logged_in_client.post(
        "/profile/edit",
        data={
            "full_name": "Jane Smith",
            "title": "Engineer",
            "skills": "Python",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"A database error occurred. Please try again." in response.data

    with app.app_context():
        assert TalentProfile.query.filter_by(user_id=user.id).first() is None


def test_delete_photo_removes_file_and_clears_db_state(app, logged_in_client, user):
    create_profile(app, user.id, photo_filename="avatar.png")

    upload_path = Path(app.config["UPLOAD_FOLDER"]) / "avatar.png"
    upload_path.write_bytes(b"image-bytes")

    response = logged_in_client.post("/profile/delete-photo", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/profile/edit")
    assert upload_path.exists() is False

    with app.app_context():
        profile = TalentProfile.query.filter_by(user_id=user.id).first()
        assert profile.photo_filename is None


def test_download_pdf_returns_404_when_user_has_no_profile(app, client, user):
    response = client.get(f"/profile/{user.id}/pdf", follow_redirects=False)

    assert response.status_code == 404


def test_download_pdf_blocks_anonymous_access_to_private_profile(app, client, user):
    create_profile(app, user.id, full_name="Private User", is_public=False)

    response = client.get(f"/profile/{user.id}/pdf", follow_redirects=False)

    assert response.status_code == 403


def test_download_pdf_blocks_other_non_admin_user_for_private_profile(app, client, user):
    create_profile(app, user.id, full_name="Private User", is_public=False)
    other_user_id = create_user(app, "otheruser", "other@example.com")
    assert other_user_id != user.id

    login(client, "other@example.com")
    response = client.get(f"/profile/{user.id}/pdf", follow_redirects=False)

    assert response.status_code == 403


def test_download_pdf_allows_owner_for_private_profile(app, logged_in_client, user, monkeypatch):
    create_profile(app, user.id, full_name="Jane Smith", is_public=False)
    monkeypatch.setattr("app.routes.profile.generate_profile_pdf", lambda profile, target_user: b"%PDF-test")

    response = logged_in_client.get(f"/profile/{user.id}/pdf", follow_redirects=False)

    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.data == b"%PDF-test"
    assert "Jane_Smith_profile.pdf" in response.headers["Content-Disposition"]


def test_download_pdf_allows_admin_for_private_profile(app, client, user, monkeypatch):
    create_profile(app, user.id, full_name="Jane Smith", is_public=False)
    create_user(app, "adminuser", "admin@example.com", role=UserRole.ADMIN)
    monkeypatch.setattr("app.routes.profile.generate_profile_pdf", lambda profile, target_user: b"%PDF-admin")

    login(client, "admin@example.com")
    response = client.get(f"/profile/{user.id}/pdf", follow_redirects=False)

    assert response.status_code == 200
    assert response.data == b"%PDF-admin"
