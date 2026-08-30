"""One request. Is the cookie in .env.local alive?"""
exec(open("scripts/probe.py").read())
with client() as c:
    r = cached_get(c, "session check: /voyager/api/me",
                   "https://www.linkedin.com/voyager/api/me", show_chars=250, force=True)
    print("\nSESSION ALIVE" if r["status"] == 200 else "\nSESSION NOT USABLE")
