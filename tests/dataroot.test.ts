// node --test tests/   (Node >= 22.18 strips types)
import test from "node:test";
import assert from "node:assert/strict";
import { cleanBase, parsePointer, dataUrl, loadPointer, loadFirst, loadCore, V1, type FetchFn } from "../src/dataroot.ts";
import { forestLossFire, FOREST_LOSS_FIRE_LEGEND } from "../src/labels.ts";

const ok = (j: unknown) => ({ ok: true, status: 200, json: async () => j });
const bad = (s = 404) => ({ ok: false, status: s, json: async () => { throw new Error("no body"); } });
const site = (files: Record<string, unknown>): { f: FetchFn; calls: string[] } => {
  const calls: string[] = [];
  return { calls, f: async (u) => { const k = u.split("?")[0]; calls.push(u); if (k in files) return files[k] === "boom" ? Promise.reject(new TypeError("network")) : ok(files[k]); return bad(); } };
};
const V2 = { version: "v3", base: "data-v4/", fallback: "data-prev/" };

test("cleanBase: relative folder, trailing slash, rejects anything unsafe", () => {
  assert.equal(cleanBase("data-v4"), "data-v4/");
  assert.equal(cleanBase("data-v4/"), "data-v4/");
  for (const b of ["/etc/", "https://x.org/data-prev/", "../data-prev/", "a/../b/", "a\\b", "", "  ", 5, null, undefined]) assert.equal(cleanBase(b), "data-v4/", String(b));
  assert.equal(cleanBase("..x/"), "..x/"); // only a ".." path segment is refused
});
test("parsePointer: v1 default, v2 needs no code, junk -> v1", () => {
  assert.deepEqual(parsePointer({ version: "v3", base: "data-v4/", fallback: "data-v4/" }), V1);
  assert.deepEqual(parsePointer({ version: "v4", base: "data-v4/" }), { version: "v4", base: "data-v4/", fallback: "data-v4/" });
  assert.deepEqual(parsePointer({ version: "v3", base: "data-v4", fallback: "data-v1" }), { version: "v3", base: "data-v4/", fallback: "data-v1/" });
  assert.deepEqual(parsePointer({ version: "v3", base: "../evil/" }), { version: "v3", base: "data-v4/", fallback: "data-v4/" });
  for (const j of [null, "x", 3, [], undefined]) assert.deepEqual(parsePointer(j), V1);
});
test("dataUrl builds from site base + data base", () => {
  assert.equal(dataUrl("/", "data-prev/", "manifest.json"), "/data-prev/manifest.json");
  assert.equal(dataUrl("/abang_on_earth/", "data-v4/", "fire/viirs/2020-01.pmtiles"), "/abang_on_earth/data-v4/fire/viirs/2020-01.pmtiles");
  assert.equal(dataUrl("/", "data-prev/", "/layers.json"), "/data-prev/layers.json");
});
test("loadPointer: reads data-version.json; missing, network error or bad JSON -> v1", async () => {
  assert.equal((await loadPointer("/", site({ "/data-version.json": { version: "v3", base: "data-v4/" } }).f)).base, "data-v4/");
  assert.deepEqual(await loadPointer("/", site({}).f), V1);
  assert.deepEqual(await loadPointer("/", site({ "/data-version.json": "boom" }).f), V1);
  assert.deepEqual(await loadPointer("/", async () => ({ ok: true, status: 200, json: async () => { throw new SyntaxError("x"); } })), V1);
});
test("loadPointer asks for no-cache (a switch shows up without a hard refresh)", async () => {
  let init: unknown; await loadPointer("/", async (_u, i) => { init = i; return bad(); });
  assert.deepEqual(init, { cache: "no-cache" });
});
test("loadFirst: uses the pointer's base when it answers", async () => {
  const s = site({ "/data-v4/manifest.json": { n: 2 }, "/data-prev/manifest.json": { n: 1 } });
  const r = await loadFirst<{ n: number }>("/", V2, "manifest.json", s.f);
  assert.equal(r.data.n, 2); assert.deepEqual(r.root, { version: "v3", base: "data-v4/", fellBack: false });
  assert.deepEqual(s.calls, ["/data-v4/manifest.json"]);
});
test("loadFirst: new base fails (404 or network error) -> falls back to data-prev/", async () => {
  for (const v2 of [undefined, "boom"]) {
    const s = site({ ...(v2 ? { "/data-v4/manifest.json": v2 } : {}), "/abang_on_earth/data-prev/manifest.json": { n: 1 } });
    const r = await loadFirst<{ n: number }>("/abang_on_earth/", V2, "manifest.json", s.f);
    assert.equal(r.data.n, 1); assert.equal(r.root.fellBack, true); assert.equal(r.root.base, "data-prev/");
    assert.deepEqual(s.calls, ["/abang_on_earth/data-v4/manifest.json", "/abang_on_earth/data-prev/manifest.json"]);
  }
});
test("loadFirst: both fail -> throws (the app shows its normal load error)", async () => {
  await assert.rejects(loadFirst("/", V2, "manifest.json", site({}).f), /HTTP 404/);
});
test("loadFirst: base == fallback is tried once", async () => {
  const s = site({}); await assert.rejects(loadFirst("/", V1, "manifest.json", s.f)); assert.equal(s.calls.length, 1);
});
test("forest-loss fire labels: clearing layers renamed, legend replaced, other layers untouched", () => {
  const c = forestLossFire({ label: "MODIS clearing fires", legend: "old", clearing: true, id: "clrm" });
  assert.equal(c.label, "MODIS forest-loss fires"); assert.equal(c.legend, FOREST_LOSS_FIRE_LEGEND); assert.equal(c.id, "clrm");
  assert.match(c.legend, /not proof of land clearing/);
  const p = { label: "MODIS fires", legend: "x" }; assert.equal(forestLossFire(p), p);
});

