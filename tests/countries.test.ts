import { test } from "node:test";
import assert from "node:assert/strict";
import { parseCountries, unionBounds, regionGroups, startCountry, hiddenEstimate, regionGap, boundsOf } from "../src/countries.ts";

const C = [
  { code: "IDN", name: "Indonesia", total: "indonesia", bounds: [95, -11, 141, 6] as [number, number, number, number] },
  { code: "MYS", name: "Malaysia", total: "malaysia", bounds: [99.6, 0.8, 119.3, 7.4] as [number, number, number, number] },
];
const M = { countries: C, all: { id: "all", name: "All four countries" } };

test("parseCountries: needs two well-formed countries; anything else = single-country data", () => {
  assert.deepEqual(parseCountries({ countries: C, all: M.all }), M);
  assert.equal(parseCountries({ countries: C })!.all, null);
  for (const m of [null, {}, { countries: ["IDN", "MYS"] }, { countries: [C[0]] }, { countries: [C[0], { code: "X" }] }, { countries: [C[0], { ...C[1], bounds: [1, 2, 3] }] }, "x", 3]) assert.equal(parseCountries(m), null, JSON.stringify(m));
});
test("unionBounds / boundsOf", () => {
  assert.deepEqual(unionBounds(C), [[95, -11], [141, 7.4]]);
  assert.deepEqual(boundsOf(C[1] as never), [[99.6, 0.8], [119.3, 7.4]]);
});
test("regionGroups: all = all-total + one group per country; a country = its total then its regions", () => {
  const of = (c: string) => (c === "IDN" ? ["riau"] : ["mys-sabah"]);
  assert.deepEqual(regionGroups(M, "all", of), [{ label: null, ids: ["all"] }, { label: "Indonesia", ids: ["indonesia", "riau"] }, { label: "Malaysia", ids: ["malaysia", "mys-sabah"] }]);
  assert.deepEqual(regionGroups(M, "MYS", of), [{ label: null, ids: ["malaysia", "mys-sabah"] }]);
  assert.deepEqual(regionGroups(M, "XXX", of), []);
  assert.deepEqual(regionGroups({ countries: C, all: null }, "all", of).map((g) => g.label), ["Indonesia", "Malaysia"]);
});
test("startCountry: the region's country wins; old links without c= work; default all", () => {
  const co = (id: string) => ({ riau: "IDN", "mys-sabah": "MYS", malaysia: "MYS", indonesia: "IDN" } as Record<string, string>)[id];
  assert.equal(startCountry(M, "riau", undefined, co), "IDN");   // link saved before the change
  assert.equal(startCountry(M, "mys-sabah", "IDN", co), "MYS");
  assert.equal(startCountry(M, "all", "MYS", co), "all");
  assert.equal(startCountry(M, undefined, "MYS", co), "MYS");
  assert.equal(startCountry(M, undefined, undefined, co), "all");
  assert.equal(startCountry(M, "nonsense", "nonsense", co), "all");
  assert.equal(startCountry({ countries: C, all: null }, undefined, undefined, co), "IDN");
});
test("hiddenEstimate: only the flagged VIIRS-equivalent months of a series marked unreliable", () => {
  const s = { viirs_eq_unreliable: true, viirs_eq_flag: [1, 1, 0] };
  assert.equal(hiddenEstimate(s, "viirs_eq", 0), true);
  assert.equal(hiddenEstimate(s, "viirs_eq", 2), false);   // observed month
  assert.equal(hiddenEstimate(s, "modis_eq", 0), false);   // other metric
  assert.equal(hiddenEstimate({ viirs_eq_flag: [1] }, "viirs_eq", 0), false);
  assert.equal(hiddenEstimate(undefined, "viirs_eq", 0), false);
  assert.equal(hiddenEstimate({ viirs_eq_unreliable: true }, "viirs_eq", 0), false);
});
test("regionGap: per-region note of a layer", () => {
  assert.equal(regionGap({ region_gaps: { "mys-sarawak": "No palm data over about 20 % of this region" } }, "mys-sarawak"), "No palm data over about 20 % of this region");
  assert.equal(regionGap({}, "x"), "");
});

import { coveragePhrase, ASEAN } from "../src/countries.ts";
const mk = (codes: string[]) => codes.map((c) => ({ code: c, name: c + "-name" }));
test("coverage phrase: the full 11-country set -> Southeast Asia (across), in any order, with the full list kept", () => {
  const r = coveragePhrase(mk([...ASEAN].reverse())); assert.equal(r.phrase, "Southeast Asia"); assert.equal(r.prep, "across"); assert.ok(r.full.endsWith("and IDN-name"));
});
test("coverage phrase: 1-4 countries list their names (four countries, Indonesia only = one)", () => {
  assert.equal(coveragePhrase(mk(["IDN"])).phrase, "IDN-name");
  assert.equal(coveragePhrase(mk(["IDN", "MYS", "BRN", "SGP"])).phrase, "IDN-name, MYS-name, BRN-name and SGP-name");
});
test("coverage phrase: any other larger set -> N countries in Southeast Asia", () => {
  assert.equal(coveragePhrase(mk(["IDN", "MYS", "BRN", "SGP", "THA"])).phrase, "5 countries in Southeast Asia");
  assert.equal(coveragePhrase(mk([...ASEAN.slice(0, 10), "XXX"])).phrase, "11 countries in Southeast Asia");
});

import { geomBounds } from "../src/countries.ts";
test("geomBounds: Polygon and MultiPolygon bbox; anything else null", () => {
  assert.deepEqual(geomBounds({ type: "Polygon", coordinates: [[[1, 2], [5, 2], [5, 9], [1, 2]]] }), [[1, 2], [5, 9]]);
  assert.deepEqual(geomBounds({ type: "MultiPolygon", coordinates: [[[[1, 2], [3, 4], [1, 2]]], [[[10, -3], [11, -2], [10, -3]]]] }), [[1, -3], [11, 4]]);
  for (const g of [null, {}, { type: "Point", coordinates: [1, 2] }, { type: "Polygon", coordinates: [] }, "x"]) assert.equal(geomBounds(g), null);
});
