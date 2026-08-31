from app.linkedin.merge import merge_profile
from app.models.profile import (
    DateParts,
    Education,
    Experience,
    Images,
    Location,
    Name,
    ProfileCore,
)


def core():
    return ProfileCore(
        public_id="jane-doe",
        urn="urn:li:fsd_profile:X",
        name=Name(first="Jane", last="Doe", full="Jane Doe"),
        headline="Chair, Example Foundation",
        about="The full unmasked about text from the API.",
        location=Location(country_code="US"),
        images=Images(profile="https://api.example/photo.jpg",
                      background="https://api.example/bg.jpg"),
    )


def public():
    return ProfileCore(
        name=Name(first="Jane", last="Doe", full="Jane Doe"),
        about="Truncated about text…",
        location=Location(country_code="US", locality="Seattle, Washington, United States"),
        images=Images(profile="https://public.example/photo.jpg"),
        experience=[Experience(title="Chair", company="Example Foundation",
                               start=DateParts(year=2000), is_current=True)],
        education=[Education(school="Example University", start=DateParts(year=1973))],
    )


def test_the_api_wins_for_fields_both_sources_have():
    merged = merge_profile(core(), public())
    assert merged.about == "The full unmasked about text from the API."
    assert merged.images.profile == "https://api.example/photo.jpg"


def test_the_public_page_fills_the_locality_the_api_lacks():
    merged = merge_profile(core(), public())
    assert merged.location.locality == "Seattle, Washington, United States"
    assert merged.location.country_code == "US"


def test_sections_come_from_the_public_page():
    merged = merge_profile(core(), public())
    assert merged.experience[0].company == "Example Foundation"
    assert merged.education[0].school == "Example University"


def test_the_api_identity_is_kept():
    merged = merge_profile(core(), public())
    assert merged.public_id == "jane-doe"
    assert merged.urn == "urn:li:fsd_profile:X"
    assert merged.headline == "Chair, Example Foundation"


def test_a_missing_public_page_still_returns_the_core_profile():
    merged = merge_profile(core(), None)
    assert merged.name.full == "Jane Doe"
    assert merged.experience == []


def test_meta_names_the_sections_we_could_not_get():
    merged = merge_profile(core(), public())
    assert "skills" in merged.meta["missing_sections"]
    assert "certifications" in merged.meta["missing_sections"]
    assert "languages" in merged.meta["missing_sections"]
    assert merged.meta["partial"] is True


def test_meta_records_which_sources_answered():
    merged = merge_profile(core(), public())
    assert merged.meta["sources"] == ["voyager_api", "public_jsonld"]

    merged = merge_profile(core(), None)
    assert merged.meta["sources"] == ["voyager_api"]


def test_experience_missing_counts_as_a_missing_section():
    merged = merge_profile(core(), None)
    assert "experience" in merged.meta["missing_sections"]
    assert "education" in merged.meta["missing_sections"]
