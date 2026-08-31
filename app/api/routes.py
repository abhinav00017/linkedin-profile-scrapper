"""The public API.

Two endpoints that matter: exchange a LinkedIn cookie for an API key, then
use that key to read any profile.
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings
from app.core.limits import RateLimiter
from app.linkedin.client import (
    LinkedInClient,
    LinkedInError,
    LinkedInSession,
    ProfileNotFound,
    RateLimited,
    SessionDead,
)
from app.linkedin.jsonld import NoPersonInJsonLd, parse_person
from app.linkedin.details import parse_experience_page
from app.linkedin.merge import merge_profile
from app.linkedin.parse import ProfileNotInResponse, parse_dash_profile
from app.linkedin.urls import InvalidProfileUrl, parse_profile_url
from app.models.profile import ProfileCore
from app.store.keys import KeyStore

router = APIRouter()
limiter = RateLimiter()


def fail(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def get_store(settings: Settings = Depends(get_settings)) -> KeyStore:
    return KeyStore(
        db_path=settings.db_path,
        encryption_key=settings.encryption_key,
        bootstrap_key=settings.bootstrap_api_key,
        bootstrap_li_at=settings.bootstrap_li_at,
        bootstrap_jsessionid=settings.bootstrap_jsessionid,
    )


class AuthRequest(BaseModel):
    li_at: str = Field(..., min_length=20, description="Your LinkedIn li_at cookie")
    jsessionid: str | None = Field(None, description="Your JSESSIONID cookie")
    cookie_header: str | None = Field(
        None,
        description=(
            "The complete cookie header from a logged-in browser. Optional, but "
            "it makes requests far more reliable than li_at alone."
        ),
    )


class AuthResponse(BaseModel):
    api_key: str
    linkedin_member: dict
    created_at: str


class HealthResponse(BaseModel):
    status: str
    version: str


@router.get("/healthz", response_model=HealthResponse, tags=["meta"])
async def healthz(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(status="ok", version=settings.version)


@router.post("/v1/auth", response_model=AuthResponse, status_code=201, tags=["auth"])
async def authenticate(
    body: AuthRequest,
    store: KeyStore = Depends(get_store),
    settings: Settings = Depends(get_settings),
) -> AuthResponse:
    """Exchange a LinkedIn session cookie for an API key.

    We check the cookie against LinkedIn before minting anything, so a key we
    hand back is a key that works.
    """
    session = LinkedInSession(
        li_at=body.li_at,
        jsessionid=body.jsessionid,
        cookie_header=body.cookie_header,
    )
    client = LinkedInClient(session, timeout=settings.request_timeout_seconds)

    try:
        me = await client.validate()
    except SessionDead as exc:
        raise fail(422, "linkedin_session_invalid", str(exc)) from exc
    except RateLimited as exc:
        raise fail(429, "rate_limited", str(exc)) from exc
    except LinkedInError as exc:
        raise fail(502, "linkedin_unexpected_response", str(exc)) from exc

    name, public_id = None, None
    for obj in me.get("included") or []:
        if "firstName" in obj:
            name = " ".join(filter(None, [obj.get("firstName"), obj.get("lastName")]))
            public_id = obj.get("publicIdentifier")
            break

    key = store.mint(
        li_at=body.li_at,
        jsessionid=body.jsessionid or session.csrf_token,
        member_name=name,
        member_public_id=public_id,
    )

    return AuthResponse(
        api_key=key,
        linkedin_member={"name": name, "public_id": public_id},
        created_at=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/v1/profile", response_model=ProfileCore, tags=["profile"])
async def get_profile(
    url: str = Query(..., description="A LinkedIn profile URL, or a bare public id"),
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    store: KeyStore = Depends(get_store),
    settings: Settings = Depends(get_settings),
) -> ProfileCore:
    """Fetch a LinkedIn profile as structured JSON."""
    # Public demo mode: with no key, fall back to the bootstrap session so a
    # reviewer can call the API with no key at all. Every keyless request then
    # shares the bootstrap key's rate-limit bucket, which protects the account.
    if not x_api_key and settings.public_demo and settings.bootstrap_api_key:
        x_api_key = settings.bootstrap_api_key

    if not x_api_key:
        raise fail(401, "missing_api_key", "Send your key in the X-API-Key header.")

    session_row = store.lookup(x_api_key)
    if session_row is None:
        raise fail(401, "invalid_api_key", "That key is unknown or revoked.")

    allowed, why = limiter.check(
        x_api_key, settings.rate_limit_per_minute, settings.rate_limit_per_day
    )
    if not allowed:
        raise fail(429, "rate_limited", why)

    try:
        ref = parse_profile_url(url)
    except InvalidProfileUrl as exc:
        raise fail(400, "invalid_profile_url", str(exc)) from exc

    session = LinkedInSession(
        li_at=session_row.li_at,
        jsessionid=session_row.jsessionid,
        cookie_header=settings.bootstrap_cookie_header
        if session_row.is_bootstrap
        else None,
    )
    client = LinkedInClient(session, timeout=settings.request_timeout_seconds)

    started = time.monotonic()

    try:
        raw = await client.fetch_core_profile(ref.public_id)
        core = parse_dash_profile(raw)
    except SessionDead as exc:
        raise fail(403, "linkedin_session_dead", str(exc)) from exc
    except ProfileNotFound as exc:
        raise fail(404, "profile_not_found", str(exc)) from exc
    except RateLimited as exc:
        raise fail(429, "rate_limited", str(exc)) from exc
    except ProfileNotInResponse as exc:
        raise fail(404, "profile_not_found", str(exc)) from exc
    except LinkedInError as exc:
        raise fail(502, "linkedin_unexpected_response", str(exc)) from exc

    # Sections come from two further sources, fetched at the same time since
    # neither depends on the other. Both are allowed to fail: a partial
    # profile beats no profile, and meta says what is missing.
    node, page = await asyncio.gather(
        client.fetch_public_jsonld(ref.public_id),
        client.fetch_experience_page(ref.public_id),
        return_exceptions=True,
    )

    public = None
    if isinstance(node, dict):
        try:
            public = parse_person(node)
        except (NoPersonInJsonLd, ValueError):
            public = None

    experience = None
    if isinstance(page, str):
        try:
            experience = parse_experience_page(page)
        except ValueError:
            experience = None

    profile = merge_profile(core, public, experience)
    profile.profile_url = ref.canonical_url
    profile.meta["fetched_at"] = datetime.now(timezone.utc).isoformat()
    profile.meta["duration_ms"] = int((time.monotonic() - started) * 1000)
    return profile
