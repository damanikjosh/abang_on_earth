import test from "node:test";
import assert from "node:assert/strict";
import { covered, gapNote, countryOf, DEFAULT_GAP } from "../src/coverage.ts";

// a fake two-country manifest: palm planting years exist for Indonesia only
const manifest = {
  regions: [{ id: "riau", country: "IDN" }, { id: "kampong-cham", country: "KHM" }, { id: "legacy" }],
  layers: [
    { id: "loss", coverage: ["IDN", "KHM"] },
    { id: "palm", coverage: ["IDN"], gap_note: "No dated plantation data for this country" },
    { id: "plain-gap", coverage: ["IDN"] },
    { id: "everywhere" },
  ],
};
const note = (layer: string, region: string) => gapNote(manifest.layers.find((l) => l.id === layer)!, countryOf(manifest.regions.find((r) => r.id === region)));

test("Indonesia (and a region with no country field) shows no label for any layer", () => {
  for (const l of manifest.layers) { assert.equal(note(l.id, "riau"), ""); assert.equal(note(l.id, "legacy"), ""); }
});
test("a layer without `coverage` covers every country", () => { assert.equal(note("everywhere", "kampong-cham"), ""); assert.ok(covered({}, "XYZ")); });
test("Cambodia: covered layer silent, uncovered layer shows its note, default text otherwise", () => {
  assert.equal(note("loss", "kampong-cham"), "");
  assert.equal(note("palm", "kampong-cham"), "No dated plantation data for this country");
  assert.equal(note("plain-gap", "kampong-cham"), DEFAULT_GAP);
});
test("countryOf defaults to IDN", () => { assert.equal(countryOf(undefined), "IDN"); assert.equal(countryOf(null), "IDN"); assert.equal(countryOf({}), "IDN"); assert.equal(countryOf({ country: "MYS" }), "MYS"); });
