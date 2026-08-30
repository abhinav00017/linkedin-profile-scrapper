"""Throwaway probe harness. Never follows redirects. Aborts the moment
LinkedIn signals a dead session, so one bad cookie cannot cascade."""
import json, pathlib, sys
import httpx

env = {}
for line in pathlib.Path(".env.local").read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()

LI_AT, JSESSIONID = env["LI_AT"], env["JSESSIONID"].strip('"')

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
    return httpx.Client(
        headers=API_HEADERS,
        cookies={"li_at": LI_AT, "JSESSIONID": f'"{JSESSIONID}"'},
        timeout=30.0,
        follow_redirects=False,   # never loop
        max_redirects=0,
    )

def session_dead(r) -> bool:
    return "delete me" in r.headers.get("set-cookie", "")

def get(c, label, url, params=None, headers=None, show_chars=500):
    r = c.get(url, params=params, headers=headers or {})
    print(f"\n--- {label}\nHTTP {r.status_code}  len={len(r.content)}")
    if session_dead(r):
        print("!! SESSION DEAD — LinkedIn cleared li_at. Stopping so we don't burn it further.")
        sys.exit(2)
    if r.status_code in (301, 302, 303, 307, 308):
        print("redirect ->", r.headers.get("location", "")[:160])
        return r
    try:
        print(json.dumps(r.json(), indent=2)[:show_chars])
    except Exception:
        print(r.text[:show_chars])
    return r


# ---- disk cache: each distinct call hits LinkedIn at most once -------------
import hashlib, os

CACHE = pathlib.Path(".cache/linkedin")

def cached_get(c, label, url, params=None, headers=None, show_chars=500, force=False):
    """Fetch once, then replay from disk forever. Saves status, headers, body."""
    key = hashlib.sha256(f"{url}|{sorted((params or {}).items())}".encode()).hexdigest()[:16]
    path = CACHE / f"{key}.json"
    if path.exists() and not force:
        blob = json.loads(path.read_text())
        print(f"\n--- {label}  [CACHED {path.name}]\nHTTP {blob['status']}  len={len(blob['body'])}")
        print(blob["body"][:show_chars])
        return blob

    r = c.get(url, params=params, headers=headers or {})
    if session_dead(r):
        print(f"\n--- {label}\n!! SESSION DEAD — not caching. Stopping.")
        sys.exit(2)

    blob = {
        "label": label, "url": str(r.url), "status": r.status_code,
        "headers": dict(r.headers), "body": r.text,
    }
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(blob, indent=2))
    print(f"\n--- {label}  [FETCHED -> {path.name}]\nHTTP {r.status_code}  len={len(r.text)}")
    if r.status_code in (301, 302, 303, 307, 308):
        print("redirect ->", r.headers.get("location", "")[:160])
    print(r.text[:show_chars])
    return blob
