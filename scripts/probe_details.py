"""Fetch the profile detail pages and see how parseable they are.

These are real navigation URLs — the ones LinkedIn's own "Show all …" links
point at. Plain GET, full cookie jar, no browser.
"""
exec(open("scripts/probe.py").read())

import re

TARGET = "williamhgates"
SECTIONS = ["experience", "skills"]

for section in SECTIONS:
    url = f"https://www.linkedin.com/in/{TARGET}/details/{section}/"
    with client(doc=True) as c:
        blob = cached_get(c, f"details/{section}", url, show_chars=120)

    body = blob["body"]
    print(f"\n=== {section}: HTTP {blob['status']}, {len(body)} bytes")
    if blob["status"] != 200:
        continue

    # Accessibility duplicates are the stable handle: LinkedIn renders the
    # true text once visibly and once for screen readers.
    hidden = re.findall(r'<span class="[^"]*visually-hidden[^"]*"[^>]*>(.*?)</span>',
                        body, re.DOTALL)
    print(f"  visually-hidden spans: {len(hidden)}")
    for h in hidden[:12]:
        text = re.sub(r"<[^>]+>", "", h).strip()
        if text:
            print(f"     {text[:80]}")

    # aria-hidden marks the visible copy of the same text
    aria = re.findall(r'aria-hidden="true"[^>]*>([^<]{2,90})<', body)
    print(f"  aria-hidden texts: {len(aria)}")
    for a in aria[:12]:
        if a.strip():
            print(f"     {a.strip()[:80]}")

    for probe in ("Gates Foundation", "Breakthrough Energy", "Microsoft",
                  "Harvard", "Lakeside"):
        print(f"  contains {probe!r}: {probe in body}")
