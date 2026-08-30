"""Find which read strategy returns profile data today. API routes only."""
exec(open("scripts/probe.py").read())

TARGET = "williamhgates"
V = "https://www.linkedin.com/voyager/api"
results = {}

with client() as c:
    results["me (control)"] = cached_get(
        c, "control: /me", f"{V}/me", show_chars=120)

    results["legacy_profileView"] = cached_get(
        c, "A. legacy /identity/profiles/{id}/profileView",
        f"{V}/identity/profiles/{TARGET}/profileView", show_chars=300)

    results["dash_memberIdentity"] = cached_get(
        c, "B. dash /identity/dash/profiles?q=memberIdentity",
        f"{V}/identity/dash/profiles",
        params={"q": "memberIdentity", "memberIdentity": TARGET}, show_chars=300)

    results["graphql_bare"] = cached_get(
        c, "C. graphql, no queryId (the error names what it wants)",
        f"{V}/graphql", params={"variables": f"(vanityName:{TARGET})"}, show_chars=400)

print("\n\n===== SUMMARY =====")
for name, blob in results.items():
    s, n = blob["status"], len(blob["body"])
    verdict = "DATA" if s == 200 and n > 500 else "redirect" if s in (301,302,303,307,308) else f"HTTP {s}"
    print(f"  {name:24} {verdict:12} {n:8} bytes")
