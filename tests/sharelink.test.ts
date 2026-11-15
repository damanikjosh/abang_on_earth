// share-link keys x (class switches), p (opacity), t (open tab).
import test from "node:test";
import assert from "node:assert/strict";
import { encodeOff, parseOff, encodeOpacity, parseOpacity, parseTab, clampOpacity } from "../src/sharelink.ts";

const valid = (row: string, c: number) => row === "drivers" && c >= 1 && c <= 7;
test("class switches: encode, parse, round trip; unknown rows and classes are dropped", () => {
  assert.equal(encodeOff({ drivers: [5, 3] }), "drivers:3.5");
  assert.equal(encodeOff({ drivers: [], mines: [1] }), "mines:1");
  assert.deepEqual(parseOff("drivers:3.5", valid), { drivers: [3, 5] });
  assert.deepEqual(parseOff(encodeOff({ drivers: [1, 7] }), valid), { drivers: [1, 7] });
  assert.deepEqual(parseOff("drivers:3.9.x.3~nope:1~:2~drivers", valid), { drivers: [3] });
  assert.deepEqual(parseOff(undefined, valid), {}); assert.deepEqual(parseOff("", valid), {});
});
test("opacity: only non-default values are written; parsing clamps to the slider range", () => {
  assert.equal(encodeOpacity({ loss: 0.5, palm: 1, "fire-viirs": 0.35 }), "loss:0.5~fire-viirs:0.35");
  assert.equal(encodeOpacity({ loss: 1 }), "");
  const ok = (id: string) => ["loss", "fire-viirs"].includes(id);
  assert.deepEqual(parseOpacity("loss:0.5~fire-viirs:0.35", ok), { loss: 0.5, "fire-viirs": 0.35 });
  assert.deepEqual(parseOpacity("loss:7~fire-viirs:-3~nope:0.5~loss2:", ok), { loss: 1, "fire-viirs": 0.1 });
  assert.deepEqual(parseOpacity("loss:abc~loss:", ok), {});
  assert.equal(clampOpacity(0.52), 0.5); assert.equal(clampOpacity(0.99), 1);
});
test("tab: only the three real tabs", () => {
  assert.equal(parseTab("layers"), "layers"); assert.equal(parseTab("details"), "details"); assert.equal(parseTab("timeline"), "timeline");
  assert.equal(parseTab("x"), null); assert.equal(parseTab(undefined), null);
});

// the metric colour overlay row; every link made before it has no rg= key and must still show the colours
import { parseRegionsOn } from "../src/sharelink.ts";
test("rg=0 switches the metric colour overlay off; no key, rg=1 or junk keep it on (old links)", () => {
  assert.equal(parseRegionsOn(undefined), true);
  assert.equal(parseRegionsOn("0"), false);
  assert.equal(parseRegionsOn("1"), true);
  assert.equal(parseRegionsOn("off"), true);
  assert.equal(parseRegionsOn(""), true);
});
