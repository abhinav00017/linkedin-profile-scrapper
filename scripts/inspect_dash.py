import json, pathlib, collections
for p in pathlib.Path(".cache/linkedin").glob("*.json"):
    b = json.loads(p.read_text())
    if "dash/profiles" in b["url"] and b["status"] == 200:
        break
d = json.loads(b["body"])
inc = d["included"]
print("included objects:", len(inc))
types = collections.Counter(o.get("$type","?").split(".")[-1] for o in inc)
for t, n in types.most_common():
    print(f"  {n:3}  {t}")

prof = [o for o in inc if o.get("$type","").endswith("profile.Profile")]
print("\n=== Profile object keys ===")
for o in prof:
    for k, v in sorted(o.items()):
        s = json.dumps(v)[:95] if not isinstance(v,str) else v[:95]
        print(f"  {k:34} {s}")

print("\n=== remaining keys ===")
seen = set("""$type address associatedHashtagsCopy backgroundPicture backgroundPictures birthDateOn
companyNameOnProfileTopCardShown contentRestrictedAnnotation coverPhotoItems created creator
creatorBadgeStatus creatorInfo creatorWebsite defaultToActivityTab displayBadges educationCardUrn
educationOnProfileTopCardShown emailAddress emailRequired endorsementsEnabled entityUrn firstName
firstNamePronunciationHint fullNamePronunciationAudio geoLocation geoLocationBackfilled
guideFetcherUrn headline headlineGeneratedSuggestionDelegateUrn hideNonSelfProfileViewBasedOnViewer
idvAdditionalNameConsent imFollowsPromoLegoTrackingId industryUrn industryV2Urn influencer
instantMessengers iweWarned lastName lastNamePronunciationHint location locationName maidenName
memberPostAnalytics memorialized multiLocaleAddress multiLocaleFirstName
multiLocaleFirstNamePronunciationHint multiLocaleFullNamePronunciationAudio multiLocaleHeadline
multiLocaleLastName multiLocaleLastNamePronunciationHint multiLocaleMaidenName
multiLocalePhoneticFirstName multiLocalePhoneticLastName multiLocaleSummary multiLocaleTempStatus
objectUrn phoneNumbers phoneticFirstName phoneticLastName premium premiumCoverPhotosCTA
premiumFeatures primaryLocale""".split())
for o in prof:
    for k, v in sorted(o.items()):
        if k in seen: continue
        s = json.dumps(v)[:95] if not isinstance(v,str) else v[:95]
        print(f"  {k:34} {s}")

print("\n=== every card urn ===")
for o in prof:
    for k, v in sorted(o.items()):
        if "CardUrn" in k or (isinstance(v,str) and "profileCard" in v):
            print(f"  {k:26} {v}")
