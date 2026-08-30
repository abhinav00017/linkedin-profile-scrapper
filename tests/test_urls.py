import pytest
from app.linkedin.urls import parse_profile_url, InvalidProfileUrl


@pytest.mark.parametrize("raw", [
    "https://www.linkedin.com/in/jane-doe",
    "https://www.linkedin.com/in/jane-doe/",
    "http://linkedin.com/in/jane-doe",
    "https://in.linkedin.com/in/jane-doe",
    "https://www.linkedin.com/in/jane-doe?originalSubdomain=in",
    "https://www.linkedin.com/in/jane-doe/en",
    "www.linkedin.com/in/jane-doe",
    "linkedin.com/in/jane-doe",
    "  https://www.linkedin.com/in/jane-doe/  ",
    "jane-doe",
])
def test_extracts_public_id_from_every_url_variant(raw):
    assert parse_profile_url(raw).public_id == "jane-doe"


def test_percent_encoded_public_id_is_decoded():
    assert parse_profile_url("https://www.linkedin.com/in/jos%C3%A9-garc%C3%ADa").public_id == "josé-garcía"


def test_public_id_keeps_linkedin_numeric_suffix():
    assert parse_profile_url("https://www.linkedin.com/in/jane-doe-1a2b3c4d5").public_id == "jane-doe-1a2b3c4d5"


def test_canonical_url_is_rebuilt_in_normal_form():
    assert parse_profile_url("linkedin.com/in/jane-doe?trk=x").canonical_url == "https://www.linkedin.com/in/jane-doe/"


@pytest.mark.parametrize("raw", [
    "https://www.linkedin.com/company/acme/",
    "https://www.linkedin.com/school/mit/",
    "https://www.linkedin.com/feed/update/urn:li:activity:123/",
    "https://www.linkedin.com/jobs/view/123456/",
    "https://twitter.com/in/jane-doe",
    "https://www.linkedin.com/in/",
    "",
    "   ",
    "https://www.linkedin.com/",
])
def test_rejects_anything_that_is_not_a_profile_url(raw):
    with pytest.raises(InvalidProfileUrl):
        parse_profile_url(raw)


def test_rejects_a_public_id_that_is_absurdly_long():
    with pytest.raises(InvalidProfileUrl):
        parse_profile_url("a" * 200)
