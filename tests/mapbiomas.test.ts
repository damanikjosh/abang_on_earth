// MapBiomas rows, additive by year (mode cumfile like "Oil palm"): rows, year files, licence, group, text. (The variant-picker code path stays in src/ but no row uses it.)
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, existsSync, openSync, readSync } from "node:fs";
import { encodeVariants, parseVariants } from "../src/sharelink.ts";
import { GROUPS, HIDDEN_ROWS } from "../src/layergroups.ts";

const L = JSON.parse(readFileSync("public/data-v4/layers.json", "utf8")).layers as any[];
const IDS = ["mb_palm", "mb_pulp", "mb_mine"], FILES = { mb_palm: "palm", mb_pulp: "pulp", mb_mine: "mine" } as Record<string, string>;
const NAMES = { mb_palm: "Oil palm (MapBiomas)", mb_pulp: "Pulpwood plantation (MapBiomas)", mb_mine: "Mining (MapBiomas)" } as Record<string, string>;
const YEARS = Array.from({ length: 23 }, (_, i) => String(2001 + i));

test("three rows like Oil palm: mode cumfile, 2001-2023, one view, no picker", () => {
  for (const id of IDS) {
    const d = L.find((x) => x.id === id); assert.ok(d, id);
    assert.equal(d.mode, "cumfile"); assert.equal(d.title, NAMES[id]); assert.equal(d.placeholder, false); assert.equal(d.min, 2001); assert.equal(d.max, 2023);
    assert.equal(d.variants, undefined); assert.deepEqual(d.available, YEARS); assert.equal(d.path, `mapbiomas/${FILES[id]}_{year}.pmtiles`);
  }
});
test("every year file exists, is a PMTiles file, and files only grow with the year", () => {
  for (const id of IDS) {
    let prev = 0;
    for (const y of YEARS) {
      const p = `public/data-v4/${L.find((x) => x.id === id).path.replace("{year}", y)}`; assert.ok(existsSync(p), p);
      const b = Buffer.alloc(7), fd = openSync(p, "r"); readSync(fd, b, 0, 7, 0); assert.equal(b.toString("ascii"), "PMTiles");
      const n = readFileSync(p).length; assert.ok(n >= prev * 0.999, `${p} smaller than the year before`); prev = n;
    }
  }
});
test("the old variant files are gone from public (they are in git history)", () => { for (const v of ["year", "share", "forest", "in2024"]) assert.ok(!existsSync(`public/data-v4/mapbiomas/palm_${v}.pmtiles`)); });
test("Indonesia only; licence, source and the plain-words caveats are on the layer", () => {
  for (const id of IDS) {
    const d = L.find((x) => x.id === id);
    assert.deepEqual(d.coverage, ["IDN"]); assert.match(d.licence, /CC BY-SA/); assert.match(d.source, /MapBiomas Indonesia Collection 4 v2/);
    const imp = ([] as string[]).concat(d.important).join(" ");
    assert.match(imp, /first became the class/); assert.match(imp, /only grows/); assert.match(imp, /not MapBiomas' raw map/);
    assert.match(d.long, /plus or minus 2 years/); assert.match(d.long, /2023/);
  }
  const palm = ([] as string[]).concat(L.find((x) => x.id === "mb_palm").important).join(" ");
  assert.match(palm, /2001/); assert.match(palm, /12 %/); assert.match(palm, /Papua/);
  assert.notEqual(L.find((x) => x.id === "mb_palm").color.toLowerCase(), "#7a8b3c");
  assert.match(readFileSync("public/data-v4/mapbiomas/MANIFEST.json", "utf8"), /CC-BY-SA/); assert.match(readFileSync("public/data-v4/mapbiomas/ATTRIBUTION.txt", "utf8"), /CC-BY-SA/);
});
test("the rows are in the plantations and mines group and are not hidden", () => {
  const g = GROUPS.find((x) => x.id === "plant")!; for (const id of IDS) { assert.ok(g.layers.includes(id)); assert.ok(!HIDDEN_ROWS.includes(id)); }
});
test("link key vr (kept for the variant code path): round trip, unknown dropped", () => {
  assert.equal(encodeVariants({ a: "b" }), "a:b"); assert.deepEqual(parseVariants("a:b~x:y", (r) => r === "a"), { a: "b" });
});
