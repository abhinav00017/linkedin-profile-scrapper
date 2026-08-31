"""End-to-end check against live LinkedIn. No mocks.

Runs the real app in-process with the cookie from .env.local, then asks it
for a profile the way a caller would.
"""
import json
import os
import pathlib

env = {}
for line in pathlib.Path(".env.local").read_text().splitlines():
    line = line.strip()
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()

cookie_header = env.get("COOKIE_HEADER", "")
jar = {}
for part in cookie_header.split(";"):
    if "=" in part:
        k, v = part.split("=", 1)
        jar[k.strip()] = v.strip()

li_at = jar.get("li_at") or env.get("LI_AT")
jsessionid = (jar.get("JSESSIONID") or env.get("JSESSIONID", "")).strip('"')

if not li_at:
    raise SystemExit("no li_at in .env.local")

from cryptography.fernet import Fernet  # noqa: E402

os.environ["ENCRYPTION_KEY"] = Fernet.generate_key().decode()
os.environ["DB_PATH"] = ".cache/smoke.db"
os.environ["BOOTSTRAP_API_KEY"] = "tk_smoke"
os.environ["BOOTSTRAP_LI_AT"] = li_at
os.environ["BOOTSTRAP_JSESSIONID"] = jsessionid
os.environ["BOOTSTRAP_COOKIE_HEADER"] = cookie_header

from fastapi.testclient import TestClient  # noqa: E402

from app.main import create_app  # noqa: E402

api = TestClient(create_app())

print("health:", api.get("/healthz").json())

TARGET = "https://www.linkedin.com/in/williamhgates/"
print(f"\nfetching {TARGET} ...")
r = api.get("/v1/profile", params={"url": TARGET}, headers={"X-API-Key": "tk_smoke"})
print("HTTP", r.status_code)

body = r.json()
if r.status_code != 200:
    print(json.dumps(body, indent=2)[:800])
    raise SystemExit(1)

print(f"\nname       {body['name']['full']}")
print(f"headline   {body['headline']}")
print(f"about      {(body['about'] or '')[:70]}")
print(f"location   {body['location']['locality']} / {body['location']['country_code']}")
print(f"image      {(body['images']['profile'] or '')[:60]}")
print(f"websites   {[w['url'] for w in body['websites']]}")
print(f"\nexperience {len(body['experience'])}")
for e in body["experience"]:
    s = e["start"]["year"] if e.get("start") else None
    print(f"   {e['title']} | {e['company']} | {s}")
print(f"education  {len(body['education'])}")
for e in body["education"]:
    print(f"   {e['school']} | {e['start']['year'] if e.get('start') else None}")
print(f"\nmeta       {json.dumps(body['meta'])}")

pathlib.Path(".cache/smoke_result.json").write_text(json.dumps(body, indent=2))
print("\nfull response -> .cache/smoke_result.json")
