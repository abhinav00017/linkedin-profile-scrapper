"""The response schema. This is what callers of the API get back."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Name(BaseModel):
    first: str | None = None
    last: str | None = None
    full: str


class Location(BaseModel):
    country_code: str | None = None
    geo_urn: str | None = None
    name: str | None = None


class Images(BaseModel):
    profile: str | None = None
    background: str | None = None


class Website(BaseModel):
    category: str | None = None
    url: str


class DateParts(BaseModel):
    """A LinkedIn date. The month and day are often absent."""

    year: int | None = None
    month: int | None = None
    day: int | None = None


class Experience(BaseModel):
    title: str | None = None
    company: str | None = None
    company_url: str | None = None
    location: str | None = None
    employment_type: str | None = None
    start: DateParts | None = None
    end: DateParts | None = None
    is_current: bool = False
    description: str | None = None


class Education(BaseModel):
    school: str | None = None
    degree: str | None = None
    field_of_study: str | None = None
    start: DateParts | None = None
    end: DateParts | None = None
    description: str | None = None


class Skill(BaseModel):
    name: str
    endorsement_count: int | None = None


class Certification(BaseModel):
    name: str | None = None
    authority: str | None = None
    issued: DateParts | None = None
    url: str | None = None


class Language(BaseModel):
    name: str
    proficiency: str | None = None


class Meta(BaseModel):
    strategy: str
    fetched_at: datetime
    duration_ms: int | None = None
    partial: bool = False
    missing_sections: list[str] = Field(default_factory=list)


class Profile(BaseModel):
    profile_url: str
    public_id: str
    urn: str | None = None
    member_urn: str | None = None

    name: Name
    headline: str | None = None
    about: str | None = None
    location: Location = Field(default_factory=Location)
    images: Images = Field(default_factory=Images)
    websites: list[Website] = Field(default_factory=list)

    experience: list[Experience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    skills: list[Skill] = Field(default_factory=list)
    certifications: list[Certification] = Field(default_factory=list)
    languages: list[Language] = Field(default_factory=list)

    is_influencer: bool = False
    is_premium: bool = False

    # Internal: urns the section fetches need. Not part of the public response.
    card_urns: dict[str, str] = Field(default_factory=dict, exclude=True)

    meta: Meta | None = None


class AuthRequest(BaseModel):
    li_at: str = Field(min_length=20, description="The li_at cookie from a logged-in LinkedIn session")
    jsessionid: str | None = Field(default=None, description="The JSESSIONID cookie, if you have it")
    cookie_header: str | None = Field(default=None, description="A full cookie header, as an alternative to the two above")


class AuthResponse(BaseModel):
    api_key: str
    linkedin_member: dict[str, str | None]
    created_at: datetime


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody


ErrorCode = Literal[
    "invalid_profile_url",
    "invalid_api_key",
    "linkedin_session_dead",
    "profile_not_found",
    "rate_limited",
    "linkedin_unexpected_response",
]
