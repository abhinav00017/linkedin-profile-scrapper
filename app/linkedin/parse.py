"""Turn LinkedIn's Voyager JSON into our response schema.

Voyager answers with a flat `included` list of typed objects. Nothing here
touches the network, so every rule below is testable against a saved fixture.
"""
from __future__ import annotations

from typing import Any

from app.models.profile import Images, Location, Name, Profile, Website

PROFILE_TYPE = "com.linkedin.voyager.dash.identity.profile.Profile"


class ProfileNotInResponse(ValueError):
    """LinkedIn answered, but the payload held no profile."""


def _find(included: list[dict[str, Any]], type_suffix: str) -> list[dict[str, Any]]:
    return [o for o in included if str(o.get("$type", "")).endswith(type_suffix)]


def _largest_image_url(picture: Any) -> str | None:
    """Build the URL of the biggest artifact in a LinkedIn vector image.

    LinkedIn splits an image into a root URL plus one path segment per size.
    The full URL is the two joined.
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


def _full_name(first: str | None, last: str | None) -> str:
    return " ".join(part for part in (first, last) if part).strip()


def parse_dash_profile(payload: dict[str, Any]) -> Profile:
    """Parse a /identity/dash/profiles?q=memberIdentity response."""
    included = payload.get("included") or []
    profiles = _find(included, "identity.profile.Profile")
    if not profiles:
        raise ProfileNotInResponse("no Profile object in the response")

    p = profiles[0]

    public_id = p.get("publicIdentifier") or ""
    first, last = p.get("firstName"), p.get("lastName")

    card_urns: dict[str, str] = {}
    for key, section in (("experienceCardUrn", "experience"),
                         ("educationCardUrn", "education")):
        if p.get(key):
            card_urns[section] = p[key]

    websites = [
        Website(category=w.get("category"), url=w["url"])
        for w in (p.get("websites") or [])
        if isinstance(w, dict) and w.get("url")
    ]

    geo = p.get("geoLocation") or {}
    loc = p.get("location") or {}

    return Profile(
        profile_url=f"https://www.linkedin.com/in/{public_id}/",
        public_id=public_id,
        urn=p.get("entityUrn"),
        member_urn=p.get("objectUrn"),
        name=Name(first=first, last=last, full=_full_name(first, last)),
        headline=p.get("headline"),
        about=p.get("summary"),
        location=Location(
            country_code=loc.get("countryCode"),
            geo_urn=geo.get("geoUrn"),
            name=p.get("locationName"),
        ),
        images=Images(
            profile=_largest_image_url(p.get("profilePicture")),
            background=_largest_image_url(p.get("backgroundPicture")),
        ),
        websites=websites,
        is_influencer=bool(p.get("influencer")),
        is_premium=bool(p.get("premium")),
        card_urns=card_urns,
    )
