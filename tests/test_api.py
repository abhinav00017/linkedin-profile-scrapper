import json
import pathlib

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.linkedin import client as li_client
from app.main import create_app
from app.store.keys import KeyStore

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "dash_profile.json"

ME = {
    "data": {},
    "included": [{"firstName": "Jane", "lastName": "Doe", "publicIdentifier": "jane-doe"}],
}

PUBLIC_PERSON = {
    "@type": "Person",
    "name": "Jane Doe",
    "jobTitle": ["Chair"],
    "address": {"addressCountry": "US", "addressLocality": "Seattle, Washington"},
    "worksFor": [{"@type": "Organization", "name": "Example Foundation",
                  "member": {"startDate": 2000}}],
    "alumniOf": [{"@type": "EducationalOrganization", "name": "Example University",
                  "member": {"startDate": 1973, "endDate": 1975}}],
}


@pytest.fixture
def settings(tmp_path):
    return Settings(
        encryption_key=KeyStore.generate_encryption_key(),
        db_path=str(tmp_path / "keys.db"),
        bootstrap_api_key="tk_demo",
        bootstrap_li_at="AQEDAdemocookievalue000000000000",
        bootstrap_jsessionid="ajax:1",
    )


@pytest.fixture
def app(settings, monkeypatch):
    async def fake_validate(self):
        return ME

    async def fake_core(self, public_id):
        return json.loads(FIXTURE.read_text())

    async def fake_public(self, public_id, attempts=3):
        return PUBLIC_PERSON

    async def fake_experience(self, public_id):
        return None

    monkeypatch.setattr(li_client.LinkedInClient, "validate", fake_validate)
    monkeypatch.setattr(li_client.LinkedInClient, "fetch_core_profile", fake_core)
    monkeypatch.setattr(li_client.LinkedInClient, "fetch_public_jsonld", fake_public)
    monkeypatch.setattr(li_client.LinkedInClient, "fetch_experience_page", fake_experience)

    application = create_app()
    application.dependency_overrides[get_settings] = lambda: settings
    return application


@pytest.fixture
def api(app):
    return TestClient(app)


def test_health_needs_no_key(api):
    r = api.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_auth_returns_a_key_and_says_who_the_session_belongs_to(api):
    r = api.post("/v1/auth", json={"li_at": "AQEDA" + "x" * 40})
    assert r.status_code == 201
    body = r.json()
    assert body["api_key"].startswith("tk_")
    assert body["linkedin_member"]["name"] == "Jane Doe"


def test_auth_rejects_an_obviously_empty_cookie(api):
    r = api.post("/v1/auth", json={"li_at": "short"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "invalid_request"


def test_profile_without_a_key_is_refused(api):
    r = api.get("/v1/profile", params={"url": "https://www.linkedin.com/in/jane-doe/"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "missing_api_key"


def test_public_demo_mode_serves_a_profile_with_no_key(app, settings):
    settings.public_demo = True
    r = TestClient(app).get(
        "/v1/profile", params={"url": "https://www.linkedin.com/in/jane-doe/"}
    )
    assert r.status_code == 200
    assert r.json()["name"]["full"] == "Jane Doe"


def test_public_demo_mode_needs_a_bootstrap_key_configured(app, settings):
    settings.public_demo = True
    settings.bootstrap_api_key = None
    r = TestClient(app).get(
        "/v1/profile", params={"url": "https://www.linkedin.com/in/jane-doe/"}
    )
    assert r.status_code == 401


def test_without_public_demo_a_keyless_request_is_still_refused(app, settings):
    settings.public_demo = False
    r = TestClient(app).get(
        "/v1/profile", params={"url": "https://www.linkedin.com/in/jane-doe/"}
    )
    assert r.status_code == 401


def test_profile_with_an_unknown_key_is_refused(api):
    r = api.get("/v1/profile",
                params={"url": "https://www.linkedin.com/in/jane-doe/"},
                headers={"X-API-Key": "tk_nope"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_api_key"


def test_the_bootstrap_key_works_with_no_prior_auth_call(api):
    r = api.get("/v1/profile",
                params={"url": "https://www.linkedin.com/in/jane-doe/"},
                headers={"X-API-Key": "tk_demo"})
    assert r.status_code == 200


def test_a_non_profile_url_is_rejected(api):
    r = api.get("/v1/profile",
                params={"url": "https://www.linkedin.com/company/acme/"},
                headers={"X-API-Key": "tk_demo"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "invalid_profile_url"


def test_a_profile_comes_back_with_core_fields_and_sections(api):
    r = api.get("/v1/profile",
                params={"url": "https://www.linkedin.com/in/jane-doe/"},
                headers={"X-API-Key": "tk_demo"})
    assert r.status_code == 200
    body = r.json()

    assert body["name"]["full"] == "Jane Doe"
    assert body["headline"].startswith("Chair")
    assert body["about"].startswith("Chair of the Example Foundation")
    assert body["profile_url"] == "https://www.linkedin.com/in/jane-doe/"
    assert body["images"]["profile"].startswith("https://media.licdn.com/")
    assert body["experience"][0]["company"] == "Example Foundation"
    assert body["education"][0]["school"] == "Example University"


def test_meta_is_honest_about_what_is_missing(api):
    r = api.get("/v1/profile",
                params={"url": "jane-doe"},
                headers={"X-API-Key": "tk_demo"})
    meta = r.json()["meta"]
    assert meta["sources"] == ["voyager_api", "public_jsonld"]
    assert "skills" in meta["missing_sections"]
    assert meta["partial"] is True
    assert "fetched_at" in meta
    assert isinstance(meta["duration_ms"], int)


def test_a_dead_linkedin_session_is_reported_as_403(api, monkeypatch):
    async def dead(self, public_id):
        raise li_client.SessionDead("revoked")

    monkeypatch.setattr(li_client.LinkedInClient, "fetch_core_profile", dead)
    r = api.get("/v1/profile", params={"url": "jane-doe"},
                headers={"X-API-Key": "tk_demo"})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "linkedin_session_dead"


def test_a_missing_profile_is_reported_as_404(api, monkeypatch):
    async def missing(self, public_id):
        raise li_client.ProfileNotFound("no such profile")

    monkeypatch.setattr(li_client.LinkedInClient, "fetch_core_profile", missing)
    r = api.get("/v1/profile", params={"url": "jane-doe"},
                headers={"X-API-Key": "tk_demo"})
    assert r.status_code == 404


def test_the_profile_still_returns_when_the_public_page_fails(api, monkeypatch):
    async def no_public(self, public_id, attempts=3):
        return None

    monkeypatch.setattr(li_client.LinkedInClient, "fetch_public_jsonld", no_public)
    r = api.get("/v1/profile", params={"url": "jane-doe"},
                headers={"X-API-Key": "tk_demo"})
    assert r.status_code == 200
    body = r.json()
    assert body["name"]["full"] == "Jane Doe"
    assert body["experience"] == []
    assert body["meta"]["sources"] == ["voyager_api"]


def test_the_rate_limit_eventually_refuses(api, settings, monkeypatch):
    from app.api import routes
    routes.limiter._hits.clear()
    monkeypatch.setattr(settings, "rate_limit_per_minute", 3)

    codes = [
        api.get("/v1/profile", params={"url": "jane-doe"},
                headers={"X-API-Key": "tk_demo"}).status_code
        for _ in range(5)
    ]
    assert codes[:3] == [200, 200, 200]
    assert 429 in codes[3:]
