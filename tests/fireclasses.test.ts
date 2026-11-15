// a fire layer may carry classes (MODIS day / night): which months are drawn from the class files.
import test from "node:test";
import assert from "node:assert/strict";
import { splitMonth, splitMonths, type FireClass } from "../src/fireclasses.ts";

const day: FireClass = { id: 1, label: "Day", path: "fire/modis-day/{month}.pmtiles", available: ["2002-09", "2002-10"] };
const night: FireClass = { id: 2, label: "Night", path: "fire/modis-night/{month}.pmtiles", available: ["2002-09"] };
test("a layer without classes is never split", () => {
  assert.equal(splitMonth({}, "2002-09"), false);
  assert.equal(splitMonth({ classes: [] }, "2002-09"), false);
  assert.deepEqual(splitMonths({}), []);
});
test("a month is drawn from the class files only when EVERY class has tiles for it", () => {
  const d = { classes: [day, night] };
  assert.equal(splitMonth(d, "2002-09"), true);
  assert.equal(splitMonth(d, "2002-10"), false); // night missing: the whole month falls back to the layer's own file
  assert.equal(splitMonth(d, "2019-09"), false);
  assert.deepEqual(splitMonths(d), ["2002-09"]);
});
test("a class without an available list counts as present in every month", () => {
  assert.equal(splitMonth({ classes: [{ ...day, available: undefined }, { ...night, available: undefined }] }, "1999-01"), true);
});

import { densValue, densFilter, isMerged } from "../src/fireclasses.ts";
test("density cells of day + night: one drawing per cell with the combined colour", () => {
  const d = { classes: [day, night] };
  assert.deepEqual(densValue(false), ["get", "b"]);
  assert.deepEqual(densValue(true), ["coalesce", ["get", "bt"], ["get", "b"]]);
  assert.equal(densFilter(d, 1, true), null); // the first class draws every cell
  assert.deepEqual(densFilter(d, 2, true), ["==", ["coalesce", ["get", "o"], 0], 0]); // the second only the cells the first lacks
  assert.equal(densFilter(d, 2, false), null); // one class ticked: its own cells, its own bins
  assert.equal(isMerged(d, () => true), true);
  assert.equal(isMerged(d, (id) => id === 1), false);
  assert.equal(isMerged({ classes: [day] }, () => true), false);
});
