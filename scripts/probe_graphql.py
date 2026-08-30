"""Replay the exact profile GraphQL call LinkedIn's own web app makes.

The query id came out of a real HAR capture, so this is a request LinkedIn
expects — unlike the guesses that kept getting sessions revoked.
"""
exec(open("scripts/probe.py").read())

TARGET_ID = "ACoAAA8BYqEBCGLg_vT_ca6mMEqkpp9nVffJ3hc"   # from the cached dash call
QUERY_ID = "voyagerIdentityDashProfiles.b5c27c04968c409fc0ed3546575b9b7a"

# Build the URL by hand: LinkedIn's restli syntax wants literal parens, and
# httpx would percent-encode them.
url = (
    "https://www.linkedin.com/voyager/api/graphql"
    f"?includeWebMetadata=true&variables=(memberIdentity:{TARGET_ID})"
    f"&queryId={QUERY_ID}"
)

with client() as c:
    blob = cached_get(c, "graphql voyagerIdentityDashProfiles (real queryId)",
                      url, show_chars=400)

if blob["status"] == 200:
    import json as _json
    d = _json.loads(blob["body"])
    inc = d.get("included", [])
    print(f"\nincluded objects: {len(inc)}")
    import collections
    for t, n in collections.Counter(
        o.get("$type", "?").split(".")[-1] for o in inc
    ).most_common(25):
        print(f"  {n:4}  {t}")
