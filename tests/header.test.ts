// The tile source maxzoom must come from the PMTiles header (v1 points z9-11, v2 z9 only): pmtiles' TileJSON carries header.maxZoom, MapLibre overzooms past it.
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { PMTiles, type Source, type RangeResponse } from "pmtiles";

const fileSource = (p: string): Source => ({ getKey: () => p, getBytes: async (off: number, len: number): Promise<RangeResponse> => { const b = readFileSync(p).subarray(off, off + len); return { data: b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength) as ArrayBuffer }; } });
for (const [dir, label] of [["public/data-v4/fire/viirs", "fire"], ["public/data-v4/forest-loss", "raster"]] as const) {
  test(`${label}: TileJSON maxzoom == header maxZoom (${dir})`, async () => {
    const f = readdirSync(dir).filter((n) => n.endsWith(".pmtiles")).sort()[0];
    const pm = new PMTiles(fileSource(`${dir}/${f}`)), h = await pm.getHeader(), tj = (await pm.getTileJson("http://x/{z}/{x}/{y}")) as { maxzoom: number };
    assert.equal(tj.maxzoom, h.maxZoom); assert.ok(h.maxZoom >= 8);
  });
}
