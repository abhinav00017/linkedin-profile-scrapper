"""Turn LinkedIn's normalised response graph into our flat schema.

No network here on purpose. Everything in this module is a pure function of
the JSON it is given, so it can be tested against saved fixtures.
"""
from __future__ import annotations

from typing import Any

from app.models.profile import (
    Images,
    Location,
    Name,
    ProfileCore,
    Website,
)

PROFILE_TYPE = "com.linkedin.voyager.dash.identity.profile.Profile"


class ProfileNotInResponse(ValueError):
    """LinkedIn answered, but the response carries no profile."""


def _find_profile(raw: dict[str, Any]) -> dict[str, Any]:
    for obj in raw.get("included") or []:
        if obj.get("$type") == PROFILE_TYPE:
            return obj
    raise ProfileNotInResponse(
        "no Profile object in the response — the profile may be private, "
        "deleted, or outside what this session may view"
    )


def _largest_image_url(picture: Any) -> str | None:
    """Build the URL of the biggest artifact LinkedIn offers.

    A vector image is a root URL plus a list of sized artifacts. The full URL
    is the root concatenated with an artifact's path segment.
    """
    if not isinstance(picture, dict):
        return None

    vector = (picture.get("displayImage") or {}).get("vectorImage")
    if not isinstance(vector, dict):
        return None

    root = vector.get("rootUrl")
    artifacts = vector.get("artifacts") or []
    if not root or not artifacts:
        return None

    biggest = max(artifacts, key=lambda a: a.get("width") or 0)
    segment = biggest.get("fileIdentifyingUrlPathSegment")
    if not segment:
        return None

    return f"{root}{segment}"


def _full_name(first: str | None, last: str | None) -> str | None:
    parts = [p for p in (first, last) if p]
    return " ".join(parts) if parts else None


def _card_urns(profile: dict[str, Any]) -> dict[str, str]:
    """Collect the section card urns the core response hands us."""
    out: dict[str, str] = {}
    for key, name in (("experienceCardUrn", "experience"),
                      ("educationCardUrn", "education")):
        value = profile.get(key)
        if isinstance(value, str) and value:
            out[name] = value
    return out


def parse_dash_profile(raw: dict[str, Any]) -> ProfileCore:
    """Parse the /identity/dash/profiles response into our core profile."""
    profile = _find_profile(raw)

    first = profile.get("firstName")
    last = profile.get("lastName")
    public_id = profile.get("publicIdentifier")

    location_obj = profile.get("location") or {}
    geo_obj = profile.get("geoLocation") or {}

    websites = [
        Website(category=w.get("category"), url=w["url"])
        for w in (profile.get("websites") or [])
        if isinstance(w, dict) and w.get("url")
    ]

    return ProfileCore(
        profile_url=(
            f"https://www.linkedin.com/in/{public_id}/" if public_id else None
        ),
        public_id=public_id,
        urn=profile.get("entityUrn"),
        name=Name(first=first, last=last, full=_full_name(first, last)),
        headline=profile.get("headline"),
        about=profile.get("summary"),
        location=Location(
            country_code=location_obj.get("countryCode"),
            locality=profile.get("locationName"),
            geo_urn=geo_obj.get("geoUrn"),
        ),
        images=Images(
            profile=_largest_image_url(profile.get("profilePicture")),
            background=_largest_image_url(profile.get("backgroundPicture")),
        ),
        websites=websites,
        industry_urn=profile.get("industryUrn"),
        is_premium=bool(profile.get("premium")),
        is_influencer=bool(profile.get("influencer")),
        card_urns=_card_urns(profile),
    )
