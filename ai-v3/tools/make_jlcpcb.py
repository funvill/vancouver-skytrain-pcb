"""Turn kicad-cli's raw position/BOM exports into JLCPCB's BOM + CPL and zip
the gerbers. Run from ai-v3/hardware after the kicad-cli exports (see
jlcpcb/README.md):

    python ../tools/make_jlcpcb.py [jlcpcb]

Only parts with an LCSC number are placed; the XIAO module, test points and
mounting holes are left out of both files.
"""
import csv
import glob
import os
import re
import sys
import zipfile

out = sys.argv[1] if len(sys.argv) > 1 else "jlcpcb"

# --- BOM: expand reference ranges, one line per LCSC part -----------------
def expand(refs):
    result = []
    for r in refs.split(","):
        r = r.strip()
        m = re.match(r"([A-Za-z_+]+)(\d+)-([A-Za-z_+]+)(\d+)$", r)
        if m and m.group(1) == m.group(3):
            result += [f"{m.group(1)}{i}" for i in range(int(m.group(2)), int(m.group(4)) + 1)]
        elif r:
            result.append(r)
    return result


placed = {}
with open(os.path.join(out, "bom-raw.csv"), encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))
bom = []
for r in rows:
    lcsc = (r.get("LCSC Part") or r.get("LCSC") or "").strip()
    if not lcsc:
        continue
    refs = expand(r["Reference"])
    for ref in refs:
        placed[ref] = lcsc
    bom.append({"Comment": r["Value"], "Designator": ",".join(refs),
                "Footprint": r["Footprint"].split(":")[-1], "LCSC Part #": lcsc})
with open(os.path.join(out, "bom-jlcpcb.csv"), "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["Comment", "Designator", "Footprint", "LCSC Part #"])
    w.writeheader()
    w.writerows(bom)

# --- CPL --------------------------------------------------------------------
cpl = []
with open(os.path.join(out, "pos-raw.csv"), encoding="utf-8-sig", newline="") as f:
    for r in csv.DictReader(f):
        if r["Ref"] not in placed:
            continue
        cpl.append({"Designator": r["Ref"], "Mid X": f"{float(r['PosX']):.4f}mm",
                    "Mid Y": f"{float(r['PosY']):.4f}mm",
                    "Layer": "Top" if r["Side"] == "top" else "Bottom",
                    "Rotation": f"{float(r['Rot']):.1f}"})
cpl.sort(key=lambda c: (re.sub(r"\d+$", "", c["Designator"]), int(re.sub(r"\D", "", c["Designator"]) or 0)))
with open(os.path.join(out, "cpl-jlcpcb.csv"), "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
    w.writeheader()
    w.writerows(cpl)
missing = sorted(set(placed) - {c["Designator"] for c in cpl})

# --- gerber zip ---------------------------------------------------------------
zpath = os.path.join(out, "vancouver-skytrain-pcb-gerbers.zip")
with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
    for p in sorted(glob.glob(os.path.join(out, "gerbers", "*"))):
        z.write(p, os.path.basename(p))
print(f"BOM: {len(bom)} line(s), {len(placed)} placed part(s); CPL: {len(cpl)} row(s)"
      f"{'; MISSING from CPL: ' + ', '.join(missing) if missing else ''}; "
      f"zip: {len(glob.glob(os.path.join(out, 'gerbers', '*')))} file(s)")
