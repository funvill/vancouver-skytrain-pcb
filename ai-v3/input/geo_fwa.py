"""Metro Vancouver land / water from the BC Freshwater Atlas (FWA).

Why this source: the FWA is the province's authoritative 1:20 000
hydrography. Unlike OSM's coastline (which in this area stops at Burrard
Inlet - the Fraser's arms are riverbank polygons there, which is how an
earlier build lost Sea Island and the whole estuary), the FWA gives every
piece we need as ready-made POLYGONS, so nothing has to be assembled from
lines:

  FWA_WATERSHED_GROUPS_POLY  watershed groups cover LAND only (they end
                             at the coastline), so land = their union
                             and sea = frame - land - no coastline
                             tracing at all
  FWA_RIVERS_POLY            the Fraser and its arms/channels, Pitt,
                             Coquitlam ... as polygons, islands included
  FWA_LAKES_POLY             lakes as polygons

All three were fetched from the provincial WFS with a bbox and cached in
osm/ (see FETCH at the bottom). Coordinates are projected with a local
equirectangular projection into km from the frame's north-west corner,
y down. `water()` returns the smoothed water geometry in that frame;
`python geo_fwa.py` renders a preview PNG with the stations overlaid.
"""
import json
import math

from shapely.geometry import MultiPolygon, Polygon, box, shape
from shapely.ops import unary_union

# --- frame ------------------------------------------------------------------
# Cropped to the network: Point Grey's tip to just past Langley City
# Centre's label, a sliver of North Shore above Lonsdale Quay to ~1 km
# below Langley. On a 200 mm-wide board that is 200 x ~111 mm, 4.4 mm/km.
LON0, LON1 = -123.262, -122.627      # west .. east
LAT0, LAT1 = 49.322, 49.096          # north .. south
BOARD_W_MM = 200.0
LAT_MID = (LAT0 + LAT1) / 2
KX, KY = 111.32 * math.cos(math.radians(LAT_MID)), 111.32   # km per degree
W_KM, H_KM = (LON1 - LON0) * KX, (LAT0 - LAT1) * KY
FRAME = box(0, 0, W_KM, H_KM)


def km(lat, lon):
    """Frame-relative km: x east from the west edge, y south from the north."""
    return ((lon - LON0) * KX, (LAT0 - lat) * KY)


def _project(geom_json):
    """GeoJSON (lon, lat) geometry -> shapely in frame km."""
    def ring(r):
        return [km(lat, lon) for lon, lat in r]
    g = geom_json
    if g["type"] == "Polygon":
        return Polygon(ring(g["coordinates"][0]),
                       [ring(r) for r in g["coordinates"][1:]]).buffer(0)
    if g["type"] == "MultiPolygon":
        return MultiPolygon([Polygon(ring(p[0]), [ring(r) for r in p[1:]])
                             for p in g["coordinates"]]).buffer(0)
    raise ValueError(g["type"])


def _features(name):
    return json.load(open(f"osm/{name}.json", encoding="utf-8"))["features"]


# Lakes below this are ponds at 3 mm/km; rivers below it are creeks.
MIN_LAKE_HA = 8.0
MIN_RIVER_HA = 12.0
# River islands smaller than this are filled (the Fraser is braided
# around dozens of bars); Sea Island, Lulu, Annacis, Barnston survive.
MIN_ISLAND_KM2 = 0.25
SMOOTH_KM = 0.05          # simplify tolerance
OPEN_CLOSE_KM = 0.035     # drops nooks narrower than ~70 m


def land_raw():
    return unary_union([_project(f["geometry"]) for f in _features("FWA_WATERSHED_GROUPS_POLY")])


MIN_RIVER_WIDTH_KM = 0.10   # mean width (2*area/perimeter); drops creeks


def rivers_raw():
    out = []
    for f in _features("FWA_RIVERS_POLY"):
        if (f["properties"].get("AREA_HA") or 0) < MIN_RIVER_HA:
            continue
        g = _project(f["geometry"])
        if g.length and 2 * g.area / g.length >= MIN_RIVER_WIDTH_KM:
            out.append(g)
    return unary_union(out)


KEEP_LAKES = {"Burnaby Lake", "Deer Lake", "Trout Lake", "Como Lake",
              "Lost Lagoon", "Lafarge Lake", "Sasamat Lake", "Buntzen Lake"}


