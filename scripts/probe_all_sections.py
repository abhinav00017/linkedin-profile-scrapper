"""Fetch every detail page for a profile that has all the sections filled in.

Real navigation URLs, plain GET, full cookie jar. Everything is cached, so
this costs one request per page and never repeats.
"""
exec(open("scripts/probe.py").read())

import html as htmllib
import re
import sys

TARGET = sys.argv[1] if len(sys.argv) > 1 else "uday-karanam"
SECTIONS = ["experience", "education", "skills", "certifications", "languages"]

BOUNDARIES = ("Ad Options", "More profiles for you", "About\nAccessibility",
              "Why am I seeing this ad?")


def readable(body):
    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", body, flags=re.DOTALL | re.I)
    t = re.sub(r"<[^>]+>", "\n", t)
    t = htmllib.unescape(t)
    return [ln.strip() for ln in t.split("\n") if ln.strip()]


print(f"target: {TARGET}\n")

for section in SECTIONS:
    url = f"https://www.linkedin.com/in/{TARGET}/details/{section}/"
    with client(doc=True) as c:
        blob = cached_get(c, f"details/{section}", url, show_chars=0)

    print(f"\n{'=' * 70}\n{section.upper()}   HTTP {blob['status']}  {len(blob['body'])} bytes")
    if blob["status"] != 200:
        continue

    lines = readable(blob["body"])

    # the section content sits between its heading and the ad block
    heading = section.capitalize()
    aliases = {"experience": ["Experience"], "education": ["Education"],
               "skills": ["Skills"],
               "certifications": ["Licenses & certifications", "Certifications"],
               "languages": ["Languages"]}
    start = None
    for alias in aliases[section]:
        if alias in lines:
            start = lines.index(alias)
            break
    if start is None:
        print("  heading not found — first 15 lines:")
        for ln in lines[:15]:
            print(f"     {ln[:76]}")
        continue

    end = len(lines)
    for i in range(start + 1, len(lines)):
        if lines[i] in ("Ad Options", "More profiles for you", "About"):
            end = i
            break

    content = lines[start + 1:end]
    print(f"  {len(content)} content lines:")
    for ln in content:
        print(f"     {ln[:76]}")
