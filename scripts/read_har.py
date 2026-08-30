"""Pull LinkedIn's own API calls out of a HAR export.

Prints every voyager request the browser made: URL, query ids, and what came
back. This is how we learn the real request shapes instead of guessing at
them, which is what kept getting sessions revoked.
"""
import json
import pathlib
import sys
from urllib.parse import urlparse, parse_qs

path = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "har/linkedin.har")
if not path.exists():
    sys.exit(f"no HAR at {path}")

har = json.loads(path.read_text())
entries = har["log"]["entries"]
print(f"{len(entries)} requests in the HAR\n")

voyager = [e for e in entries if "/voyager/api/" in e["request"]["url"]]
print(f"{len(voyager)} voyager API calls")
print("=" * 78)

OUT = pathlib.Path(".cache/har")
OUT.mkdir(parents=True, exist_ok=True)

for i, e in enumerate(voyager):
    req, res = e["request"], e["response"]
    u = urlparse(req["url"])
    q = parse_qs(u.query)
    size = res["content"].get("size", 0)
    print(f"\n[{i:02}] {req['method']} {u.path}")
    print(f"     status {res['status']}   {size} bytes")
    for k in ("queryId", "q", "variables", "includeWebMetadata", "decorationId"):
        if k in q:
            print(f"     {k} = {q[k][0][:150]}")
    body = res["content"].get("text", "")
    if body:
        name = u.path.strip("/").replace("/", "_")[:60]
        (OUT / f"{i:02}_{name}.json").write_text(body)

print(f"\n\nbodies saved to {OUT}/")

print("\n=== calls whose response mentions a profile section ===")
MARKERS = ("EXPERIENCE", "EDUCATION", "SKILL", "CERTIFICATION", "LANGUAGE",
           "profilePositionGroup", "profileEducation", "profileSkill")
for i, e in enumerate(voyager):
    body = e["response"]["content"].get("text", "") or ""
    hits = [w for w in MARKERS if w in body]
    if hits:
        u = urlparse(e["request"]["url"])
        qid = parse_qs(u.query).get("queryId", [""])[0]
        print(f"  [{i:02}] {u.path[-55:]:55} {qid[:45]:45} {hits[:4]}")

print("\n=== request headers LinkedIn's web app sends ===")
if voyager:
    for h in voyager[0]["request"]["headers"]:
        if h["name"].lower() in ("accept", "csrf-token", "x-restli-protocol-version",
                                 "x-li-lang", "x-li-track", "x-li-page-instance",
                                 "user-agent", "referer", "sec-fetch-site",
                                 "sec-fetch-mode", "sec-fetch-dest"):
            print(f"  {h['name']}: {h['value'][:120]}")
