"""Read the JSON-LD block LinkedIn embeds in public profile pages.

LinkedIn publishes this for search engines. It carries experience and
education, which the authenticated API does not hand us in one call.

It masks some values for logged-out readers, writing them as runs of
asterisks. We turn those into null rather than passing the asterisks on.
"""
from __future__ import annotations

from typing import Any

from app.models.profile import (
    DateParts,
    Education,
    Experience,
    Images,
    Location,
    Name,
    ProfileCore,
)


class NoPersonInJsonLd(ValueError):
    """The document holds no Person node."""


def _unmask(value: Any) -> str | None:
    """LinkedIn masks hidden values as asterisks. Report nothing, not '****'."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if set(text) <= {"*", " "}:
        return None
    return text


def _find_person(doc: dict[str, Any]) -> dict[str, Any]:
    if doc.get("@type") == "Person":
        return doc
    for node in doc.get("@graph") or []:
        if isinstance(node, dict) and node.get("@type") == "Person":
            return node
    raise NoPersonInJsonLd("no Person node in the JSON-LD document")


def _titles(person: dict[str, Any]) -> list[str | None]:
    raw = person.get("jobTitle")
    if isinstance(raw, str):
        return [_unmask(raw)]
    if isinstance(raw, list):
        return [_unmask(t) for t in raw]
    return []


def _year(value: Any) -> DateParts | None:
    if isinstance(value, int):
        return DateParts(year=value)
    if isinstance(value, str) and value.isdigit():
        return DateParts(year=int(value))
    return None


def _split_name(full: str | None) -> Name:
    if not full:
        return Name()
    parts = full.split()
    if len(parts) == 1:
        return Name(first=parts[0], full=full)
    return Name(first=parts[0], last=" ".join(parts[1:]), full=full)


def _experience(person: dict[str, Any]) -> list[Experience]:
    """Pair jobTitle with worksFor by position — LinkedIn aligns the two lists."""
    titles = _titles(person)
    out: list[Experience] = []

    for i, org in enumerate(person.get("worksFor") or []):
        if not isinstance(org, dict):
            continue
        member = org.get("member") or {}
        start = _year(member.get("startDate"))
        end = _year(member.get("endDate"))
        out.append(
            Experience(
                title=titles[i] if i < len(titles) else None,
                company=_unmask(org.get("name")),
                company_url=_unmask(org.get("url")),
                start=start,
                end=end,
                is_current=bool(start) and end is None,
            )
        )
    return out


def _education(person: dict[str, Any]) -> list[Education]:
    out: list[Education] = []
    for org in person.get("alumniOf") or []:
        if not isinstance(org, dict):
            continue
        member = org.get("member") or {}
        out.append(
            Education(
                school=_unmask(org.get("name")),
                degree=_unmask(member.get("degree")),
                field_of_study=_unmask(member.get("fieldOfStudy")),
                start=_year(member.get("startDate")),
                end=_year(member.get("endDate")),
            )
        )
    return out


def parse_person(doc: dict[str, Any]) -> ProfileCore:
    person = _find_person(doc)

    address = person.get("address") or {}
    image = person.get("image") or {}

    return ProfileCore(
        name=_split_name(_unmask(person.get("name"))),
        about=_unmask(person.get("description")),
        location=Location(
            country_code=_unmask(address.get("addressCountry")),
            locality=_unmask(address.get("addressLocality")),
        ),
        images=Images(profile=_unmask(image.get("contentUrl"))),
        experience=_experience(person),
        education=_education(person),
    )
