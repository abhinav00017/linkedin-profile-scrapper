"""Can we fetch profile section cards?"""
exec(open("scripts/probe.py").read())
from urllib.parse import quote

PID = "ACoAAA8BYqEBCGLg_vT_ca6mMEqkpp9nVffJ3hc"   # williamhgates, from the dash call
V = "https://www.linkedin.com/voyager/api"

def card_urn(kind):
    return f"urn:li:fsd_profileCard:({PID},{kind},en_US)"

with client() as c:
    # variant 1: RESTli path segment, fully encoded
    cached_get(c, "1. profileCards/<urn>  EXPERIENCE",
        f"{V}/identity/dash/profileCards/{quote(card_urn('EXPERIENCE'), safe='')}",
        show_chars=350)

    # variant 2: batch get by ids
    cached_get(c, "2. profileCards?ids=List(<urn>)  EXPERIENCE",
        f"{V}/identity/dash/profileCards",
        params={"ids": f"List({quote(card_urn('EXPERIENCE'), safe='')})"},
        show_chars=350)

    # variant 3: the deepDive finder the web app uses for 'show all'
    cached_get(c, "3. profileCards?q=deepDive EXPERIENCE",
        f"{V}/identity/dash/profileCards",
        params={"q": "deepDive", "profileUrn": f"urn:li:fsd_profile:{PID}",
                "sectionType": "experience"},
        show_chars=350)
