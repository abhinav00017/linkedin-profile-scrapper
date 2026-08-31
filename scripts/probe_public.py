"""Fetch the logged-out public profile and look for JSON-LD.

No cookies at all. This cannot affect the session, and it is the renderer
LinkedIn serves to search engines, which carries structured data.
"""
import html as htmllib
import json
import pathlib
import re
import sys

import httpx

TARGETS = ["williamhgates", "sundarpichai"]

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36")

HEADERS = {
    "user-agent": UA,
    "accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,"
               "image/webp,*/*;q=0.8"),
    "accept-language": "en-US,en;q=0.9",
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "none",
    "upgrade-insecure-requests": "1",
}

CACHE = pathlib.Path(".cache/public")
CACHE.mkdir(parents=True, exist_ok=True)

# NO cookies on this client, deliberately.
c = httpx.Client(headers=HEADERS, timeout=45.0, follow_redirects=True)

for target in TARGETS:
    url = f"https://www.linkedin.com/in/{target}/"
    dest = CACHE / f"{target}.html"
    if dest.exists():
        body = dest.read_text()
        status = 200
        print(f"\n=== {target} [cached] {len(body)} bytes")
    else:
        r = c.get(url)
        body, status = r.text, r.status_code
        dest.write_text(body)
        print(f"\n=== {target}  HTTP {status}  {len(body)} bytes  final={str(r.url)[:70]}")

    if status != 200:
        continue

    blocks = re.findall(
        r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
        body, re.DOTALL)
    print(f"    JSON-LD blocks: {len(blocks)}")

    for i, raw in enumerate(blocks):
        try:
            data = json.loads(htmllib.unescape(raw.strip()))
        except Exception as exc:
            print(f"    [{i}] unparseable: {exc}")
            continue
        (CACHE / f"{target}.ld{i}.json").write_text(json.dumps(data, indent=2))

        graph = data.get("@graph", data if isinstance(data, list) else [data])
        for node in graph:
            if not isinstance(node, dict):
                continue
            t = node.get("@type")
            print(f"    [{i}] @type={t}")
            if t == "Person":
                print(f"          name        {node.get('name')}")
                print(f"          headline    {str(node.get('jobTitle'))[:70]}")
                print(f"          about       {str(node.get('description'))[:70]}")
                print(f"          address     {node.get('address')}")
                print(f"          image       {str(node.get('image'))[:60]}")
                works = node.get("worksFor") or []
                alumni = node.get("alumniOf") or []
                print(f"          worksFor    {len(works)} entries")
                for w in works[:4]:
                    if isinstance(w, dict):
                        print(f"             - {w.get('name')}  {w.get('member', '')}")
                print(f"          alumniOf    {len(alumni)} entries")
                for a in alumni[:4]:
                    if isinstance(a, dict):
                        print(f"             - {a.get('name')}  {a.get('member', '')}")

c.close()
print(f"\nsaved to {CACHE}/")
