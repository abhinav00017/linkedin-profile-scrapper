from app.linkedin.details import (
    extract_text_lines,
    parse_experience_lines,
    parse_month_year,
)

# Verbatim from a real /details/experience/ page.
REAL_LINES = [
    "Experience",
    "Product Designer",
    "Freelance",
    "Apr 2026 - Present · 5 mos",
    "Remote",
    "Product Design, Strategy and +2 skills",
    "Product Designer",
    "Craft My Plate · Full-time",
    "Jan 2025 - Mar 2026 · 1 yr 3 mos",
    "Hyderabad, Telangana, India · On-site",
    "User Experience Designer - Contract",
    "Network of Creative Thinkers · Full-time",
    "Aug 2024 - Dec 2024 · 5 mos",
    "Panchgani, Maharashtra, India · On-site",
    "LinkedIn helped me get this job",
    "helped me get this job",
    "Product Designer",
    "HireIntel · Full-time",
    "Dec 2023 - Aug 2024 · 9 mos",
    "Bengaluru, Karnataka, India · Remote",
    "Led design and shipped V2 of HireIntel's platform.",
    "Reduced candidate drop-offs by 26%, enabling thousands of interviews.",
    "User Experience (UX), Product Design and +4 skills",
    "Ad Options",
]


def parsed():
    return parse_experience_lines(REAL_LINES)


def test_finds_every_role():
    assert len(parsed()) == 4


def test_reads_titles_in_page_order():
    assert [e.title for e in parsed()] == [
        "Product Designer",
        "Product Designer",
        "User Experience Designer - Contract",
        "Product Designer",
    ]


def test_splits_company_from_employment_type():
    roles = parsed()
    assert roles[1].company == "Craft My Plate"
    assert roles[1].employment_type == "Full-time"


def test_a_company_with_no_employment_type_is_left_alone():
    roles = parsed()
    assert roles[0].company == "Freelance"
    assert roles[0].employment_type is None


def test_reads_start_and_end_months():
    roles = parsed()
    assert (roles[1].start.year, roles[1].start.month) == (2025, 1)
    assert (roles[1].end.year, roles[1].end.month) == (2026, 3)


def test_a_present_role_has_no_end_date_and_is_current():
    role = parsed()[0]
    assert role.end is None
    assert role.is_current is True
    assert (role.start.year, role.start.month) == (2026, 4)


def test_a_finished_role_is_not_current():
    assert parsed()[1].is_current is False


def test_reads_location_and_work_mode():
    role = parsed()[1]
    assert role.location == "Hyderabad, Telangana, India"
    assert role.work_mode == "On-site"


def test_a_bare_work_mode_counts_as_the_location_field():
    role = parsed()[0]
    assert role.work_mode == "Remote"


def test_reads_the_description():
    role = parsed()[3]
    assert "Led design and shipped V2" in role.description
    assert "Reduced candidate drop-offs by 26%" in role.description


def test_the_skills_line_is_not_treated_as_description():
    for role in parsed():
        assert "skills" not in (role.description or "")


def test_linkedin_promo_lines_are_dropped():
    for role in parsed():
        assert "helped me get this job" not in (role.description or "")


def test_a_page_with_no_roles_gives_an_empty_list():
    assert parse_experience_lines(["Experience", "Ad Options"]) == []


class TestMonthYear:
    def test_reads_a_month_and_year(self):
        d = parse_month_year("Apr 2026")
        assert (d.year, d.month) == (2026, 4)

    def test_reads_a_bare_year(self):
        d = parse_month_year("2019")
        assert (d.year, d.month) == (2019, None)

    def test_present_is_not_a_date(self):
        assert parse_month_year("Present") is None

    def test_nonsense_is_not_a_date(self):
        assert parse_month_year("banana") is None


class TestTextExtraction:
    def test_strips_tags_and_keeps_the_text(self):
        html = "<div><p>Product Designer</p><p>Freelance</p></div>"
        assert extract_text_lines(html) == ["Product Designer", "Freelance"]

    def test_drops_script_and_style_content(self):
        html = "<script>var x = 'Hidden';</script><style>.a{color:red}</style><p>Kept</p>"
        assert extract_text_lines(html) == ["Kept"]

    def test_unescapes_entities(self):
        assert extract_text_lines("<p>Tools &amp; Technologies</p>") == [
            "Tools & Technologies"
        ]