test("loadPointer: every call has its own URL (cache-busting query) and still no-cache", async () => {
  const urls: string[] = []; let t = 1000;
  for (let i = 0; i < 2; i++) await loadPointer("/", async (u) => { urls.push(u); return bad(); }, () => (t += 60000));
  assert.match(urls[0], /^\/data-version\.json\?_=\d+$/); assert.notEqual(urls[0], urls[1]);
});

// ---- the data root loads as one unit ----
const core = (n: number, over: Record<string, unknown> = {}, dir = "data-prev/") => ({
  [`/${dir}manifest.json`]: { n, files: { regions: "regions.geojson", monthly: "monthly.json" } },
  [`/${dir}regions.geojson`]: { type: "FeatureCollection", features: [{ properties: { id: "riau", name: "Riau" } }] },
  [`/${dir}monthly.json`]: { months: ["2020-01"], series: { riau: {} } },
  [`/${dir}layers.json`]: { schema_version: 1, layers: [{ id: "loss", legend: "Loss \u2014 x", path: "forest-loss/{year}.pmtiles" }] },
  ...over,
});
const base = (o: Record<string, unknown> = {}) => ({ ...core(1), ...core(2, {}, "data-v4/"), ...o });
type Any = Record<string, any>;
test("loadCore: good v2 folder -> all four files from v2, no fallback", async () => {
  const s = site(base()); const r = await loadCore<Any, Any, Any, Any>("/", V2, s.f);
  assert.equal(r.data.manifest.n, 2); assert.deepEqual(r.root, { version: "v3", base: "data-v4/", fellBack: false });
  assert.ok(s.calls.every((u) => u.startsWith("/data-v4/")));
});
test("loadCore: any ONE of the four files missing / network error / malformed in v2 -> all four come from v1 (never mixed)", async () => {
  const bads: [string, unknown][] = [];
  for (const f of ["manifest.json", "regions.geojson", "monthly.json", "layers.json"]) for (const v of [undefined, "boom", {}, [], "x", null, { layers: "no" }, { type: "FeatureCollection" }, { months: [], series: {} }]) bads.push([f, v]);
  for (const [f, v] of bads) {
    const files: Record<string, unknown> = base(); if (v === undefined) delete files[`/data-v4/${f}`]; else files[`/data-v4/${f}`] = v;
    if (f === "manifest.json" && typeof v === "object" && v && !Array.isArray(v) && "months" in v) continue; // not a manifest-shaped case
    const s = site(files); const r = await loadCore<Any, Any, Any, Any>("/", V2, s.f);
    const where = `${f} = ${JSON.stringify(v)}`;
    assert.equal(r.root.fellBack, true, where); assert.equal(r.root.base, "data-prev/", where); assert.equal(r.data.manifest.n, 1, where);
    assert.ok(s.calls.filter((u) => u.startsWith("/data-prev/")).length === 4, where);
  }
});
test("loadCore: layers.json items without id/legend/path are malformed (rows would throw)", async () => {
  const s = site(base({ "/data-v4/layers.json": { layers: [{ id: "loss" }] } })); const r = await loadCore<Any, Any, Any, Any>("/", V2, s.f); assert.equal(r.root.fellBack, true);
});
test("loadCore: manifest files.regions points at a name -> that name is fetched; fire_layers must be well formed", async () => {
  const s = site(base({ "/data-v4/manifest.json": { files: { regions: "r2.geojson", monthly: "monthly.json" } }, "/data-v4/r2.geojson": core(0)["/data-prev/regions.geojson"] }));
  assert.equal((await loadCore<Any, Any, Any, Any>("/", V2, s.f)).root.base, "data-v4/");
  const t = site(base({ "/data-v4/manifest.json": { files: { regions: "regions.geojson", monthly: "monthly.json" }, fire_layers: { layers: "x" } } }));
  assert.equal((await loadCore<Any, Any, Any, Any>("/", V2, t.f)).root.base, "data-prev/");
});
test("loadCore: both folders broken -> throws with both reasons; pointer == fallback is tried once", async () => {
  await assert.rejects(loadCore("/", V2, site({}).f), /data-v4\/manifest\.json: HTTP 404; data-prev\/manifest\.json: HTTP 404/);
  const s = site({}); await assert.rejects(loadCore("/", V1, s.f)); assert.equal(s.calls.length, 1);
});

