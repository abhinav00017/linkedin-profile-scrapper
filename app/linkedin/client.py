"""HTTP client for LinkedIn.

Plain HTTP only. No browser, no headless anything.

Two rules earned the hard way, by losing four sessions:

  * Send the whole browser cookie set at page routes. LinkedIn revokes a
    session that arrives at an HTML route with only li_at and JSESSIONID.
  * Only request paths LinkedIn's own clients request. An invented path
    reads as probing and gets the session revoked.
"""
from __future__ import annotations

import asyncio
import html as htmllib
import json
import time
import re
from dataclasses import dataclass

import httpx

VOYAGER = "https://www.linkedin.com/voyager/api"

CHROME_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"
)

CLIENT_HINTS = {
    "sec-ch-ua": '"Not=A?Brand";v="99", "Google Chrome";v="151", "Chromium";v="151"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
}

DOC_ACCEPT = (
    "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,"
    "image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
)

JSON_LD = re.compile(
    r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', re.DOTALL
)


class LinkedInError(RuntimeError):
    """Base for anything that went wrong talking to LinkedIn."""


class SessionDead(LinkedInError):
    """LinkedIn revoked the session. The caller must authenticate again."""


class RateLimited(LinkedInError):
    """LinkedIn is throttling us."""


class ProfileNotFound(LinkedInError):
    """No such profile, or this session may not see it."""


class _TimedCache:
    """Small in-process cache with a time to live.

    The public page is throttled aggressively, so holding a good answer for a
    while is the difference between returning sections and returning none.
    """

    def __init__(self, ttl_seconds: float = 3600.0, max_entries: int = 500) -> None:
        self._ttl = ttl_seconds
        self._max = max_entries
        self._entries: dict[str, tuple[float, dict]] = {}

    def get(self, key: str) -> dict | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        stored_at, value = entry
        if time.monotonic() - stored_at > self._ttl:
            self._entries.pop(key, None)
            return None
        return value

    def put(self, key: str, value: dict) -> None:
        if len(self._entries) >= self._max:
            oldest = min(self._entries, key=lambda k: self._entries[k][0])
            self._entries.pop(oldest, None)
        self._entries[key] = (time.monotonic(), value)


_PUBLIC_CACHE = _TimedCache()


@dataclass(frozen=True)
class LinkedInSession:
    li_at: str
    jsessionid: str | None = None
    cookie_header: str | None = None

    def cookies(self) -> dict[str, str]:
        """Prefer the full browser cookie set when we have one."""
        if self.cookie_header:
            out = {}
            for part in self.cookie_header.split(";"):
                if "=" in part:
                    k, v = part.split("=", 1)
                    out[k.strip()] = v.strip()
            return out
        jar = {"li_at": self.li_at}
        if self.jsessionid:
            jar["JSESSIONID"] = f'"{self.jsessionid.strip(chr(34))}"'
        return jar

    @property
    def csrf_token(self) -> str | None:
        if self.jsessionid:
            return self.jsessionid.strip('"')
        jar = self.cookies()
        value = jar.get("JSESSIONID")
        return value.strip('"') if value else None

    @property
    def has_full_cookie_jar(self) -> bool:
        return len(self.cookies()) > 5


def _session_was_revoked(response: httpx.Response) -> bool:
    """LinkedIn clears li_at when it decides a session is not genuine."""
    return "delete me" in response.headers.get("set-cookie", "")


