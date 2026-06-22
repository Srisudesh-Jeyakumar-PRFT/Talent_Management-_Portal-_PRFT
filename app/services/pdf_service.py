

import io
import logging
import os
import urllib.request

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer,
    HRFlowable, Table, TableStyle, KeepTogether, Image,
)

logger = logging.getLogger(__name__)

#  Font 
def _ensure_franklin_gothic():
    path = (
        "C:/Users/srisudesh.jeyakumar/OneDrive - Perficient, Inc"
        "/Desktop/talent management portal/app/images"
        "/Franklin Gothic Demi Cond Regular.ttf"
    )
    if not os.path.exists(path):
        fallback = "/tmp/FranklinGothicDemiCond.ttf"
        if not os.path.exists(fallback):
            urllib.request.urlretrieve(
                "https://github.com/liberationfonts/liberation-fonts"
                "/raw/main/src/LiberationSansNarrow-Bold.ttf",
                fallback,
            )
        path = fallback
    pdfmetrics.registerFont(TTFont("FranklinGothicDemiCond", path))
    pdfmetrics.registerFontFamily(
        "FranklinGothicDemiCond",
        normal="FranklinGothicDemiCond",
        bold="FranklinGothicDemiCond",
        italic="FranklinGothicDemiCond",
        boldItalic="FranklinGothicDemiCond",
    )

_ensure_franklin_gothic()

#  Colours 
TEAL       = colors.HexColor("#075056")
RED        = colors.HexColor("#CC1F20")
NEAR_BLACK = colors.HexColor("#010101")
LIGHT_GREY = colors.HexColor("#F2F2F2")
MID_GREY   = colors.HexColor("#707170")
BODY_GREY  = colors.HexColor("#333333")

PAGE_W, PAGE_H = letter
MARGIN    = 1 * inch
CONTENT_W = PAGE_W - 2 * MARGIN

LOGO_PATH = (
    "C:/Users/srisudesh.jeyakumar/OneDrive - Perficient, Inc"
    "/Desktop/talent management portal/app/images"
    "/Logo_Perficient_Full-Color.png"
)


def _build_styles():
    base = getSampleStyleSheet()
    FG = "FranklinGothicDemiCond"
    return dict(
        name=ParagraphStyle("Name", parent=base["Normal"],
            fontName=FG, fontSize=18, leading=22, textColor=TEAL, spaceAfter=2),
        title=ParagraphStyle("JobTitle", parent=base["Normal"],
            fontName=FG, fontSize=11, leading=14, textColor=BODY_GREY, spaceAfter=0),
        section=ParagraphStyle("SectionHeader", parent=base["Normal"],
            fontName=FG, fontSize=14, leading=18, textColor=TEAL,
            spaceBefore=14, spaceAfter=4),
        employer=ParagraphStyle("Employer", parent=base["Normal"],
            fontName=FG, fontSize=11, leading=14, textColor=NEAR_BLACK,
            spaceBefore=8, spaceAfter=2),
        label=ParagraphStyle("Label", parent=base["Normal"],
            fontName=FG, fontSize=10, leading=13, textColor=RED),
        body=ParagraphStyle("Body", parent=base["Normal"],
            fontName=FG, fontSize=10, leading=14, textColor=BODY_GREY),
        footer=ParagraphStyle("Footer", parent=base["Normal"],
            fontName=FG, fontSize=8, leading=10, textColor=MID_GREY),
        meta_label=ParagraphStyle("MetaLabel", parent=base["Normal"],
            fontName=FG, fontSize=10, leading=13, textColor=TEAL),
    )


def _divider(story):
    story.append(HRFlowable(width="100%", thickness=1.5, color=TEAL, spaceAfter=6))


def _grey_table(rows, col_widths):
    tbl = Table(rows, colWidths=col_widths)
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), LIGHT_GREY),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("LINEBELOW",     (0, 0), (-1, -1), 0.5, colors.white),
    ]))
    return tbl


def _safe(text):
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")


