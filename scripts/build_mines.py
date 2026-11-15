#!/usr/bin/env python3
"""Mine outlines for the 11 countries: Maus et al. 2024 global mining polygons (ODbL 1.0, includes (c) OpenStreetMap contributors),
Zenodo 10.5281/zenodo.7307210, download both from the record. Commodities come from the same record's global_mining_forest_loss.csv (list_of_commodities, per polygon id).
Output: one GeoJSON, properties id, a = area in hectares, c = commodity list ("" = none recorded), cc = ISO-3. Geometry simplified 0.00002 deg (~2 m) and rounded to 0.00001 deg (~1 m);
measured: 129,216 -> 115,096 vertices, 4.9 -> 3.1 MB (0.72 MB gzip). 4,023 polygons: small enough to ship as one file (no vector tiling needed).
usage: build_mines.py GPKG LOSS_CSV OUT_GEOJSON"""
import sys, json, geopandas as gpd, pandas as pd, shapely
ISO = ["IDN", "MYS", "BRN", "SGP", "THA", "MMR", "LAO", "KHM", "VNM", "PHL", "TLS"]
def main(gpkg, csv, out):
    g = gpd.read_file(gpkg); g = g[g.isoa3.isin(ISO)].copy()
    c = pd.read_csv(csv, usecols=["id", "list_of_commodities"], dtype=str).drop_duplicates("id").set_index("id").list_of_commodities
    g["c"] = g.id.map(c).fillna("").str.replace(",", ", ")
    g["a"] = (g["area"] * 100).round(2)                       # km2 -> ha
    g["geometry"] = shapely.set_precision(g.geometry.simplify(0.00002, preserve_topology=True).values, 0.00001)
    g = g[~g.geometry.is_empty].rename(columns={"isoa3": "cc"})[["id", "cc", "a", "c", "geometry"]].sort_values("id")
    open(out, "w").write(g.to_json(drop_id=True, na="null"))
    print(len(g), "polygons;", int((g.c != "").sum()), "with commodities;", g.groupby("cc").size().to_dict())
if __name__ == "__main__": main(*sys.argv[1:4])
