"""Read the /details/experience/ page.

LinkedIn server-renders this page, so a plain GET returns the whole list —
titles, companies, employment types, dates, locations and descriptions, all
unmasked. It is the richest source available without a browser.

The markup uses generated class names that change on every LinkedIn deploy,
so nothing here keys on a class. We work from the text in document order and
anchor on the date line, which has a shape LinkedIn has kept stable:

    Product Designer                          <- title
    Craft My Plate · Full-time                <- company · employment type
    Jan 2025 - Mar 2026 · 1 yr 3 mos          <- the anchor
    Hyderabad, Telangana, India · On-site     <- location · work mode
    Led design and shipped V2 …               <- description
    Product Design, Strategy and +2 skills    <- skills
"""
from __future__ import annotations

import html as htmllib
import re

from app.models.profile import DateParts, Experience

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

# "Jan 2025 - Mar 2026", "2019 - 2023", "Apr 2026 - Present"
DATE_RANGE = re.compile(
    r"^(?P<start>(?:[A-Z][a-z]{2}\s+)?\d{4})\s*[-–]\s*(?P<end>Present|(?:[A-Z][a-z]{2}\s+)?\d{4})\b"
)

MONTH_YEAR = re.compile(r"^(?:(?P<month>[A-Z][a-z]{2})\s+)?(?P<year>\d{4})$")

SKILLS_LINE = re.compile(r"(?:\band\s\+\d+\s+skills?|\bskills?)\s*$", re.IGNORECASE)

WORK_MODES = {"on-site", "remote", "hybrid"}

# LinkedIn injects these next to some roles. They are not profile data.
NOISE = {
    "linkedin helped me get this job",
    "helped me get this job",
    "show all",
    "…see more",
    "see more",
    "translate to english",
}

STOP_HEADINGS = {"ad options", "more profiles for you", "about", "people also viewed"}

SEP = "·"


def extract_text_lines(page: str) -> list[str]:
    """The page's visible text, one line per element, in document order."""
    without_code = re.sub(
        r"<(script|style|noscript)[^>]*>.*?</\1>", " ", page, flags=re.DOTALL | re.I
    )
    text = re.sub(r"<[^>]+>", "\n", without_code)
    text = htmllib.unescape(text)
    return [line.strip() for line in text.split("\n") if line.strip()]


def parse_month_year(value: str) -> DateParts | None:
    match = MONTH_YEAR.match(value.strip())
    if not match:
        return None
    month = match.group("month")
    return DateParts(
        year=int(match.group("year")),
        month=MONTHS.get(month.lower()) if month else None,
    )


def _split_on_separator(line: str) -> tuple[str, str | None]:
    if SEP in line:
        left, _, right = line.partition(SEP)
        return left.strip(), right.strip() or None
    return line.strip(), None


def _is_noise(line: str) -> bool:
    return line.strip().lower() in NOISE


def _looks_like_a_location(line: str) -> bool:
    """A location is a comma-separated place, or a bare work mode."""
    lowered = line.strip().lower()
    if lowered in WORK_MODES:
        return True
    place, mode = _split_on_separator(line)
    if mode and mode.lower() in WORK_MODES:
        return True
    return "," in place and not place.endswith(".")


def _parse_skills(line: str) -> list[str]:
    """'Product Design, Strategy and +2 skills' -> the two named skills.

    The '+2' ones are not named on the page, so we return only what is there.
    """
    body = re.sub(r"\s*and\s\+\d+\s+skills?\s*$", "", line, flags=re.I)
    body = re.sub(r"\s*skills?\s*$", "", body, flags=re.I)
    return [part.strip() for part in body.split(",") if part.strip()]


def parse_experience_lines(lines: list[str]) -> list[Experience]:
    """Group the page's text into roles, anchoring on each date line."""
    # Stop before the ad block and the sidebar.
    end = len(lines)
    for i, line in enumerate(lines):
        if line.strip().lower() in STOP_HEADINGS:
            end = i
            break
    lines = lines[:end]

    anchors = [i for i, line in enumerate(lines) if DATE_RANGE.match(line)]
    roles: list[Experience] = []

    for position, anchor in enumerate(anchors):
        # A role needs a title and a company line above its date line.
        if anchor < 2:
            continue

        title = lines[anchor - 2]
        company_line = lines[anchor - 1]

        # Everything up to two lines before the next date line belongs here.
        extras_end = anchors[position + 1] - 2 if position + 1 < len(anchors) else len(lines)
        extras = [ln for ln in lines[anchor + 1:extras_end] if not _is_noise(ln)]

        company, employment_type = _split_on_separator(company_line)

        match = DATE_RANGE.match(lines[anchor])
        start = parse_month_year(match.group("start"))
        end_raw = match.group("end")
        finish = None if end_raw == "Present" else parse_month_year(end_raw)
        _, duration = _split_on_separator(lines[anchor])

        location = work_mode = None
        skills: list[str] = []
        description_parts: list[str] = []

        for extra in extras:
            if SKILLS_LINE.search(extra):
                skills = _parse_skills(extra)
            elif location is None and work_mode is None and _looks_like_a_location(extra):
                place, mode = _split_on_separator(extra)
                if place.lower() in WORK_MODES:
                    work_mode = place
                else:
                    location = place
                    work_mode = mode
            else:
                description_parts.append(extra)

        roles.append(
            Experience(
                title=title,
                company=company,
                employment_type=employment_type,
                start=start,
                end=finish,
                is_current=end_raw == "Present",
                duration=duration,
                location=location,
                work_mode=work_mode,
                description="\n".join(description_parts) or None,
                skills=skills,
            )
        )

    return roles


def parse_experience_page(page: str) -> list[Experience]:
    return parse_experience_lines(extract_text_lines(page))
