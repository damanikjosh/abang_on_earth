// the homepage "Facts" row: five cards, five drawn diagrams, map links that carry an explicit layer set and only name layers/classes/months that exist.
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
const html = readFileSync("index.html", "utf8");
const row = html.slice(html.indexOf('<section class="band" id="facts"'), html.indexOf("<!-- facts:end -->"));
const layers = JSON.parse(readFileSync("public/data-v4/layers.json", "utf8")).layers as { id: string }[];
const links5 = JSON.parse(readFileSync("scripts/facts_links.json", "utf8")).links as { hash: string; start: string; action: string }[];
const fire = JSON.parse(readFileSync("public/data-v4/manifest.json", "utf8")).fire_layers.layers as { id: string; min: string; max: string; classes?: { id: number; disabled?: boolean }[] }[];

test("the Facts row exists once, sits before the technical report row, has an anchor and five cards", () => {
  assert.equal((html.match(/id="facts"/g) ?? []).length, 1);
  assert.ok(html.indexOf('id="facts"') < html.indexOf('id="paper"') && html.indexOf('id="research"') < html.indexOf('id="facts"'));
  assert.equal((row.match(/<article class="fact two"/g) ?? []).length, 5);
  assert.equal((row.match(/Open on the map and press Play/g) ?? []).length, 5);
});
test("every card has a diagram with drawn marks, a caveat line and a source line", () => {
  const cards = row.split("<article").slice(1);
  assert.equal(cards.length, 5);
  for (const c of cards) {
    assert.match(c, /<svg class="fx"[^>]*role="img"/); assert.match(c, /<(polyline|rect class="bar-)/);
    assert.match(c, /What to keep in mind\./); assert.match(c, /Source: /);
  }
});
test("every map link carries s=, a month, a view, and names only real layers, fire classes and months", () => {
  const links = [...row.matchAll(/href="app\/#([^"]+)"/g)].map((m) => new URLSearchParams(m[1].replaceAll("&amp;", "&")));
  assert.equal(links.length, 5);
  for (const c of row.split("<article").slice(1)) assert.equal((c.match(/data-fact-link/g) ?? []).length, 1, "exactly one map link per fact");
  for (const c of row.split("<article").slice(1)) assert.match(c, /fact-hint">Press Play: /);
  const ids = new Set([...layers.map((l) => l.id), ...fire.map((f) => "fire-" + f.id)]);
  for (const q of links) {
    assert.ok(q.has("s") && q.get("s") !== "", "s= present"); assert.ok(q.get("s")!.split(",").every((i) => ids.has(i)), q.get("s")!);
    assert.match(q.get("m")!, /^\d{4}-\d{2}$/); assert.match(q.get("v")!, /^-?\d+\.\d+,-?\d+\.\d+,\d+(\.\d+)?$/);
    for (const [r, cs] of (q.get("x") ?? "").split("~").filter(Boolean).map((p) => p.split(":") as [string, string])) {
      const f = fire.find((d) => "fire-" + d.id === r)!; assert.ok(f, r);
      for (const c of cs.split(".")) assert.ok(f.classes!.some((k) => String(k.id) === c), `${r} class ${c}`);
    }
    // a Play demo may start before a layer's first month (Fact 1 starts in 2011 with the VIIRS row already on, so VIIRS appears when Play reaches 2012): the layer must have data in the ACTION month, and the start must not be past its last month
    const act = links5.find((l) => l.hash.includes(q.get("m")! ) && l.start === q.get("m"))!.action;
    for (const id of q.get("s")!.split(",").filter((i) => i.startsWith("fire-"))) { const f = fire.find((d) => "fire-" + d.id === id)!; assert.ok(q.get("m")! <= f.max && act >= f.min && act <= f.max, `${id} has no data for ${act}`); }
  }
});
test("wording rules: no 'AI' for Super Intelligence, no 'hotspot', Harmonized VIIRS is called experimental and never validated", () => {
  assert.doesNotMatch(row, /\bAI\b|hotspot|NASA logo/i);
  assert.match(row, /experimental model output, not VIIRS data/); assert.doesNotMatch(row, /validated|unproven/); assert.match(row, /paper\/technical-report\.pdf/);
});
test("the diagrams and numbers are those of scripts/build_facts_data.py (no hand edits)", () => {
  execFileSync("python3", ["scripts/build_facts_data.py", "--check"], { stdio: "pipe" });
});