class LinkedInClient:
    def __init__(self, session: LinkedInSession, timeout: float = 30.0) -> None:
        self.session = session
        self._timeout = timeout

    def _api_headers(self) -> dict[str, str]:
        headers = {
            "user-agent": CHROME_UA,
            "accept": "application/vnd.linkedin.normalized+json+2.1",
            "accept-language": "en-US,en;q=0.9",
            "x-restli-protocol-version": "2.0.0",
            "x-li-lang": "en_US",
            "referer": "https://www.linkedin.com/feed/",
            **CLIENT_HINTS,
        }
        if self.session.csrf_token:
            headers["csrf-token"] = self.session.csrf_token
        return headers

    def _doc_headers(self) -> dict[str, str]:
        return {
            "user-agent": CHROME_UA,
            "accept": DOC_ACCEPT,
            "accept-language": "en-US,en;q=0.9",
            "priority": "u=0, i",
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "none",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
            **CLIENT_HINTS,
        }

    def _check(self, r: httpx.Response) -> None:
        if _session_was_revoked(r):
            raise SessionDead(
                "LinkedIn revoked this session. Authenticate again with a fresh cookie."
            )
        if r.status_code == 999:
            raise RateLimited("LinkedIn is throttling this client (HTTP 999).")
        if r.status_code == 429:
            raise RateLimited("LinkedIn rate limit (HTTP 429).")

    async def validate(self) -> dict:
        """Confirm the session works. Used before we mint an API key."""
        async with httpx.AsyncClient(
            headers=self._api_headers(), cookies=self.session.cookies(),
            timeout=self._timeout, follow_redirects=False,
        ) as c:
            r = await c.get(f"{VOYAGER}/me")
            self._check(r)
            if r.status_code != 200:
                raise SessionDead(
                    f"LinkedIn refused the session check (HTTP {r.status_code})."
                )
            return r.json()

    async def fetch_core_profile(self, public_id: str) -> dict:
        """The authenticated read. Full, unmasked, but core fields only."""
        async with httpx.AsyncClient(
            headers=self._api_headers(), cookies=self.session.cookies(),
            timeout=self._timeout, follow_redirects=False,
        ) as c:
            r = await c.get(
                f"{VOYAGER}/identity/dash/profiles",
                params={"q": "memberIdentity", "memberIdentity": public_id},
            )
            self._check(r)
            if r.status_code == 404:
                raise ProfileNotFound(f"no profile at /in/{public_id}")
            if r.status_code != 200:
                raise LinkedInError(
                    f"unexpected status {r.status_code} from the profile endpoint"
                )
            return r.json()

    async def fetch_experience_page(self, public_id: str) -> str | None:
        """The /details/experience/ page, which LinkedIn server-renders.

        This is the richest source we can reach without a browser: titles,
        companies, employment types, dates, locations and descriptions, all
        unmasked. Sent with the full cookie jar, because a page route with a
        thin cookie set gets the session revoked.
        """
        url = f"https://www.linkedin.com/in/{public_id}/details/experience/"
        async with httpx.AsyncClient(
            headers=self._doc_headers(), cookies=self.session.cookies(),
            timeout=self._timeout, follow_redirects=False,
        ) as c:
            r = await c.get(url)
            self._check(r)
            return r.text if r.status_code == 200 else None

    async def fetch_public_jsonld(self, public_id: str, attempts: int = 3) -> dict | None:
        """The logged-out read. Adds experience and education.

        Sent with NO cookies on purpose: this is the renderer LinkedIn gives
        search engines, and it is the only place the sections appear as data.

        LinkedIn throttles this route hard, answering 999 for minutes at a
        time. We cache what we get so a throttle does not erase a profile we
        already read, and we give up quietly rather than fail the request.
        """
        cached = _PUBLIC_CACHE.get(public_id)
        if cached is not None:
            return cached

        url = f"https://www.linkedin.com/in/{public_id}/"
        delay = 2.0

        async with httpx.AsyncClient(
            headers=self._doc_headers(), timeout=self._timeout, follow_redirects=True
        ) as c:
            for attempt in range(attempts):
                r = await c.get(url)
                if r.status_code == 200:
                    person = self._extract_person(r.text)
                    if person:
                        _PUBLIC_CACHE.put(public_id, person)
                    return person
                if r.status_code in (999, 429):
                    if attempt == attempts - 1:
                        return None
                    await asyncio.sleep(delay)
                    delay *= 2
                    continue
                return None
        return None

    @staticmethod
    def _extract_person(page: str) -> dict | None:
        for raw in JSON_LD.findall(page):
            try:
                doc = json.loads(htmllib.unescape(raw.strip()))
            except json.JSONDecodeError:
                continue
            nodes = doc.get("@graph") if isinstance(doc, dict) else None
            if nodes is None:
                nodes = doc if isinstance(doc, list) else [doc]
            for node in nodes:
                if isinstance(node, dict) and node.get("@type") == "Person":
                    return node
        return None
