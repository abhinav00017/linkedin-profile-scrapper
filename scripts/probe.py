"""Throwaway probe harness.

Hard rules, learned by burning two sessions:
  * never follow a redirect
  * never send the session at an HTML document route unless we hold a full
    browser cookie set — LinkedIn revokes the session when we do
  * abort the instant LinkedIn signals a dead session
  * cache every response, so one live request serves all later work
"""
import hashlib, json, pathlib, sys
import httpx

env = {}
for line in pathlib.Path(".env.local").read_text().splitlines():
    line = line.strip()
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()

COOKIE_HEADER = env.get("COOKIE_HEADER", "").strip()

def _cookies_from_header(h: str) -> dict:
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

print(f"cookie jar: {len(COOKIES)} cookies {'(FULL browser set)' if FULL_JAR else '(minimal — API routes only)'}")

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

API_HEADERS = {
    "user-agent": UA,
    "accept": "application/vnd.linkedin.normalized+json+2.1",
    "accept-language": "en-US,en;q=0.9",
    "csrf-token": JSESSIONID,
    "x-restli-protocol-version": "2.0.0",
    "x-li-lang": "en_US",
    "referer": "https://www.linkedin.com/feed/",
}

def client():
    return httpx.Client(headers=API_HEADERS, cookies=COOKIES, timeout=30.0,
                        follow_redirects=False, max_redirects=0)

def _guard(url: str) -> None:
    """Refuse to send the session anywhere that revokes it."""
    if "/voyager/api/" in url:
        return
    if not FULL_JAR:
        raise RuntimeError(
            f"BLOCKED: {url}\n"
            "  Only /voyager/api/ routes are safe with a minimal cookie set.\n"
            "  LinkedIn revokes the session on HTML routes. Supply COOKIE_HEADER first."
        )

def session_dead(r) -> bool:
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
