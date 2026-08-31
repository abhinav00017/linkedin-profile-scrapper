"""Fetch the server-rendered profile page and find the embedded data.

One plain HTTP GET with Chrome's exact cookies and headers. No browser.
"""
exec(open("scripts/probe.py").read())

import re

TARGET = "williamhgates"

with client(doc=True) as c:
    blob = cached_get(c, f"profile page /in/{TARGET}/",
                      f"https://www.linkedin.com/in/{TARGET}/", show_chars=200)

body = blob["body"]
print(f"\n=== page: HTTP {blob['status']}, {len(body)} bytes ===")

if blob["status"] != 200:
    raise SystemExit(f"not a 200 — got {blob['status']}")

# LinkedIn ships its data inside <code> elements the JS reads on boot.
codes = re.findall(r'<code[^>]*id="([^"]+)"[^>]*>(.*?)</code>', body, re.DOTALL)
print(f"<code> blocks: {len(codes)}")

MARKERS = ("profilePositionGroup", "profileEducation", "profileSkill",
           "profileCertification", "profileLanguage", "EXPERIENCE", "EDUCATION",
           "fsd_profile", "Profile")

interesting = []
for cid, content in codes:
    hits = [m for m in MARKERS if m in content]
    if hits:
        interesting.append((cid, len(content), hits))

print(f"\nblocks mentioning profile data: {len(interesting)}")
for cid, size, hits in sorted(interesting, key=lambda x: -x[1])[:15]:
    print(f"  {cid:34} {size:8} bytes  {hits[:5]}")

out = pathlib.Path(".cache/page_blocks")
out.mkdir(parents=True, exist_ok=True)
import html as _html
saved = 0
for cid, content in codes:
    text = _html.unescape(content)
    try:
        json.loads(text)
    except Exception:
        continue
    (out / f"{cid}.json").write_text(text)
    saved += 1
print(f"\n{saved} blocks parsed as JSON -> {out}/")