def generate_profile_pdf(profile, user) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        rightMargin=MARGIN, leftMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=MARGIN,
        title=f"{profile.full_name} - Perficient Profile",
        author="Perficient, Inc.",
    )

    s = _build_styles()
    story = []

    #  Header 
    name_block = [Paragraph(profile.full_name.upper(), s["name"])]
    if profile.title:
        name_block.append(Paragraph(profile.title, s["title"]))

    if os.path.exists(LOGO_PATH):
        logo = Image(LOGO_PATH)
        logo._restrictSize(4 * cm, 2 * cm)
        header_tbl = Table([[name_block, logo]],
                           colWidths=[CONTENT_W - 4.5 * cm, 4.5 * cm])
        header_tbl.setStyle(TableStyle([
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN",         (1, 0), (1, 0),   "RIGHT"),
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
            ("TOPPADDING",    (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(header_tbl)
    else:
        for p in name_block:
            story.append(p)

    story.append(Spacer(1, 0.3 * cm))
    story.append(HRFlowable(width="100%", thickness=2, color=TEAL, spaceAfter=4))
    story.append(Spacer(1, 0.3 * cm))

    #  Contact 
    meta_rows = []
    if user.email:
        meta_rows.append([Paragraph("Email", s["meta_label"]), Paragraph(user.email, s["body"])])
    if profile.location:
        meta_rows.append([Paragraph("Location", s["meta_label"]), Paragraph(profile.location, s["body"])])
    if profile.experience_years is not None:
        meta_rows.append([Paragraph("Experience", s["meta_label"]),
                          Paragraph(f"{profile.experience_years} year(s)", s["body"])])
    if meta_rows:
        story.append(_grey_table(meta_rows, [3.5 * cm, CONTENT_W - 3.5 * cm]))
        story.append(Spacer(1, 0.5 * cm))

    #  Bio 
    if profile.bio:
        story.append(Paragraph("PROFESSIONAL OVERVIEW", s["section"]))
        _divider(story)
        story.append(Paragraph(_safe(profile.bio), s["body"]))
        story.append(Spacer(1, 0.3 * cm))

    #  Skills 
    if profile.skills_list:
        story.append(Spacer(1, 0.2 * cm))
        story.append(_grey_table(
            [[Paragraph("Technologies", s["label"]),
              Paragraph("  |  ".join(profile.skills_list), s["body"])]],
            [3.5 * cm, CONTENT_W - 3.5 * cm],
        ))
        story.append(Spacer(1, 0.4 * cm))

    #  Education 
    educations = getattr(profile, "educations", [])
    if educations:
        story.append(Paragraph("EDUCATION", s["section"]))
        _divider(story)
        edu_rows = []
        for edu in educations:
            degree_line = edu.degree or ""
            if edu.field:
                degree_line += f" in {edu.field}"
            year_range = ""
            if edu.start_year and edu.end_year:
                year_range = f"{edu.start_year} - {edu.end_year}"
            elif edu.end_year:
                year_range = edu.end_year
            right = _safe(degree_line)
            if year_range:
                right += f"  |  {year_range}"
            edu_rows.append([
                Paragraph(f"<b>{_safe(edu.institution)}</b>", s["body"]),
                Paragraph(right, s["body"]),
            ])
        story.append(_grey_table(edu_rows, [CONTENT_W * 0.45, CONTENT_W * 0.55]))
        story.append(Spacer(1, 0.4 * cm))

    #  Experience 
    experiences = getattr(profile, "experiences", [])
    if experiences:
        story.append(Paragraph("PROFESSIONAL AND BUSINESS EXPERIENCE", s["section"]))
        _divider(story)
        for job in experiences:
            block = []
            end = "Present" if job.is_current or not job.end_date else job.end_date
            date_str = f"{job.start_date} - {end}".upper()
            company_line = f"{job.company}    {job.job_title}" if job.company and job.job_title else (job.company or job.job_title or "")
            block.append(Paragraph(date_str, s["employer"]))
            block.append(Paragraph(company_line, s["employer"]))
            if job.description:
                lines = [l.strip() for l in job.description.splitlines() if l.strip()]
                if lines:
                    block.append(Paragraph("<b>Responsibilities:</b>", s["body"]))
                    for line in lines:
                        prefix = "" if line.startswith(("*", "-", "•")) else "• "
                        block.append(Paragraph(f"{prefix}{_safe(line)}", s["body"]))
            block.append(Spacer(1, 0.3 * cm))
            story.append(KeepTogether(block))

    # ── Links ─────────────────────────────────────────────────────────────────
    link_rows = []
    if getattr(profile, "portfolio_url", None):
        link_rows.append([Paragraph("Portfolio", s["meta_label"]), Paragraph(profile.portfolio_url, s["body"])])
    if getattr(profile, "github_url", None):
        link_rows.append([Paragraph("GitHub", s["meta_label"]), Paragraph(profile.github_url, s["body"])])
    if getattr(profile, "linkedin_url", None):
        link_rows.append([Paragraph("LinkedIn", s["meta_label"]), Paragraph(profile.linkedin_url, s["body"])])
    if link_rows:
        story.append(Paragraph("LINKS", s["section"]))
        _divider(story)
        story.append(_grey_table(link_rows, [3.5 * cm, CONTENT_W - 3.5 * cm]))
        story.append(Spacer(1, 0.5 * cm))

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.8 * cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=MID_GREY, spaceAfter=4))
    story.append(Paragraph(
        "PERFICIENT.COM  &nbsp;&nbsp;|&nbsp;&nbsp;  Proprietary and Confidential",
        s["footer"],
    ))

    try:
        doc.build(story)
    except Exception:
        logger.exception("PDF generation failed for profile_id=%s", profile.id)
        raise

    return buffer.getvalue()