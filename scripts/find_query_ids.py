"""Extract profile-section GraphQL query ids from LinkedIn's JS bundles.

The bundles are static CDN files. We fetch them with NO cookies, so this
cannot put the session at risk however many we download.
"""
import json
import pathlib
import re

import httpx

# the cached profile page tells us which bundles the app loads
page = None
for p in pathlib.Path(".cache/linkedin").glob("*.json"):
    blob = json.loads(p.read_text())
    if "/in/" in blob["url"] and blob["status"] == 200:
        page = blob["body"]
        break
if page is None:
    raise SystemExit("no cached profile page — run scripts/probe_html.py first")

srcs = set(re.findall(r'https://static\.licdn\.com/[^"\'\s\\]+\.js', page))
print(f"{len(srcs)} bundle URLs referenced by the page")

# profile-related bundles first; fall back to everything if none match
profile_first = sorted(srcs, key=lambda u: (0 if "profile" in u.lower() else 1, len(u)))

CACHE = pathlib.Path(".cache/bundles")
CACHE.mkdir(parents=True, exist_ok=True)

QUERY_ID = re.compile(r'"(voyager[A-Za-z]+\.[0-9a-f]{32})"')
INTERESTING = ("ProfileCards", "ProfileComponents", "ProfileCard", "Position",
               "Education", "Skill", "Certification", "Language", "Profile")

found = {}
client = httpx.Client(timeout=30.0, follow_redirects=True,
                      headers={"user-agent": "Mozilla/5.0", "accept": "*/*"})

for i, url in enumerate(profile_first[:40]):
    name = url.rsplit("/", 1)[-1]
    dest = CACHE / name
    try:
        if dest.exists():
            text = dest.read_text(errors="ignore")
        else:
            r = client.get(url)          # no cookies — static asset
            if r.status_code != 200:
                print(f"  [{i:02}] {r.status_code} {name}")
                continue
            text = r.text
            dest.write_text(text, errors="ignore")
    except Exception as exc:
        print(f"  [{i:02}] failed {name}: {exc}")
        continue

    ids = set(QUERY_ID.findall(text))
    hits = {q for q in ids if any(k in q for k in INTERESTING)}
    if hits:
        print(f"  [{i:02}] {name[:52]:52} {len(ids):4} ids, {len(hits)} profile-ish")
        for q in sorted(hits):
            found.setdefault(q, name)

client.close()

print("\n" + "=" * 74)
print("PROFILE-RELATED QUERY IDS")
print("=" * 74)
for q in sorted(found):
    print(f"  {q}")

out = pathlib.Path(".cache/query_ids.json")
out.write_text(json.dumps(found, indent=2))
print(f"\n{len(found)} ids -> {out}")
