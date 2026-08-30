"""The shape we return to callers.

Deliberately not LinkedIn's shape. LinkedIn returns a normalised graph built
for their own UI; callers want a flat, predictable document.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Name(BaseModel):
    first: str | None = None
    last: str | None = None
    full: str | None = None


class Location(BaseModel):
    country_code: str | None = None
    locality: str | None = None
    geo_urn: str | None = None


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
    name: str
    authority: str | None = None
    issued: DateParts | None = None
    url: str | None = None


class Language(BaseModel):
    name: str
    proficiency: str | None = None


class ProfileCore(BaseModel):
    """Everything the core profile call gives us.

    Sections arrive separately, so they default empty rather than missing.
    """

    profile_url: str | None = None
    public_id: str | None = None
    urn: str | None = None
    name: Name = Field(default_factory=Name)
    headline: str | None = None
    about: str | None = None
    location: Location = Field(default_factory=Location)
    images: Images = Field(default_factory=Images)
    websites: list[Website] = Field(default_factory=list)
    industry_urn: str | None = None
    is_premium: bool = False
    is_influencer: bool = False

    # urns we need to fetch the sections with
    card_urns: dict[str, str] = Field(default_factory=dict)

    experience: list[Experience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    skills: list[Skill] = Field(default_factory=list)
    certifications: list[Certification] = Field(default_factory=list)
    languages: list[Language] = Field(default_factory=list)

    meta: dict[str, Any] = Field(default_factory=dict)
