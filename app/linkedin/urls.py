"""Turn anything a user might paste into a LinkedIn public id."""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import unquote, urlparse

MAX_PUBLIC_ID_LEN = 100

# /in/<public-id> anywhere in the path, on any linkedin subdomain
_PROFILE_PATH = re.compile(r"/in/(?P<public_id>[^/?#]+)", re.IGNORECASE)
# a bare public id: letters, digits, hyphens, unicode word chars
_BARE_ID = re.compile(r"^[\w\-À-ɏ]+$", re.UNICODE)


class InvalidProfileUrl(ValueError):
    """The input is not a LinkedIn profile URL."""


@dataclass(frozen=True)
class ProfileRef:
    public_id: str
    canonical_url: str


def _is_linkedin_host(host: str) -> bool:
    host = host.lower().removeprefix("www.")
    return host == "linkedin.com" or host.endswith(".linkedin.com")


def parse_profile_url(raw: str) -> ProfileRef:
    if not raw or not raw.strip():
        raise InvalidProfileUrl("empty input")

    value = raw.strip()

    # A bare public id, e.g. "jane-doe"
    if "/" not in value and "." not in value:
        return _build(value)

    # Give urlparse a scheme so "linkedin.com/in/x" parses as a host, not a path
    with_scheme = value if "://" in value else f"https://{value}"
    parts = urlparse(with_scheme)

    if not _is_linkedin_host(parts.netloc):
        raise InvalidProfileUrl(f"not a linkedin.com URL: {parts.netloc or raw!r}")

    match = _PROFILE_PATH.search(parts.path)
    if not match:
        raise InvalidProfileUrl(
            "not a profile URL — expected /in/<public-id>. "
            "Company, school, job and post URLs are not supported."
        )

    return _build(match.group("public_id"))


def _build(public_id: str) -> ProfileRef:
    public_id = unquote(public_id).strip()

    if not public_id or not _BARE_ID.match(public_id):
        raise InvalidProfileUrl(f"invalid public id: {public_id!r}")
    if len(public_id) > MAX_PUBLIC_ID_LEN:
        raise InvalidProfileUrl(f"public id too long ({len(public_id)} chars)")

    return ProfileRef(
        public_id=public_id,
        canonical_url=f"https://www.linkedin.com/in/{public_id}/",
    )
