import copy
import json
import pathlib

import pytest

from app.linkedin.parse import ProfileNotInResponse, parse_dash_profile

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "dash_profile.json"


@pytest.fixture
def raw():
    return json.loads(FIXTURE.read_text())


@pytest.fixture
def profile(raw):
    return parse_dash_profile(raw)


def test_reads_the_public_id(profile):
    assert profile.public_id == "jane-doe"


def test_reads_the_profile_urn(profile):
    assert profile.urn == "urn:li:fsd_profile:ACoAAAFIXTURE0000000000000000000000000"


def test_builds_the_full_name_from_its_parts(profile):
    assert profile.name.first == "Jane"
    assert profile.name.last == "Doe"
    assert profile.name.full == "Jane Doe"


def test_reads_the_headline(profile):
    assert profile.headline == "Chair, Example Foundation and Founder, Example Energy"


def test_maps_summary_to_about(profile):
    assert profile.about == "Chair of the Example Foundation. Voracious reader."


def test_reads_the_country_code(profile):
    assert profile.location.country_code == "US"


def test_profile_image_uses_the_largest_artifact(profile):
    assert profile.images.profile == (
        "https://media.licdn.com/dms/image/v2/D5603AQFIXTURE/profile-displayphoto-shrink_"
        "400_400/fixture/0/1736826818802?e=1789603200&v=beta&t=bbb"
    )


def test_background_image_uses_the_largest_artifact(profile):
    assert profile.images.background.endswith("1584_396/fixture/0/1736826818802?e=1&v=beta&t=eee")


def test_reads_websites(profile):
    assert [(w.category, w.url) for w in profile.websites] == [("BLOG", "https://example.com/blog")]


def test_keeps_the_section_card_urns_for_later_fetches(profile):
    assert "EXPERIENCE" in profile.card_urns["experience"]
    assert "EDUCATION" in profile.card_urns["education"]


def test_a_null_summary_becomes_none_not_the_string_none(raw):
    raw["included"][0]["summary"] = None
    assert parse_dash_profile(raw).about is None


def test_a_missing_profile_picture_is_none_rather_than_an_error(raw):
    raw["included"][0]["profilePicture"] = None
    assert parse_dash_profile(raw).images.profile is None


def test_an_empty_artifact_list_is_none_rather_than_an_error(raw):
    raw["included"][0]["profilePicture"]["displayImage"]["vectorImage"]["artifacts"] = []
    assert parse_dash_profile(raw).images.profile is None


def test_a_response_with_no_profile_object_raises(raw):
    raw["included"] = []
    with pytest.raises(ProfileNotInResponse):
        parse_dash_profile(raw)


def test_parsing_does_not_mutate_the_response_it_was_given(raw):
    before = copy.deepcopy(raw)
    parse_dash_profile(raw)
    assert raw == before