def lakes_raw():
    """Only the lakes worth showing at this scale - by name, so a 10 ha
    pond doesn't sneak in on area alone."""
    return unary_union([_project(f["geometry"]) for f in _features("FWA_LAKES_POLY")
                        if f["properties"].get("GNIS_NAME_1") in KEEP_LAKES
                        and (f["properties"].get("AREA_HA") or 0) >= MIN_LAKE_HA])


def _fill_small_holes(geom, min_km2):
    out = []
    for g in getattr(geom, "geoms", [geom]):
        out.append(Polygon(g.exterior, [r for r in g.interiors
                                        if Polygon(r).area >= min_km2]))
    return unary_union(out)


MIN_PIECE_KM2 = 0.5   # a sea/river piece must be at least this (lakes exempt)


def water(smooth=True):
    sea = FRAME.difference(land_raw())
    flow = unary_union([sea, rivers_raw()]).intersection(FRAME)
    # creeks, and bays that are mostly outside the frame (Mud Bay's tip at
    # the bottom edge): keep the big connected water, drop the rest
    flow = unary_union([g for g in getattr(flow, "geoms", [flow])
                        if g.area >= MIN_PIECE_KM2 and
                        not (g.area < 3.0 and g.intersects(FRAME.boundary))])
    w = unary_union([flow, lakes_raw().intersection(FRAME)])
    if smooth:
        w = w.buffer(-OPEN_CLOSE_KM).buffer(2 * OPEN_CLOSE_KM).buffer(-OPEN_CLOSE_KM)
        w = w.simplify(SMOOTH_KM, preserve_topology=True)
        w = _fill_small_holes(w, MIN_ISLAND_KM2)
        w = unary_union([g for g in getattr(w, "geoms", [w]) if g.area >= 0.05])
        w = w.intersection(FRAME)
    return w


def render(path, water_geom, stations=None, dpi=110):
    """Preview PNG: board colours, frame = board aspect, stations overlaid."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(15, 15 * H_KM / W_KM), dpi=dpi)
    ax.set_facecolor("#2f5442")
    for g in getattr(water_geom, "geoms", [water_geom]):
        x, y = g.exterior.xy
        ax.fill(x, y, color="#f2d43a", lw=0)
        for r in g.interiors:
            x, y = r.xy
            ax.fill(x, y, color="#2f5442", lw=0)
    for sid, (x, y, name) in (stations or {}).items():
        ax.plot(x, y, "o", ms=4, mfc="white", mec="black", mew=0.5)
        ax.text(x + 0.15, y - 0.15, name, fontsize=5, color="white")
    ax.set_xlim(0, W_KM)
    ax.set_ylim(H_KM, 0)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    plt.subplots_adjust(0, 0, 1, 1)
    plt.savefig(path, dpi=dpi)
    plt.close(fig)


if __name__ == "__main__":
    import sys
    w = water()
    mm_per_km = BOARD_W_MM / W_KM
    print(f"frame {W_KM:.1f} x {H_KM:.1f} km -> board {BOARD_W_MM:.0f} x "
          f"{H_KM * mm_per_km:.1f} mm at {mm_per_km:.2f} mm/km")
    print(f"water: {len(getattr(w, 'geoms', [w]))} piece(s), "
          f"{w.area:.0f} km^2 of {W_KM * H_KM:.0f}")
    stations = {}
    try:
        d = json.load(open("vancouver.json", encoding="utf-8"))
        st = json.load(open("osm_station_latlon.json", encoding="utf-8"))
        for sid, (lat, lon) in st.items():
            x, y = km(lat, lon)
            nm = d["stations"].get(sid, {}).get("name", sid)
            stations[sid] = (x, y, nm)
    except FileNotFoundError:
        pass
    out = sys.argv[1] if len(sys.argv) > 1 else "../test-results/geo-preview.png"
    render(out, w, stations)
    print("wrote", out)

# FETCH (bbox -123.30,49.08,-122.60,49.36):
#   https://openmaps.gov.bc.ca/geo/pub/wfs?service=WFS&version=2.0.0
#     &request=GetFeature&typeName=WHSE_BASEMAPPING.<LAYER>
#     &outputFormat=json&srsName=EPSG:4326&bbox=<bbox>,EPSG:4326
#   for LAYER in FWA_WATERSHED_GROUPS_POLY, FWA_RIVERS_POLY, FWA_LAKES_POLY
