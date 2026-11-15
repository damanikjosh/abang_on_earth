// the map type is only "sat" when the link says so; anything else is the plain map.
import test from "node:test";
import assert from "node:assert/strict";
import { parseBase } from "../src/sharelink.ts";

test("map type: sat only for b=sat, everything else is the plain map", () => {
  assert.equal(parseBase("sat"), "sat");
  for (const v of [undefined, "", "plain", "SAT", "satellite", "1"]) assert.equal(parseBase(v), "plain");
});
