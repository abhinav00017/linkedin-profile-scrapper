# LinkedIn Profile API — Design

Date: 2026-08-30
Status: approved, pending endpoint verification

## Problem

Build a hosted HTTPS API. It accepts a LinkedIn profile URL. It returns the
profile as structured JSON.

The API must reach LinkedIn over plain HTTP. It must not drive a browser. No
Playwright, no Puppeteer, no Selenium, no headless Chrome.

## Who authenticates

The caller authenticates with their own LinkedIn account, not ours.

1. The caller posts their `li_at` session cookie to `/v1/auth`.
2. We check the cookie against LinkedIn. We store it encrypted. We return an
   API key.
3. The caller sends that key with every profile request. We fetch the profile
   with the caller's LinkedIn session.

Each caller spends their own LinkedIn request budget. One caller cannot get
another caller's account restricted.

A bootstrap key covers the demo. The server reads `BOOTSTRAP_API_KEY` and
`BOOTSTRAP_LI_AT` from the environment at start. That key works even when the
database is empty. The submission uses this key.

## Endpoints

### POST /v1/auth

Request:

```json
{ "li_at": "AQEDA...", "jsessionid": "ajax:1234567890123456789" }
```

`jsessionid` is optional. When absent we ask LinkedIn for a fresh one.

Response `201`:

```json
{
  "api_key": "tk_live_...",
  "linkedin_member": { "name": "Jane Doe", "public_id": "jane-doe" },
  "created_at": "2026-08-30T10:00:00Z"
}
```

We call LinkedIn's `/me` before we mint a key. A dead cookie gets `422`, not a
key that fails later.

### GET /v1/profile

Query: `url` — any LinkedIn profile URL.
Header: `X-API-Key`.

Response `200`: the profile schema below.

### GET /healthz

Returns `200` and the build version. No auth.

### GET /docs

The OpenAPI page FastAPI generates. This is the API documentation the README
points at.

## Talking to LinkedIn

Base: `https://www.linkedin.com/voyager/api/`

Every request carries:

| Header | Value |
|---|---|
| `cookie` | `li_at=<cookie>; JSESSIONID="<jsessionid>"` |
| `csrf-token` | the `JSESSIONID` value, quotes stripped |
| `x-restli-protocol-version` | `2.0.0` |
| `accept` | `application/vnd.linkedin.normalized+json+2.1` |
| `x-li-lang` | `en_US` |
| `user-agent` | a current desktop Chrome string |

### Read strategies

We try three strategies in order. Each one fills what it can. The response
names the strategy that served it.

1. **Voyager GraphQL** — `/voyager/api/graphql`. The call LinkedIn's own web
   app makes. Richest data. It needs a `queryId` that LinkedIn rotates. We keep
   every `queryId` in config, so a rotation is a config change and not a code
   change.
2. **Voyager REST** — `/identity/dash/profiles` with a decoration id. Older and
   thinner. More stable.
3. **Public JSON-LD** — the `application/ld+json` block LinkedIn embeds in the
   public profile page for search engines. Thin, but it needs no session.

Strategy 3 is the floor. It keeps the API useful when LinkedIn breaks the
first two.

## Response schema

```json
{
  "profile_url": "https://www.linkedin.com/in/jane-doe/",
  "public_id": "jane-doe",
  "urn": "urn:li:fsd_profile:ACoAAA...",
  "name": { "first": "Jane", "last": "Doe", "full": "Jane Doe" },
  "headline": "Software Engineer at Acme",
  "location": { "country": "India", "locality": "Bengaluru" },
  "about": "…",
  "images": { "profile": "https://…", "background": "https://…" },
  "experience": [
    {
      "title": "Software Engineer",
      "company": "Acme",
      "company_url": "https://www.linkedin.com/company/acme/",
      "location": "Bengaluru, India",
      "employment_type": "Full-time",
      "start": { "year": 2023, "month": 4 },
      "end": null,
      "is_current": true,
      "description": "…"
    }
  ],
  "education": [
    {
      "school": "…", "degree": "…", "field_of_study": "…",
      "start": { "year": 2019 }, "end": { "year": 2023 }, "description": null
    }
  ],
  "skills": [ { "name": "Python", "endorsement_count": 12 } ],
  "certifications": [
    { "name": "…", "authority": "…", "issued": { "year": 2024, "month": 1 },
      "url": null }
  ],
  "languages": [ { "name": "English", "proficiency": "Native or bilingual" } ],
  "meta": {
    "strategy": "voyager_graphql",
    "fetched_at": "2026-08-30T10:00:00Z",
    "duration_ms": 3120,
    "partial": false,
    "missing_sections": []
  }
}
```

