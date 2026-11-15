import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { displayName } from "../src/names.ts";

test("displayName", () => {
  assert.equal(displayName("Roi Et Province"), "Roi Et");
  assert.equal(displayName("NORTH-EAST REGION"), "North-East Region");
  assert.equal(displayName("CENTRAL REGION"), "Central Region");
  assert.equal(displayName("Saigang"), "Sagaing");
  for (const a of ["ARMM", "CAR", "NCR", "Bangkok", "Bà Rịa–Vũng Tàu", "Calabarzon"]) assert.equal(displayName(a), a);
  assert.equal(displayName("  Nan   Province "), "Nan");
});
test("real regions.geojson: no duplicate display names inside a country, no 'Province' suffix, no long ALL-CAPS", () => {
  const g = JSON.parse(readFileSync("public/data-v4/regions.geojson", "utf8")).features as { properties: { id: string; name: string; country?: string } }[];
  const seen = new Set<string>();
  for (const f of g) {
    const d = displayName(f.properties.name), key = `${f.properties.country}|${d}`;
    assert.ok(!seen.has(key), `duplicate ${key}`); seen.add(key);
    assert.ok(!/ Province$/.test(d) && !(d.length > 4 && d === d.toUpperCase()), d);
  }
  assert.equal(g.length, 287);
});
