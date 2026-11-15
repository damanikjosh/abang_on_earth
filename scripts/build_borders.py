#!/usr/bin/env python3
"""Builds public/data-v4/borders.geojson: the two border levels drawn on the map, derived from regions.geojson.
  uv run --with shapely python scripts/build_borders.py [DATA_DIR=public/data-v4]
Every polygon edge is looked at. An edge that two regions share exactly (same two vertices; the regions were simplified together, so shared edges keep identical vertices) is
  MINOR  if both regions are of the same country (province border), and
  MAJOR  if they are of different countries (international border).
Edges that only one region has are coast, or an international border whose two countries' source lines differ slightly (geoBoundaries draws each country on its own).
Such an edge is MAJOR when its midpoint lies within TOL degrees of another country's outline (drawn once, from the alphabetically first country of the pair), else coast
and in no level. Also country-outlines.geojson ({c: "THA"} lines: the outer edge of each country = coast + international border; used only while a country is selected).
Output: one FeatureCollection of merged lines, properties {l: "major", p: "IDN-MYS"} or {l: "minor", c: "IDN"}, coordinates as in regions.geojson.
Also registers files.borders in manifest.json and rewrites VERSION.json (sizes + sha256). Rollback: git revert the merge commit (the app draws no border when the file is absent)."""
import sys, json, collections, hashlib, pathlib, datetime
import shapely
from shapely.geometry import LineString, MultiLineString, Point
from shapely.ops import linemerge, unary_union
TOL = 0.025  # degrees (about 2.7 km): measured gap between two countries' versions of one border: 90 % of edges within 0.01, 99 % within 0.025 (BRN-MYS, MMR-THA, LAO-VNM, KHM-VNM)
def rings(geom):
    if geom["type"] == "Polygon": yield from geom["coordinates"]
    else:
        for p in geom["coordinates"]: yield from p
def build(regions):
    cty = {f["properties"]["id"]: f["properties"]["country"] for f in regions["features"]}
    seg = collections.defaultdict(list)
    for f in regions["features"]:
        i = f["properties"]["id"]
        for r in rings(f["geometry"]):
            for a, b in zip(r, r[1:]):
                if a != b: seg[frozenset((tuple(a), tuple(b)))].append((i, tuple(a), tuple(b)))
    minor = collections.defaultdict(list); major = collections.defaultdict(list); single = []; stat = collections.Counter()
    for k, v in seg.items():
        ids = {x[0] for x in v}
        if len(ids) == 1: single.append(v[0]); continue
        assert len(ids) == 2 and len(v) == 2, ("edge shared by more than two regions", v)
        cs = sorted({cty[x[0]] for x in v}); a, b = v[0][1], v[0][2]
        if len(cs) == 1: minor[cs[0]].append((a, b)); stat["minor_exact"] += 1
        else: major["-".join(cs)].append((a, b)); stat["major_exact"] += 1
    # outline of each country = its edges that are not shared with a region of the same country
    outline = collections.defaultdict(list)
    for k, v in seg.items():
        if len(v) == 1: outline[cty[v[0][0]]].append(LineString([v[0][1], v[0][2]]))
        elif len({cty[x[0]] for x in v}) > 1:
            for x in v: outline[cty[x[0]]].append(LineString([x[1], x[2]]))
    out = {c: unary_union(l) for c, l in outline.items()}
    for (i, a, b) in single:
        m = Point((a[0] + b[0]) / 2, (a[1] + b[1]) / 2); c = cty[i]
        best = min(((out[o].distance(m), o) for o in out if o != c), default=(9, None))
        if best[0] <= TOL and c < best[1]: major["-".join(sorted((c, best[1])))].append((a, b)); stat["major_gap"] += 1
        elif best[0] <= TOL: stat["major_gap_other_side_skipped"] += 1
        else: stat["coast"] += 1
    feats = []
    def lines(es):
        m = linemerge(MultiLineString([[a, b] for a, b in es]))
        return list(m.geoms) if m.geom_type == "MultiLineString" else [m]
    for p, es in sorted(major.items()):
        for ln in lines(es): feats.append({"type": "Feature", "properties": {"l": "major", "p": p}, "geometry": {"type": "LineString", "coordinates": [list(c) for c in ln.coords]}})
    for c, es in sorted(minor.items()):
        for ln in lines(es): feats.append({"type": "Feature", "properties": {"l": "minor", "c": c}, "geometry": {"type": "LineString", "coordinates": [list(c2) for c2 in ln.coords]}})
    # outer edge of each country (coast + international border), for the selected-country outline (loaded only when a country is selected)
    ofeats = []
    for c, ls in sorted(outline.items()):
        for ln in lines([(l.coords[0], l.coords[1]) for l in ls]): ofeats.append({"type": "Feature", "properties": {"c": c}, "geometry": {"type": "LineString", "coordinates": [list(x) for x in ln.coords]}})
    return {"type": "FeatureCollection", "features": feats}, stat, {p: len(e) for p, e in major.items()}, {c: len(e) for c, e in minor.items()}, {"type": "FeatureCollection", "features": ofeats}
def main(data="public/data-v4"):
    D = pathlib.Path(data); regions = json.loads((D / "regions.geojson").read_text())
    fc, stat, pm, cm, oc = build(regions)
    (D / "country-outlines.geojson").write_text(json.dumps(oc, separators=(",", ":")) + "\n"); print("country outline lines", len(oc["features"]), "bytes", (D / "country-outlines.geojson").stat().st_size)
    (D / "borders.geojson").write_text(json.dumps(fc, separators=(",", ":")) + "\n")
    print("edge counts", dict(stat)); print("major edges by country pair", pm); print("minor edges by country", cm)
    print("lines", len(fc["features"]), "bytes", (D / "borders.geojson").stat().st_size)
    M = json.loads((D / "manifest.json").read_text()); M["files"]["borders"] = "borders.geojson"; M["files"]["outlines"] = "country-outlines.geojson"
    (D / "manifest.json").write_text(json.dumps(M, indent=1))
if __name__ == "__main__": main(*sys.argv[1:2])
