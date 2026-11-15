//  / R2: text a visitor reads in the layer pop-ups has no unexplained acronyms and no unverifiable parenthetical.
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
const L = JSON.parse(readFileSync("public/data-v4/layers.json", "utf8")).layers as { id: string; legend: string; long?: string }[];
const M = JSON.parse(readFileSync("public/data-v4/manifest.json", "utf8")).fire_layers.layers as { id: string; legend: string }[];
test("legend texts: no GLAD-L/RADD/SDPT/S-NPP/C6.1 acronyms and no 'timeline starts in Nov 2000'", () => {
  for (const d of [...L, ...M]) for (const t of [d.legend, (d as { long?: string }).long ?? ""]) assert.doesNotMatch(t, /GLAD|RADD|SDPT|S-NPP|C6\.1|Nov 2000/, `${d.id}: ${t.slice(0, 80)}`);
});

test("manifest texts a visitor can reach (title, units, metrics, sources, fire legends): no S-NPP, C6.1 or 'hotspot'", () => {
  const m = JSON.parse(readFileSync("public/data-v4/manifest.json", "utf8"));
  assert.doesNotMatch(JSON.stringify([m.title, m.units, m.metrics, m.sources, m.fire_layers.layers.map((d: { legend: string }) => d.legend)]), /S-NPP|C6\.1|hotspot/i);
});
