// pure state of the layer panel and its link encoding, incl. today's share-link keys (l f o p).
import test from "node:test";
import assert from "node:assert/strict";
import { initialState, activeOrder, setActive, applyActiveOrder, setOpacity, opacityOf, setGroupOpen, setOpenGroups, encodeState, decodeState, clampOpacity, type Defaults } from "../src/layerpanel/state.ts";

const D: Defaults = { order: ["fire-viirs", "fire-modis", "fire-harm", "metric", "loss", "peat", "palm"], active: ["fire-viirs", "fire-modis", "metric"], open: ["fires"], keepInLegacy: ["metric"] };
const arr = (s: ReadonlySet<string>) => [...s].sort();

test("initial state: active rows in default order, unknown default ids dropped, duplicates removed", () => {
  const s = initialState({ ...D, active: ["metric", "nope", "fire-viirs", "metric"] });
  assert.deepEqual(activeOrder(s), ["fire-viirs", "metric"]);
  assert.deepEqual(initialState({ order: ["a", "a", "b"], active: [], open: [] }).order, ["a", "b"]);
});
test("setActive: switching on/off, unknown ids ignored, input state never changed", () => {
  const s0 = initialState(D), s1 = setActive(s0, "loss", true);
  assert.deepEqual(activeOrder(s1), ["fire-viirs", "fire-modis", "metric", "loss"]);
  assert.deepEqual(activeOrder(s0), ["fire-viirs", "fire-modis", "metric"]);
  assert.equal(setActive(s0, "nope", true), s0);
  assert.deepEqual(activeOrder(setActive(s1, "fire-viirs", false)), ["fire-modis", "metric", "loss"]);
});
test("applyActiveOrder: active rows take over each other's slots, inactive rows stay put", () => {
  let s = setActive(initialState(D), "loss", true);                 // order: viirs modis harm metric loss peat palm ; active: viirs modis metric loss
  s = applyActiveOrder(s, ["loss", "metric", "fire-modis", "fire-viirs"]);
  assert.deepEqual(s.order, ["loss", "metric", "fire-harm", "fire-modis", "fire-viirs", "peat", "palm"]);
  assert.deepEqual(activeOrder(s), ["loss", "metric", "fire-modis", "fire-viirs"]);
});
test("applyActiveOrder: unknown, inactive and duplicate ids are ignored; missing active rows are kept after the listed ones", () => {
  const s = applyActiveOrder(initialState(D), ["metric", "peat", "zzz", "metric"]);
  assert.deepEqual(activeOrder(s), ["metric", "fire-viirs", "fire-modis"]);
  assert.equal(s.order.length, D.order.length);
  assert.deepEqual([...s.order].sort(), [...D.order].sort());
});
test("opacity: clamped to 0..1 in steps of 0.05, 1 is not stored, unknown rows ignored", () => {
  assert.equal(clampOpacity(0.123), 0.1); assert.equal(clampOpacity(-3), 0); assert.equal(clampOpacity(7), 1); assert.equal(clampOpacity(NaN), 1);
  let s = setOpacity(initialState(D), "loss", 0.5);
  assert.equal(opacityOf(s, "loss"), 0.5); assert.equal(opacityOf(s, "peat"), 1);
  s = setOpacity(s, "loss", 1); assert.equal(s.opacity.size, 0);
  assert.equal(setOpacity(s, "nope", 0.4).opacity.size, 0);
  assert.equal(opacityOf(setOpacity(s, "loss", 0), "loss"), 0);
});
test("groups: open/close, no duplicates", () => {
  let s = setGroupOpen(initialState(D), "land", true); s = setGroupOpen(s, "land", true);
  assert.deepEqual(s.open, ["fires", "land"]);
  assert.deepEqual(setGroupOpen(s, "fires", false).open, ["land"]);
  assert.deepEqual(setOpenGroups(s, ["a", "a", "b"]).open, ["a", "b"]);
});
test("default state encodes to an empty string and decodes back to itself", () => {
  const s = initialState(D);
  assert.equal(encodeState(s, D), "");
  const r = decodeState("", D); assert.equal(r.legacy, false);
  assert.deepEqual(r.state.order, s.order); assert.deepEqual(arr(r.state.active), arr(s.active)); assert.deepEqual(r.state.open, s.open);
});
test("round trip: active set, order, opacity, open groups", () => {
  let s = setActive(initialState(D), "loss", true);
  s = setActive(s, "fire-modis", false);
  s = applyActiveOrder(s, ["loss", "metric", "fire-viirs"]);
  s = setOpacity(s, "loss", 0.35); s = setOpacity(s, "metric", 0.7);
  s = setOpenGroups(s, ["land", "plant"]);
  const enc = encodeState(s, D);
  assert.match(enc, /^s=loss,metric,fire-viirs&o=.*&p=loss:0\.35~metric:0\.7&g=land,plant$/);
  const r = decodeState("#" + enc, D);
  assert.equal(r.legacy, false);
  assert.deepEqual(r.state.order, s.order); assert.deepEqual(arr(r.state.active), arr(s.active));
  assert.deepEqual([...r.state.opacity], [...s.opacity]); assert.deepEqual(r.state.open, s.open);
  assert.equal(encodeState(r.state, D), enc);
});
test("nothing on is written as an empty s and read back as nothing on (not as the defaults)", () => {
  let s = initialState(D); for (const i of D.active) s = setActive(s, i, false);
  const enc = encodeState(s, D); assert.equal(enc, "s=");
  assert.equal(decodeState(enc, D).state.active.size, 0);
});
test("all groups closed is written as an empty g", () => {
  const s = setOpenGroups(initialState(D), []);
  assert.equal(encodeState(s, D), "g="); assert.deepEqual(decodeState("g=", D).state.open, []);
});
test("unknown ids are ignored in every key; garbage never throws", () => {
  const r = decodeState("s=loss,__proto__,constructor,nope,loss&o=zzz,peat,peat,palm&p=nope:0.2~loss:abc~peat:0.5~palm:&g=land,,land", D).state;
  assert.deepEqual(arr(r.active), ["loss"]);
  assert.deepEqual(r.order, ["peat", "palm", "fire-viirs", "fire-modis", "fire-harm", "metric", "loss"]);
  assert.deepEqual([...r.opacity], [["peat", 0.5]]);
  assert.deepEqual(r.open, ["land"]);
  for (const bad of ["%", "s=%E0%A4%A", "&&&=", "p=~~:", "o=,,,", "x".repeat(100000), "s=" + "a,".repeat(50000)]) assert.doesNotThrow(() => decodeState(bad, D));
  assert.equal(({} as Record<string, unknown>).polluted, undefined);
});
test("opacity from a link is clamped", () => {
  const r = decodeState("p=loss:5~peat:-1~palm:0.123", D).state;
  assert.deepEqual([...r.opacity].sort(), [["palm", 0.1], ["peat", 0]]); // loss 5 -> 1 = default, not stored
});
test("accepts a URLSearchParams and a plain record as input", () => {
  assert.deepEqual(arr(decodeState(new URLSearchParams("s=peat"), D).state.active), ["peat"]);
  assert.deepEqual(arr(decodeState({ s: "palm", x: undefined }, D).state.active), ["palm"]);
});
test("today's share-link format: l (context layers), f (fire layers without prefix), o, p", () => {
  const r = decodeState("m=2019-09&r=all&k=viirs_eq&v=110.1,0.4,5&l=loss,peat&o=peat,fire-viirs,loss&f=viirs&p=loss:0.5~fire-viirs:0.35", D);
  assert.equal(r.legacy, true);
  assert.deepEqual(arr(r.state.active), ["fire-viirs", "loss", "metric", "peat"]); // metric: kept on by keepInLegacy
  assert.deepEqual(r.state.order.slice(0, 3), ["peat", "fire-viirs", "loss"]);
  assert.deepEqual([...r.state.opacity].sort(), [["fire-viirs", 0.35], ["loss", 0.5]]);
});
test("old link: no f key means the default fire layers, empty f means none, no l means no context layers", () => {
  assert.deepEqual(arr(decodeState("l=loss", D).state.active), ["fire-modis", "fire-viirs", "loss", "metric"]);
  assert.deepEqual(arr(decodeState("l=loss&f=", D).state.active), ["loss", "metric"]);
  assert.deepEqual(arr(decodeState("f=modis,harm,bogus", D).state.active), ["fire-harm", "fire-modis", "metric"]);
});
test("old link opacity 0.1 minimum and old ids that no longer exist are dropped", () => {
  const r = decodeState("l=loss,tmfdef&f=viirs,old&p=tmfdef:0.5~loss:0.1", D);
  assert.deepEqual(arr(r.state.active), ["fire-viirs", "loss", "metric"]);
  assert.deepEqual([...r.state.opacity], [["loss", 0.1]]);
});
test("the new s key wins over old keys in the same link", () => {
  const r = decodeState("s=peat&l=loss&f=viirs", D);
  assert.equal(r.legacy, false); assert.deepEqual(arr(r.state.active), ["peat"]);
});
