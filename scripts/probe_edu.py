"""Does /details/education/ server-render for a profile that has education?"""
exec(open("scripts/probe.py").read())

from app.linkedin.details import extract_text_lines

for target, expect in [("williamhgates", "Harvard"), ("uday-karanam", "GITAM")]:
    for section in ("education", "certifications", "languages"):
        url = f"https://www.linkedin.com/in/{target}/details/{section}/"
        with client(doc=True) as c:
            blob = cached_get(c, f"{target}/{section}", url, show_chars=0)

        lines = extract_text_lines(blob["body"])
        heading = next((ln for ln in lines
                        if ln.lower().startswith(section[:6])
                        or ln in ("Licenses & certifications", "Education", "Languages")), None)
        print(f"{target:16} {section:15} HTTP {blob['status']} "
              f"{len(blob['body']):8}b  heading={heading!r}  "
              f"expect_marker={expect in blob['body']}")
