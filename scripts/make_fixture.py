"""Turn a cached live response into an anonymised test fixture.

Keeps LinkedIn's exact structure. Replaces the person. The repo is public, so
no real profile data goes into it.
"""
import json
import pathlib

SRC = pathlib.Path(".cache/linkedin")
DST = pathlib.Path("tests/fixtures")

# real value -> fixture value
SWAPS = {
    "Bill": "Jane",
    "Gates": "Doe",
    "williamhgates": "jane-doe",
    "ACoAAA8BYqEBCGLg_vT_ca6mMEqkpp9nVffJ3hc": "ACoAAAFIXTURE00000000000000000000000000",
    "251749025": "100000001",
    "Chair, Gates Foundation and Founder, Breakthrough Energy":
        "Chair, Example Foundation and Founder, Example Energy",
}


def scrub(node):
    if isinstance(node, dict):
        return {k: scrub(v) for k, v in node.items()}
    if isinstance(node, list):
        return [scrub(v) for v in node]
    if isinstance(node, str):
        out = node
        for old, new in SWAPS.items():
            out = out.replace(old, new)
        return out
    return node


def main() -> None:
    blob = None
    for p in SRC.glob("*.json"):
        b = json.loads(p.read_text())
        if "dash/profiles" in b["url"] and b["status"] == 200:
            blob = b
            break
    if blob is None:
        raise SystemExit("no cached dash/profiles response found")

    data = json.loads(blob["body"])

    # the summary is long prose about a real person — replace it wholesale
    for obj in data.get("included", []):
        if obj.get("$type", "").endswith("profile.Profile"):
            if obj.get("summary"):
                obj["summary"] = ("Chair of the Example Foundation. Founder of "
                                  "Example Energy. Voracious reader.")
            if isinstance(obj.get("multiLocaleSummary"), dict):
                obj["multiLocaleSummary"] = {
                    k: "Chair of the Example Foundation."
                    for k in obj["multiLocaleSummary"]
                }

    data = scrub(data)

    DST.mkdir(parents=True, exist_ok=True)
    out = DST / "dash_profile.json"
    out.write_text(json.dumps(data, indent=2))
    print(f"wrote {out}  ({out.stat().st_size} bytes)")

    text = out.read_text()
    leaked = [v for v in ("Bill", "Gates", "williamhgates", "251749025") if v in text]
    print("LEAKED REAL VALUES:", leaked if leaked else "none")


if __name__ == "__main__":
    main()