Rules:

- A section LinkedIn does not give us is `[]` or `null`. It is never an error.
- Dates are objects, never strings. A LinkedIn date can lack a month.
- `meta.partial` is `true` when any section failed. `missing_sections` names
  them. The caller always knows what they did not get.

## Errors

Every error returns the same body:

```json
{ "error": { "code": "linkedin_session_dead", "message": "…" } }
```

| Status | Code | Cause |
|---|---|---|
| 400 | `invalid_profile_url` | The URL is not a LinkedIn profile URL |
| 401 | `invalid_api_key` | The key is missing or unknown |
| 403 | `linkedin_session_dead` | The caller's cookie expired or hit a checkpoint |
| 404 | `profile_not_found` | LinkedIn has no such profile |
| 429 | `rate_limited` | Our cap or LinkedIn's |
| 502 | `linkedin_unexpected_response` | LinkedIn answered with something we cannot parse |

## URL parsing

We accept all of these and reduce them to a public id:

- `https://www.linkedin.com/in/jane-doe`
- `https://www.linkedin.com/in/jane-doe/`
- `http://linkedin.com/in/jane-doe?originalSubdomain=in`
- `https://in.linkedin.com/in/jane-doe`
- `linkedin.com/in/jane-doe`
- `jane-doe`

We reject company, school and post URLs with `400`.

## Storage

SQLite. One table.

```sql
CREATE TABLE api_keys (
  key_hash        TEXT PRIMARY KEY,
  li_at_encrypted BLOB NOT NULL,
  jsessionid      TEXT,
  member_name     TEXT,
  member_public_id TEXT,
  created_at      TEXT NOT NULL,
  last_used_at    TEXT,
  request_count   INTEGER NOT NULL DEFAULT 0,
  revoked         INTEGER NOT NULL DEFAULT 0
);
```

- We store a SHA-256 hash of the key, never the key.
- We encrypt `li_at` with Fernet, using `ENCRYPTION_KEY` from the environment.
  A stolen database file yields no working sessions.
- The file lives on a Fly.io volume, so keys survive a redeploy.

## Rate limiting

Two caps, both to protect LinkedIn accounts rather than to restrict the caller:

- 10 profile fetches per minute per key.
- 300 profile fetches per day per key.

We also back off when LinkedIn answers `429` or `999`.

## Testing

- Parser tests run against saved fixture JSON. We scrub every fixture of
  cookies, tokens and member ids before it enters the repo.
- URL parser tests cover every variant above.
- API tests mock the LinkedIn client. CI never calls LinkedIn.

## Secrets

- `.env` and `.env.local` are gitignored from the first commit.
- `.env.example` documents every variable and holds no real value.
- A pre-commit check greps staged files for `li_at` and `AQEDA` patterns.

## Deployment

Fly.io. HTTPS by default. A small persistent volume holds the SQLite file. No
idle spindown, so the reviewer's first request does not stall.

## Known limitations

We write these in the README, honestly:

- LinkedIn rotates GraphQL `queryId` values. A rotation drops us to a weaker
  strategy until config is updated.
- Out-of-network profiles return less data than connections. LinkedIn decides
  this, not us.
- Private profiles return only what the public page exposes.
- Session cookies expire. The caller re-authenticates.
- This uses LinkedIn's internal API and breaks LinkedIn's terms of service. It
  is built for this challenge.

## Open question

Which read strategy works today. We verify against a live cookie and a real
out-of-network profile before we build the fetch layer.
