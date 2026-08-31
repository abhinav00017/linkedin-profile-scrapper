# LinkedIn Profile API

Give it a LinkedIn profile URL. Get structured JSON.

Built by hitting LinkedIn's own HTTP endpoints directly. No browser, no
Playwright, no Selenium, no headless Chrome — just HTTP requests shaped the
way LinkedIn's own clients shape them.

---

## Try it

```bash
curl -s "https://linkedin-profile-api.fly.dev/v1/profile?url=https://www.linkedin.com/in/williamhgates/" \
  -H "X-API-Key: YOUR_KEY"
```

Interactive documentation: **`/docs`**

---

## How it authenticates

**You bring your own LinkedIn session.** The API does not read profiles with
my account — it reads them with yours.

1. `POST /v1/auth` with your LinkedIn `li_at` cookie. The API checks it
   against LinkedIn, then returns an API key.
2. `GET /v1/profile` with that key. Your session does the reading.

This means each caller spends their own LinkedIn request budget, and no
caller can get another caller's account throttled.

### Getting your cookie

1. Open a logged-in `linkedin.com` tab
2. `F12` → **Application** → **Cookies** → `https://www.linkedin.com`
3. Copy the value of **`li_at`** (and **`JSESSIONID`** if you want a more
   reliable session)

---

## API

### `POST /v1/auth`

Exchange a LinkedIn cookie for an API key.

```bash
curl -s -X POST https://linkedin-profile-api.fly.dev/v1/auth \
  -H "Content-Type: application/json" \
  -d '{"li_at": "AQEDAT...", "jsessionid": "ajax:1234567890"}'
```

```json
{
  "api_key": "tk_QmpZ...",
  "linkedin_member": { "name": "Jane Doe", "public_id": "jane-doe" },
  "created_at": "2026-08-31T06:15:07Z"
}
```

