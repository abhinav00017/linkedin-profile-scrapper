import pytest

from app.linkedin.jsonld import NoPersonInJsonLd, parse_person

PERSON = {
    "@type": "Person",
    "name": "Jane Doe",
    "description": "Chair of the Example Foundation.",
    "jobTitle": ["Chair", "Founder", "Co-founder"],
    "address": {
        "@type": "PostalAddress",
        "addressCountry": "US",
        "addressLocality": "Seattle, Washington, United States",
    },
    "image": {"@type": "ImageObject", "contentUrl": "https://media.licdn.com/x.jpg"},
    "worksFor": [
        {
            "@type": "Organization",
            "name": "Example Foundation",
            "url": "https://www.linkedin.com/company/example-foundation",
            "member": {"@type": "OrganizationRole", "startDate": 2000},
        },
        {
            "@type": "Organization",
            "name": "Example Energy",
            "member": {"@type": "OrganizationRole", "startDate": 2015, "endDate": 2020},
        },
        {"@type": "Organization", "name": "Example Corp", "member": {"@type": "OrganizationRole"}},
    ],
    "alumniOf": [
        {
            "@type": "EducationalOrganization",
            "name": "Example University",
            "url": "https://www.linkedin.com/school/example-university/",
            "member": {"@type": "OrganizationRole", "startDate": 1973, "endDate": 1975},
        }
    ],
}


def doc(person=None):
    return {"@graph": [{"@type": "WebPage"}, person or PERSON]}


@pytest.fixture
def parsed():
    return parse_person(doc())


def test_reads_the_name(parsed):
    assert parsed.name.full == "Jane Doe"


def test_reads_the_about_text(parsed):
    assert parsed.about == "Chair of the Example Foundation."


def test_locality_is_richer_than_the_bare_country_code(parsed):
    assert parsed.location.locality == "Seattle, Washington, United States"
    assert parsed.location.country_code == "US"


def test_reads_the_profile_image(parsed):
    assert parsed.images.profile == "https://media.licdn.com/x.jpg"


def test_experience_pairs_job_titles_with_companies_by_position(parsed):
    assert [(e.title, e.company) for e in parsed.experience] == [
        ("Chair", "Example Foundation"),
        ("Founder", "Example Energy"),
        ("Co-founder", "Example Corp"),
    ]


def test_experience_carries_the_company_url_when_linkedin_gives_one(parsed):
    assert parsed.experience[0].company_url == "https://www.linkedin.com/company/example-foundation"
    assert parsed.experience[1].company_url is None


def test_experience_reads_start_and_end_years(parsed):
    assert parsed.experience[1].start.year == 2015
    assert parsed.experience[1].end.year == 2020


def test_a_role_with_no_end_date_is_marked_current(parsed):
    assert parsed.experience[0].is_current is True
    assert parsed.experience[1].is_current is False


def test_education_reads_school_and_years(parsed):
    edu = parsed.education[0]
    assert edu.school == "Example University"
    assert edu.start.year == 1973
    assert edu.end.year == 1975


def test_masked_values_become_none_rather_than_rows_of_asterisks():
    person = dict(PERSON)
    person["jobTitle"] = ["********", "Founder", "**********"]
    person["worksFor"] = [
        {"@type": "Organization", "name": "*********** ****", "member": {}},
        {"@type": "Organization", "name": "Example Energy", "member": {}},
        {"@type": "Organization", "name": "Example Corp", "member": {}},
    ]
    out = parse_person(doc(person))
    assert out.experience[0].title is None
    assert out.experience[0].company is None
    assert out.experience[1].title == "Founder"
    assert out.experience[1].company == "Example Energy"


def test_a_single_job_title_string_is_accepted_as_well_as_a_list():
    person = dict(PERSON)
    person["jobTitle"] = "Chair"
    person["worksFor"] = [{"@type": "Organization", "name": "Example Foundation", "member": {}}]
    assert parse_person(doc(person)).experience[0].title == "Chair"


def test_more_companies_than_titles_does_not_raise():
    person = dict(PERSON)
    person["jobTitle"] = ["Chair"]
    out = parse_person(doc(person))
    assert len(out.experience) == 3
    assert out.experience[2].title is None


def test_a_document_with_no_person_raises():
    with pytest.raises(NoPersonInJsonLd):
        parse_person({"@graph": [{"@type": "WebPage"}]})


def test_a_bare_person_document_without_a_graph_is_accepted():
    assert parse_person(PERSON).name.full == "Jane Doe"


def test_missing_sections_are_empty_lists_not_errors():
    out = parse_person({"@type": "Person", "name": "Jane Doe"})
    assert out.experience == []
    assert out.education == []
