"""Throwaway probe harness.

Hard rules, learned by burning four sessions:
  * never follow a redirect
  * send the full browser cookie set and Chrome's real headers, so the
    request is indistinguishable from the browser's
  * only request URLs the real app requests
  * abort the instant LinkedIn signals a dead session
  * cache every response, so one live request serves all later work
"""
import hashlib
import json
import pathlib
import sys

import httpx

env = {}
for line in pathlib.Path(".env.local").read_text().splitlines():
    line = line.strip()
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()

COOKIE_HEADER = env.get("COOKIE_HEADER", "").strip()


def _cookies_from_header(h):
    out = {}
    for part in h.split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
    return out


if COOKIE_HEADER:
    COOKIES = _cookies_from_header(COOKIE_HEADER)
    FULL_JAR = True
else:
    COOKIES = {"li_at": env["LI_AT"], "JSESSIONID": f'"{env["JSESSIONID"].strip(chr(34))}"'}
    FULL_JAR = False

JSESSIONID = COOKIES.get("JSESSIONID", "").strip('"')
if not JSESSIONID:
    sys.exit("no JSESSIONID in the cookie set — cannot build a csrf token")

UA = env.get("USER_AGENT") or (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"
)

print(f"cookie jar: {len(COOKIES)} cookies "
      f"{'(FULL browser set)' if FULL_JAR else '(minimal — API routes only)'}")

# Chrome's client hints. LinkedIn checks these on document requests.
CLIENT_HINTS = {
    "sec-ch-ua": '"Not=A?Brand";v="99", "Google Chrome";v="151", "Chromium";v="151"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
}

# Headers for /voyager/api/ calls — what the web app's XHRs send.
API_HEADERS = {
    "user-agent": UA,
    "accept": "application/vnd.linkedin.normalized+json+2.1",
    "accept-language": "en-US,en;q=0.9",
    "csrf-token": JSESSIONID,
    "x-restli-protocol-version": "2.0.0",
    "x-li-lang": "en_US",
    "referer": "https://www.linkedin.com/feed/",
    **CLIENT_HINTS,
}

# Headers for a page request — copied from Chrome's real navigation.
DOC_HEADERS = {
    "user-agent": UA,
    "accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,"
               "image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"),
    "accept-language": "en-US,en;q=0.9",
    "priority": "u=0, i",
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "none",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
    **CLIENT_HINTS,
}


def client(doc=False):
    return httpx.Client(
        headers=DOC_HEADERS if doc else API_HEADERS,
        cookies=COOKIES,
        timeout=45.0,
        follow_redirects=False,
        max_redirects=0,
    )


def _guard(url):
    """Refuse to send a minimal cookie set at a route that revokes it."""
    if "/voyager/api/" in url:
        return
    if not FULL_JAR:
        raise RuntimeError(
            f"BLOCKED: {url}\n"
            "  Only /voyager/api/ routes are safe with a minimal cookie set.\n"
            "  LinkedIn revokes the session on HTML routes. Set COOKIE_HEADER first."
        )


def session_dead(r):
    return "delete me" in r.headers.get("set-cookie", "")


CACHE = pathlib.Path(".cache/linkedin")


def cached_get(c, label, url, params=None, headers=None, show_chars=500, force=False):
    _guard(url)
    key = hashlib.sha256(f"{url}|{sorted((params or {}).items())}".encode()).hexdigest()[:16]
    path = CACHE / f"{key}.json"
    if path.exists() and not force:
        blob = json.loads(path.read_text())
        print(f"\n--- {label}  [CACHED]\nHTTP {blob['status']}  len={len(blob['body'])}")
        print(blob["body"][:show_chars])
        return blob

    r = c.get(url, params=params, headers=headers or {})
    if session_dead(r):
        print(f"\n--- {label}\n!! SESSION DEAD — not caching. Stopping.")
        sys.exit(2)

    blob = {"label": label, "url": str(r.url), "status": r.status_code,
            "headers": dict(r.headers), "body": r.text}
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(blob, indent=2))
    print(f"\n--- {label}  [FETCHED]\nHTTP {r.status_code}  len={len(r.text)}")
    if r.status_code in (301, 302, 303, 307, 308):
        print("redirect ->", r.headers.get("location", "")[:160])
    print(r.text[:show_chars])
    return blob


get = cached_get