| Field | Required | Notes |
|---|---|---|
| `li_at` | yes | Your LinkedIn session cookie |
| `jsessionid` | no | Improves reliability; used as the CSRF token |
| `cookie_header` | no | The complete cookie header from your browser. Most reliable of all — see [Approach](#approach) |

The cookie is checked against LinkedIn before a key is issued, so a key you
receive is a key that works. A dead cookie returns `422`.

### `GET /v1/profile`

```bash
curl -s "https://linkedin-profile-api.fly.dev/v1/profile?url=https://www.linkedin.com/in/williamhgates/" \
  -H "X-API-Key: tk_QmpZ..."
```

`url` accepts anything a person might paste:

```
https://www.linkedin.com/in/jane-doe
https://www.linkedin.com/in/jane-doe/
http://linkedin.com/in/jane-doe?originalSubdomain=in
https://in.linkedin.com/in/jane-doe
linkedin.com/in/jane-doe
jane-doe
```

Company, school, job and post URLs are rejected with `400`.

<details>
<summary><b>Response</b></summary>

```json
{
  "profile_url": "https://www.linkedin.com/in/williamhgates/",
  "public_id": "williamhgates",
  "urn": "urn:li:fsd_profile:ACoAAA...",
  "name": { "first": "Bill", "last": "Gates", "full": "Bill Gates" },
  "headline": "Chair, Gates Foundation and Founder, Breakthrough Energy",
  "about": "Chair of the Gates Foundation. Founder of Breakthrough Energy…",
  "location": {
    "country_code": "US",
    "locality": "Seattle, Washington, United States",
    "geo_urn": "urn:li:fsd_geo:104116203"
  },
  "images": {
    "profile": "https://media.licdn.com/dms/image/v2/…",
    "background": "https://media.licdn.com/dms/image/v2/…"
  },
  "websites": [{ "category": "BLOG", "url": "https://gatesnot.es/…" }],
  "experience": [
    {
      "title": "Product Designer",
      "company": "Craft My Plate",
      "employment_type": "Full-time",
      "start": { "year": 2025, "month": 1 },
      "end": { "year": 2026, "month": 3 },
      "is_current": false,
      "duration": "1 yr 3 mos",
      "location": "Hyderabad, Telangana, India",
      "work_mode": "On-site",
      "description": "Led design and shipped V2 of the platform…",
      "skills": ["Product Design", "Strategy"]
    }
  ],
  "education": [
    { "school": "Harvard University", "start": { "year": 1973 }, "end": { "year": 1975 } }
  ],
  "skills": [],
  "certifications": [],
  "languages": [],
  "meta": {
    "sources": ["voyager_api", "experience_details_page", "public_jsonld"],
    "missing_sections": ["skills", "certifications", "languages"],
    "partial": true,
    "fetched_at": "2026-08-31T06:55:22Z",
    "duration_ms": 8382
  }
}
```

</details>

**`meta` is the honest part.** It names which sources answered and which
sections could not be retrieved. A section LinkedIn does not give us is `[]`
or `null` — never an error, never invented.

Dates are objects (`{"year": 2000, "month": 4}`), not strings, because a
LinkedIn date often has no month.

### `GET /healthz`

Liveness and version. No key needed.

### Errors

Every error has the same shape:

```json
{ "error": { "code": "linkedin_session_dead", "message": "…" } }
```

| Status | Code | Meaning |
|---|---|---|
| 400 | `invalid_profile_url` | Not a LinkedIn profile URL |
| 401 | `missing_api_key` / `invalid_api_key` | No key, or unknown/revoked |
| 403 | `linkedin_session_dead` | Your LinkedIn cookie expired — authenticate again |
| 404 | `profile_not_found` | No such profile, or your session cannot see it |
| 429 | `rate_limited` | Our cap, or LinkedIn's |
| 502 | `linkedin_unexpected_response` | LinkedIn returned something unparseable |

---

## Approach

The interesting part of this problem is not the API. It is working out what
LinkedIn will actually answer.

### Voyager

LinkedIn's web app talks to an internal API at `/voyager/api/`. It
authenticates with the `li_at` cookie plus a `csrf-token` header whose value
is the `JSESSIONID` cookie. Two generations coexist:

```
REST     /voyager/api/identity/dash/profiles?q=memberIdentity&memberIdentity=<publicId>
GraphQL  /voyager/api/graphql?variables=(memberIdentity:<urn>)&queryId=<name>.<32-hex>
```

Both work and both return the same core profile. The REST finder is used
here because it takes the public id straight from the URL, with no lookup
step.

Responses come back **normalised**: a `data` object of URN pointers plus an
`included` array of typed objects. `app/linkedin/parse.py` flattens that
graph into the response schema.

### What does not work, and why

| Attempt | Result |
|---|---|
| `/identity/profiles/{id}/profileView` | `410 Gone`. Retired by LinkedIn |
| Writing my own GraphQL query | Rejected. Only pre-registered `queryId` hashes are accepted, and they rotate |
| Parsing the logged-in profile page | No JSON in it. LinkedIn now server-renders profiles with obfuscated class names like `_02484ad3` |
| Reading query ids from JS bundles | The server-rendered page loads only 16 scripts, none containing query hashes |

The last two matter: **LinkedIn's profile page makes no API call at all any
more.** The data is rendered into HTML server-side. A HAR capture of a full
profile page load contains zero section requests, because none happen.

### How sections are retrieved

The authenticated API returns the core profile but no sections. Two further
sources fill what they can, fetched concurrently.

**Experience — the `/details/experience/` page.** This is the page behind
LinkedIn's "Show all experiences" link, and it is one of the few LinkedIn
still renders on the server. A plain GET returns the whole list, unmasked:

```
Product Designer
Craft My Plate · Full-time
Jan 2025 - Mar 2026 · 1 yr 3 mos
Hyderabad, Telangana, India · On-site
```

The parser (`app/linkedin/details.py`) anchors on **the date line**, whose
shape LinkedIn has kept stable, and reads the lines around it. Nothing keys
on a CSS class, because LinkedIn regenerates class names (`_02484ad3`) on
every deploy — a parser built on those would break within days.

**Education — the logged-out page's JSON-LD.** LinkedIn renders a different
page for visitors with no session, because that is what search engines index,
and it embeds structured data:

```json
{
  "@type": "Person",
  "alumniOf": [{ "name": "Harvard University", "member": { "startDate": 1973, "endDate": 1975 } }]
}
```

| Source | Provides |
|---|---|
| Voyager API (your session) | name, headline, about, location, images, websites |
| `/details/experience/` (your session) | experience, in full and unmasked |
| Public JSON-LD (no cookies) | education, readable locality |

The authenticated sources win wherever two sources disagree, because the
public page truncates and masks.

### Sessions get revoked, and why

LinkedIn scores each request for whether it looks like a real browser. Four
sessions were revoked during development before the pattern became clear.
LinkedIn signals it by answering `302` with `set-cookie: li_at="delete me"`.

Two things trigger it:

1. **An HTML page request carrying only `li_at` and `JSESSIONID`.** A real
   browser also sends `bcookie`, `bscookie`, `lidc`, `li_gc`. Two cookies at
   a page route reads as a hijacked session. API routes tolerate it; page
   routes do not.
2. **A URL shape LinkedIn's clients never request.** An invented path reads
   as probing.

The client sends Chrome's exact headers — `sec-ch-ua`, `sec-fetch-*`,
`priority`, a current `user-agent` — and only requests paths LinkedIn's own
clients request. Supplying `cookie_header` at `/v1/auth` passes your whole
cookie set through, which is the most reliable configuration.

`SessionDead` is detected explicitly and surfaced as `403` so a caller knows
to re-authenticate rather than seeing a confusing `502`.

---

## Local setup

```bash
git clone https://github.com/<you>/linkedin-profile-api.git
cd linkedin-profile-api

python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

cp .env.example .env
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# paste that into ENCRYPTION_KEY in .env

uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs

### Tests

```bash
pytest
```

106 tests, no network calls. Parsers are tested against saved fixtures, and
the LinkedIn client is mocked at the API layer. Fixtures are hand-authored
with LinkedIn's exact structure and a fictional person, so no real profile
data lives in this repository.

---

## Security

- **No secrets in the repo.** `.env` and `.env.local` are gitignored from the
  first commit; `.env.example` documents every variable and holds no values.
- **API keys are hashed** with SHA-256 before storage. The database never
  holds a usable key.
- **LinkedIn cookies are encrypted at rest** with Fernet. A stolen database
  file yields no working sessions without `ENCRYPTION_KEY`.
- **Rate limits** cap requests per key, per minute and per day. They exist to
  protect the LinkedIn account behind a key, not to ration the caller.

---

## Deployment

Fly.io, HTTPS by default, with a persistent volume so keys survive redeploys.

```bash
fly launch --no-deploy
fly volumes create linkedin_api_data --size 1
fly secrets set ENCRYPTION_KEY="$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
fly secrets set BOOTSTRAP_API_KEY="tk_demo_..." BOOTSTRAP_LI_AT="AQEDA..."
fly deploy
```

`auto_stop_machines = false` keeps the machine warm, so the first request
does not stall on a cold start.

---

## Known limitations

Written plainly, because these are real.

**Skills, certifications and languages are not returned.** This is the real
limit of a no-browser approach, and it is worth being precise about why.

LinkedIn renders those sections **client-side**. Their detail pages —
`/details/skills/`, `/details/certifications/`, `/details/languages/` —
answer `200` with a full-size document, but the section content is not in it.
The skills page contains only the filter tabs ("All", "Industry Knowledge",
"Tools & Technologies") and then the advertisement block. The data arrives
afterwards, through JavaScript this API deliberately does not run.

Verified against two profiles, one with all sections populated and one
without, to rule out an empty profile as the explanation. `/details/experience/`
server-renders; the other four do not.

Reaching them needs either a browser, which the brief excludes, or a GraphQL
`queryId` for the section queries. LinkedIn does not publish those hashes,
accepts no query that is not on its allowlist, and rotates them on deploy.

`meta.missing_sections` names them on every response rather than returning
empty arrays that would read as "this person has no skills".

**Per-role skills do come through.** The experience page lists them per
position — `"Product Design, Strategy and +2 skills"` — so `experience[].skills`
is populated where LinkedIn shows it. The unnamed `+2` are not on the page,
so they are not invented.

**Education depends on an aggressively throttled page.** The public JSON-LD
is the only source for it, and LinkedIn answers `999` after roughly one
request per IP, for minutes at a time. Successful reads are cached for an
hour. Under load, expect education to be missing more often than present.
It also gives school and years but no degree or field of study.

**The public page masks some values.** For logged-out readers LinkedIn stars
out parts of the data — job titles appear as `********`, some company names
as `************ ******`. Masked values are returned as `null`, not as
asterisks. This is why the authenticated `/details/experience/` page is
preferred for experience: it has no masking at all.

**The public page is throttled hard.** LinkedIn answers `999` after roughly
one request from an IP and keeps doing so for minutes. Successful reads are
cached for an hour to soften this, and a throttled read degrades the
response to core-profile-only rather than failing it. Under sustained load,
expect experience and education to be missing more often than not.

**Out-of-network profiles return less.** LinkedIn decides how much a session
may see. A profile you are connected to returns more than a stranger's. This
is LinkedIn's policy, not a limit of this code.

**Sessions expire.** Cookies last weeks, not forever, and LinkedIn revokes
them when a request looks wrong. The API returns `403 linkedin_session_dead`
and the caller authenticates again.

**Rate limiting is per process.** It lives in memory, so a second instance
would not share counters. Single-instance deployment keeps it correct; more
instances would need Redis.

**LinkedIn can break this at any time.** It is an internal API with no
stability promise. The read path is structured as independent strategies so
one breaking degrades the response rather than ending it.

---

## Project layout

```
app/
  api/routes.py        endpoints, request and response models
  core/config.py       settings from the environment
  core/limits.py       rate limiting
  linkedin/client.py   HTTP client — headers, cookies, session-death detection
  linkedin/urls.py     URL parsing
  linkedin/parse.py    Voyager response  -> schema
  linkedin/jsonld.py   public JSON-LD    -> schema
  linkedin/details.py  /details/experience/ page -> schema
  linkedin/merge.py    combines both sources
  models/profile.py    the response schema
  store/keys.py        API keys, hashed; cookies, encrypted
tests/                 106 tests, no network
scripts/               throwaway probes used to work out the endpoints
```

`scripts/` is kept deliberately. It is the record of how the endpoints were
found, including the ones that failed.

---

## A note on terms

This uses LinkedIn's internal API, which its User Agreement does not permit.
It was built for a hiring challenge that asked for exactly this. Use your own
account, and know that LinkedIn may restrict an account whose session drives
automated requests.
