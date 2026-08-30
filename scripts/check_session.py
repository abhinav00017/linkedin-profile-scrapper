"""One request. Tells you whether the cookie in .env.local is alive."""
exec(open("scripts/probe.py").read())
with client() as c:
    r = get(c, "session check: /voyager/api/me", "https://www.linkedin.com/voyager/api/me", show_chars=300)
    print("\nSESSION ALIVE" if r.status_code == 200 else "\nSESSION NOT USABLE")
