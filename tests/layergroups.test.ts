// every row of the layer list belongs to exactly one group or is hidden on purpose; the group order is fixed.
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { GROUPS, HIDDEN_ROWS, REMOVED_ROWS, DEFAULT_OPEN, groupOfRow } from "../src/layergroups.ts";

const root = new URL("../public/", import.meta.url);
const folder = JSON.parse(readFileSync(new URL("data-version.json", root), "utf8")).base as string;
const layers = JSON.parse(readFileSync(new URL(folder + "layers.json", root), "utf8")).layers as { id: string; placeholder?: boolean }[];
const manifest = JSON.parse(readFileSync(new URL(folder + "manifest.json", root), "utf8"));
const rows = ["regions", "countries", ...layers.map((l) => l.id), ...(manifest.fire_layers?.layers ?? []).map((l: { id: string }) => "fire-" + l.id)];

test("every row id of layers.json, manifest.fire_layers and the colour overlay is in a group or hidden", () => {
  for (const id of rows) assert.ok(groupOfRow(id) || HIDDEN_ROWS.includes(id) || REMOVED_ROWS.includes(id), `row ${id} has no group`);
});
test("no row is in two groups; no group is empty; hidden rows are in no group", () => {
  const seen = new Set<string>();
  for (const g of GROUPS) { assert.ok(g.layers.length > 0, g.id); for (const id of g.layers) { assert.ok(!seen.has(id), `${id} twice`); seen.add(id); } }
  for (const h of [...HIDDEN_ROWS, ...REMOVED_ROWS]) assert.ok(!seen.has(h), `${h} hidden and grouped`);
});
test("every id in a group exists (no stale names)", () => {
  for (const g of GROUPS) for (const id of g.layers) assert.ok(rows.includes(id), `${id} in group ${g.id} is not a row`);
});
test("the hidden rows are exactly the placeholder context layers", () => {
  assert.deepEqual([...HIDDEN_ROWS].sort(), layers.filter((l) => l.placeholder).map((l) => l.id).sort());
});
test("group order is fixed and the default open groups exist", () => {
  assert.deepEqual(GROUPS.map((g) => g.id), ["fires", "colour", "land", "plant", "more"]);
  for (const o of DEFAULT_OPEN) assert.ok(GROUPS.some((g) => g.id === o));
});