import { withTimeout } from "../src/dataroot.ts";
test("withTimeout: a request that never answers rejects after the deadline; a quick one passes; a stalled body rejects too", async () => {
  const hang = ((_u: string, init?: { signal?: AbortSignal }) => new Promise((_res, rej) => init?.signal?.addEventListener("abort", () => rej(new Error("aborted"))))) as never;
  await assert.rejects(withTimeout(hang, 30)("/data-v4/manifest.json?x=1"), /data-v4\/manifest\.json: no answer after 0 s/);
  const ok = withTimeout((async () => ({ ok: true, status: 200, json: async () => ({ a: 1 }) })) as never, 30);
  assert.deepEqual(await (await ok("/x")).json(), { a: 1 });
  const stalledBody = withTimeout(((_u: string, init?: { signal?: AbortSignal }) => Promise.resolve({ ok: true, status: 200, json: () => new Promise((_r, rej) => init?.signal?.addEventListener("abort", () => rej(new Error("body aborted")))) })) as never, 30);
  await assert.rejects(async () => (await stalledBody("/y")).json(), /no answer/);
});

// ---- the app can start the map from the manifest alone  ----
test("loadCore: onManifest is called with the manifest of the folder that is being tried, before regions/monthly/layers are asked for", async () => {
  const s = site(base()); const seen: [number, string, number][] = [];
  await loadCore<Any, Any, Any, Any>("/", V2, s.f, (m, b) => seen.push([m.n, b, s.calls.length]));
  assert.deepEqual(seen, [[2, "data-v4/", 1]]); // one call, manifest n=2 from data-v4/, only the manifest had been requested so far
});
test("loadCore: when the first folder fails after its manifest, onManifest is called again for the fallback folder", async () => {
  const files: Record<string, unknown> = base(); delete files["/data-v4/layers.json"];
  const s = site(files); const seen: string[] = [];
  const r = await loadCore<Any, Any, Any, Any>("/", V2, s.f, (_m, b) => seen.push(b));
  assert.deepEqual(seen, ["data-v4/", "data-prev/"]); assert.equal(r.root.fellBack, true);
});
