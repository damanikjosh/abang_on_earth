import test from "node:test";
import assert from "node:assert/strict";
import { firstSentence, rangeText, coverageNotes, regionGapNotes, chipFor, isRoutineStatus, esc } from "../src/layerinfo.ts";

const cs = [{ code: "IDN", name: "Indonesia" }, { code: "MYS", name: "Malaysia" }, { code: "LAO", name: "Laos" }];
test("firstSentence", () => {
  assert.equal(firstSentence("Fire detections on forest. This includes more."), "Fire detections on forest.");
  assert.equal(firstSentence("No full stop here"), "No full stop here");
});
test("rangeText", () => {
  assert.equal(rangeText({ min: "2001-01", max: "2025-12" }), "2001-01 to 2025-12");
  assert.equal(rangeText({ min: 2001 }), "from 2001");
  assert.equal(rangeText({}), "");
});
test("coverageNotes lists the countries without data, with the layer's own gap note", () => {
  assert.deepEqual(coverageNotes({ coverage: ["IDN", "MYS"], gap_note: "No palm data" }, cs), ["No palm data. Not available in: Laos."]);
  assert.deepEqual(coverageNotes({}, cs), []);
  assert.deepEqual(coverageNotes({ coverage: ["IDN", "MYS", "LAO"] }, cs), []);
});
test("regionGapNotes groups identical texts", () => {
  const d = { region_gaps: { a: "x", b: "x", c: "x", d: "x", e: "y" } };
  assert.deepEqual(regionGapNotes(d, (i) => i.toUpperCase()), ["x (4 regions)", "y (E)"]);
});
test("chips: none for ordinary real data, placeholder / no data here / partial data / <country> only otherwise", () => {
  assert.equal(chipFor({ coverage: ["IDN", "MYS", "LAO"] }, cs, "IDN", ""), null);
  assert.equal(chipFor({ placeholder: true, coverage: ["IDN"] }, cs, "MYS", "gap")?.text, "placeholder");
  assert.equal(chipFor({ coverage: ["IDN", "MYS"] }, cs, "LAO", "")?.text, "no data here");
  assert.equal(chipFor({ coverage: ["IDN", "MYS"] }, cs, "MYS", "hole")?.text, "partial data");
  assert.equal(chipFor({ coverage: ["IDN"] }, cs, "IDN", "")?.text, "Indonesia only");
  assert.equal(chipFor({ coverage: ["IDN"] }, cs, undefined, "")?.text, "Indonesia only");
});
test("routine statuses are not warnings", () => {
  for (const t of ["Shown", "Showing 2019-05", "Showing up to 2019", "Showing share of area, up to 2019", "Showing 2019 only (share of area burned that year)", "Shown (3 of 5 classes)", "Individual detections (size = sensor footprint)", "Forest-loss fires only. Individual detections (size = sensor footprint)", ""]) assert.ok(isRoutineStatus(t), t);
  for (const t of ["Colored cells count detections per area; zoom in to zoom 9 for individual detections", "Not available for this month", "Data not available (map file missing)", "Zoom in 2 more steps (to zoom 7) to see forest loss — country-scale view is being rebuilt", "Showing 2000: nearest available year at or before 2003 (this layer has no file for 2003)", "No VIIRS data before 2012", "2 of 5 yearly files available so far", "No class selected", "Forest-loss fires only. Colored cells count detections per area; zoom in to zoom 9 for individual detections"]) assert.ok(!isRoutineStatus(t), t);
});
test("esc", () => assert.equal(esc(`<a href="x">&</a>`), "&lt;a href=&quot;x&quot;&gt;&amp;&lt;/a&gt;"));
