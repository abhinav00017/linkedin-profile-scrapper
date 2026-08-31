"""Try the dash section finders, one at a time, stopping at the first sign of trouble.

These use restli's standard finder shape (?q=viewee&profileUrn=...), which is
what LinkedIn's own clients use — not a path I invented. Every response is
cached, and the harness exits the moment LinkedIn signals a dead session.
"""
exec(open("scripts/probe.py").read())

from urllib.parse import quote

PID = "ACoAAA8BYqEBCGLg_vT_ca6mMEqkpp9nVffJ3hc"      # williamhgates
URN = quote(f"urn:li:fsd_profile:{PID}", safe="")
V = "https://www.linkedin.com/voyager/api/identity/dash"

SECTIONS = [
    ("experience", "profilePositionGroups"),
    ("education", "profileEducations"),
    ("skills", "profileSkills"),
    ("certifications", "profileCertifications"),
    ("languages", "profileLanguages"),
]

results = {}

with client() as c:
    for label, entity in SECTIONS:
        url = f"{V}/{entity}?q=viewee&profileUrn={URN}&count=50"
        blob = cached_get(c, f"{label}: {entity}", url, show_chars=220)
        results[label] = blob

print("\n\n" + "=" * 74)
print("SECTION SUMMARY")
print("=" * 74)
for label, blob in results.items():
    status, n = blob["status"], len(blob["body"])
    if status == 200 and n > 300:
        try:
            inc = json.loads(blob["body"]).get("included", [])
            kinds = {o.get("$type", "?").split(".")[-1] for o in inc}
            print(f"  {label:16} DATA      {n:7} bytes  {len(inc)} objects  {sorted(kinds)[:4]}")
        except Exception:
            print(f"  {label:16} 200 but unparseable  {n} bytes")
    else:
        print(f"  {label:16} HTTP {status}  {n} bytes")
