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
LON0, LON1 = -123.275, -122.612      # west .. east
LAT0, LAT1 = 49.336, 49.087          # north .. south
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


def rivers_raw():
    return unary_union([_project(f["geometry"]) for f in _features("FWA_RIVERS_POLY")
                        if (f["properties"].get("AREA_HA") or 0) >= MIN_RIVER_HA])


def lakes_raw():
    return unary_union([_project(f["geometry"]) for f in _features("FWA_LAKES_POLY")
                        if (f["properties"].get("AREA_HA") or 0) >= MIN_LAKE_HA])


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
    # creeks and clipped bay tips that don't connect to the main water
    flow = unary_union([g for g in getattr(flow, "geoms", [flow]) if g.area >= MIN_PIECE_KM2])
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
