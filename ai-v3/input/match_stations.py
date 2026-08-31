import json

words = json.load(open("words.json", encoding="utf-8"))
circles = json.load(open("circles.json", encoding="utf-8"))

# One reliable, unique-in-document anchor word per station (avoids the
# angled/overlapping labels that pdfplumber garbled into loose letters).
ANCHOR = {
 "waterfront": "Waterfront", "burrard": "Burrard", "granville": "Granville",
 "stadium": "Stadium–Chinatown", "main-street": "Science",
 "nanaimo": "Nanaimo", "patterson": "Patterson", "metrotown": "Metrotown",
 "royal-oak": "Royal", "edmonds": "Edmonds", "22nd-street": "22nd",
 "new-westminster": "Westminster", "columbia": "Columbia", "braid": "Braid",
 "production-way": "University", "scott-road": "Scott", "gateway": "Gateway",
 "surrey-central": "Surrey", "king-george": "George",
 "vcc-clark": "VCC–Clark", "renfrew": "Renfrew", "rupert": "Rupert",
 "gilmore": "Gilmore", "brentwood": "Brentwood", "holdom": "Holdom",
 "sperling": "Sperling–", "burquitlam": "Burquitlam",
 "moody-centre": "Moody", "inlet-centre": "Inlet",
 "coquitlam-central": "Coquitlam", "lincoln": "Lincoln", "lafarge": "Lafarge",
 "vancouver-city-centre": "Vancouver",
 "yaletown": "Yaletown–Roundhouse", "olympic-village": "Olympic",
 "broadway-city-hall": "Broadway–City", "king-edward": "Edward",
 "oakridge": "Oakridge–41st", "langara": "Langara–49th",
 "marine-drive": "Marine", "bridgeport": "Bridgeport",
 "templeton": "Templeton", "sea-island-centre": "Island", "yvr": "YVR–",
 "capstan": "Capstan", "aberdeen": "Aberdeen", "lansdowne": "Lansdowne",
 "richmond-brighouse": "Richmond-Brighouse",
}

anchors = {}
for sid, tok in ANCHOR.items():
    matches = [w for w in words if w["text"] == tok]
    assert len(matches) == 1, (sid, tok, len(matches))
    w = matches[0]
    anchors[sid] = ((w["x0"] + w["x1"]) / 2, (w["top"] + w["bottom"]) / 2)

used = set()
result = {}
for sid, (ax, ay) in anchors.items():
    best_i, best_d = None, 1e9
    for i, (cx, cy, color) in enumerate(circles):
        if i in used:
            continue
        d = (cx - ax) ** 2 + (cy - ay) ** 2
        if d < best_d:
            best_d, best_i = d, i
    used.add(best_i)
    cx, cy, color = circles[best_i]
    result[sid] = {"x": cx, "y": cy, "dist": round(best_d ** 0.5, 1),
                   "circle_i": best_i}

json.dump(result, open("station_coords.json", "w"), indent=2)
print(f"matched {len(result)} stations from {len(ANCHOR)} anchors")
print(f"unused circles ({len(circles) - len(used)}):")
for i, (x, y, c) in enumerate(circles):
    if i not in used:
        print(f"  {i:3} x={x:6.1f} y={y:6.1f} color={tuple(round(v,2) for v in c)}")
print("worst anchor->circle distances:")
for sid, r in sorted(result.items(), key=lambda kv: -kv[1]["dist"])[:8]:
    print(f"  {sid:24} {r['dist']}")
