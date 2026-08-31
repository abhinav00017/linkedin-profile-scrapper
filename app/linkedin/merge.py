"""Combine what the two sources each do well.

The authenticated API gives full, unmasked core fields but no sections.
The public page gives sections and a readable locality, but masks some
values. Neither alone is a whole profile.

Rule: the API wins wherever both have a value, because the public page
truncates and masks. The public page fills only what the API left empty.
"""
from __future__ import annotations

from app.models.profile import ProfileCore

ALL_SECTIONS = ("experience", "education", "skills", "certifications", "languages")


def _first(*values):
    for v in values:
        if v:
            return v
    return None


def merge_profile(
    core: ProfileCore,
    public: ProfileCore | None,
    experience: list | None = None,
) -> ProfileCore:
    merged = core.model_copy(deep=True)
    sources = ["voyager_api"]

    if public is not None:
        sources.append("public_jsonld")

        merged.about = _first(core.about, public.about)
        merged.headline = _first(core.headline, public.headline)

        merged.location.locality = _first(core.location.locality, public.location.locality)
        merged.location.country_code = _first(
            core.location.country_code, public.location.country_code
        )

        merged.images.profile = _first(core.images.profile, public.images.profile)
        merged.images.background = _first(core.images.background, public.images.background)

        merged.name.full = _first(core.name.full, public.name.full)

        merged.experience = public.experience
        merged.education = public.education

    # The details page beats the public page for experience: it is unmasked
    # and carries employment type, duration, location and descriptions.
    if experience:
        merged.experience = experience
        sources.append("experience_details_page")

    missing = [s for s in ALL_SECTIONS if not getattr(merged, s)]

    merged.meta = {
        **(merged.meta or {}),
        "sources": sources,
        "missing_sections": missing,
        "partial": bool(missing),
    }
    return merged
