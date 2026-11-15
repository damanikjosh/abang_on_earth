import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, statSync } from "node:fs";

// borders.geojson = two levels derived from regions.geojson by scripts/build_borders.py (coast edges in neither)
const D = new URL("../public/data-v4/", import.meta.url);
const B = JSON.parse(readFileSync(new URL("borders.geojson", D), "utf8")) as { features: { properties: { l: string; p?: string; c?: string }; geometry: { type: string; coordinates: number[][] } }[] };
const R = JSON.parse(readFileSync(new URL("regions.geojson", D), "utf8")) as { features: { properties: { id: string; country: string }; geometry: { type: string; coordinates: unknown } }[] };
const major = new Set(B.features.filter((f) => f.properties.l === "major").map((f) => f.properties.p));
const minor = new Set(B.features.filter((f) => f.properties.l === "minor").map((f) => f.properties.c));

test("manifest registers the file and the file stays small", () => {
  assert.equal(JSON.parse(readFileSync(new URL("manifest.json", D), "utf8")).files.borders, "borders.geojson");
  assert.ok(statSync(new URL("borders.geojson", D)).size < 500_000);
});
test("only two levels, all lines", () => {
  assert.ok(B.features.every((f) => ["major", "minor"].includes(f.properties.l) && f.geometry.type === "LineString" && f.geometry.coordinates.length >= 2));
});
test("major = international: the known borders are there, each pair of two different countries, never a country with itself", () => {
  for (const p of ["IDN-MYS", "IDN-TLS", "BRN-MYS", "MMR-THA", "LAO-THA", "KHM-THA", "KHM-VNM", "LAO-VNM", "MYS-THA", "MYS-SGP"]) assert.ok(major.has(p), p);
  for (const p of major) { const [a, b] = p!.split("-"); assert.notEqual(a, b); }
});
test("minor = province: every country with 2+ regions has some, and none is labelled with a pair", () => {
  const n: Record<string, number> = {};
  for (const f of R.features) n[f.properties.country] = (n[f.properties.country] ?? 0) + 1;
  for (const [c, k] of Object.entries(n)) if (k >= 2) assert.ok(minor.has(c), c);
  assert.ok([...minor].every((c) => !c!.includes("-")));
});
test("every vertex of a border line is a vertex of regions.geojson (derived, not redrawn) for the exact-shared levels", () => {
  const v = new Set<string>();
  const walk = (x: unknown): void => { if (Array.isArray(x) && typeof x[0] === "number") v.add(`${x[0]},${x[1]}`); else if (Array.isArray(x)) x.forEach(walk); };
  for (const f of R.features) walk(f.geometry.coordinates);
  for (const f of B.features) for (const c of f.geometry.coordinates) assert.ok(v.has(`${c[0]},${c[1]}`));
});
