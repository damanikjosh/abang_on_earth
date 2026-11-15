// the new layers are registered in the live data folder, their files exist, and their pop-up text is right.
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, existsSync, statSync } from "node:fs";
import { mineHtml, hectares } from "../src/mines.ts";

const D = "public/data-v4", L = JSON.parse(readFileSync(`${D}/layers.json`, "utf8")).layers as Record<string, any>[];
const by = (id: string) => L.find((l) => l.id === id)!;
const ALL11 = ["IDN", "MYS", "BRN", "SGP", "THA", "MMR", "LAO", "KHM", "VNM", "PHL", "TLS"];

test("drivers: 7 classes with plain names, one file each, source + licence, 11 countries", () => {
  const d = by("drivers"); assert.ok(d); assert.equal(d.mode, "class"); assert.equal(d.placeholder, false);
  assert.deepEqual(d.classes.map((c: any) => c.id), [1, 2, 3, 4, 5, 6, 7]);
  assert.deepEqual(d.classes.map((c: any) => c.label), ["Permanent agriculture", "Hard commodities (mining)", "Shifting cultivation", "Logging", "Wildfire", "Settlements and infrastructure", "Other natural disturbance"]);
  assert.equal(new Set(d.classes.map((c: any) => c.color)).size, 7, "distinct colours");
  assert.deepEqual(d.available, ["c1", "c2", "c3", "c4", "c5", "c6", "c7"]);
  for (let i = 1; i <= 7; i++) { const f = `${D}/${d.path.replace("{class}", String(i))}`; assert.ok(existsSync(f), f); assert.ok(statSync(f).size > 100_000); assert.equal(readFileSync(f).subarray(0, 7).toString(), "PMTiles"); }
  assert.match(d.source, /Sims et al\. 2025/); assert.equal(d.licence, "CC BY 4.0"); assert.deepEqual(d.coverage, ALL11);
  for (const must of ["1 km", "2001", "wildfire", "71", "83", "fire data"]) assert.ok(d.long.includes(must), `long text mentions ${must}`);
});
test("mines: vector layer, GeoJSON file valid, source + licence with OpenStreetMap", () => {
  const m = by("mines"); assert.ok(m); assert.equal(m.mode, "vector"); assert.deepEqual(m.available, ["s"]);
  const fc = JSON.parse(readFileSync(`${D}/${m.path}`, "utf8")); assert.equal(fc.type, "FeatureCollection"); assert.equal(fc.features.length, 4023);
  assert.ok(fc.features.every((f: any) => /^(Multi)?Polygon$/.test(f.geometry.type) && ALL11.includes(f.properties.cc) && typeof f.properties.a === "number" && typeof f.properties.c === "string"));
  assert.ok(fc.features.some((f: any) => /Copper/.test(f.properties.c)) && fc.features.some((f: any) => f.properties.c === "Coal"));
  assert.equal(m.licence, "ODbL 1.0"); assert.match(m.source, /Maus et al\. 2024/); assert.match(m.source, /OpenStreetMap contributors/);
  assert.match(m.legend, /about 2019/);
});
test("mine pop-up text", () => {
  const h = mineHtml({ id: "x", cc: "IDN", a: 3520.31, c: "Copper, Gold, Silver" }, () => "Indonesia");
  assert.match(h, /Commodities: Copper, Gold, Silver/); assert.match(h, /3,520 ha/); assert.match(h, /Indonesia/); assert.match(h, /about 2019/);
  assert.match(mineHtml({ a: 2, c: "" }), /Commodity not recorded/);
  assert.match(mineHtml({ c: "<b>x</b>" }), /&lt;b&gt;/, "escaped");
  assert.equal(hectares(0.26), "0.3 ha"); assert.equal(hectares(61.43), "61 ha"); assert.equal(hectares(10353.62), "10,354 ha");
});
