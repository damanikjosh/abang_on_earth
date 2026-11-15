import * as maplibregl from "maplibre-gl";
import { Protocol } from "pmtiles";
import type { Covered } from "./coverage";
import type { Described } from "./layerinfo";

export interface LayerDef extends Covered, Described {
  id: string; label: string; mode: "cumulative" | "cumfile" | "year" | "month" | "static" | "class" | "vector" | "variant"; path: string; /** panel row name; default = legend text before " \u2014 " */ title?: string;
  min?: number | string; max?: number | string; legend: string; color: string; fade?: boolean; placeholder?: boolean; minzoom?: number;
  /** keys of files that exist ("2019", "2025-10", "s"); written by scripts/index_layers.py. Absent = probe each file. */
  available?: string[];
  /** mode "class": several static files ({class} in path) shown together; each can be switched off. available lists "c1".."cN" */
  classes?: { id: number; label: string; color: string }[];
  /** mode "variant": one file shown at a time, chosen with a picker; {variant} in path. available lists the variant ids. */
  variants?: { id: string; label: string; text: string; legend: { color: string; label: string }[] }[]; default_variant?: string;
}
export interface LayersFile { schema_version: number; version?: string; placeholder?: boolean; layers: LayerDef[] }

// bottom -> top, all under the fire regions: peat, plantation, pulpwood, palm, TMF degradation, TMF deforestation, loss, burned area, alerts
const Z_ORDER = ["peat", "plantation", "pulp", "palm", "mb_palm", "mb_pulp", "mb_mine", "loss_palm", "tmfdeg", "tmfdef", "loss", "drivers", "burned", "mines", "alerts"];
const OPACITY: Record<string, number> = { drivers: 0.8, mines: 0.75, loss: 0.9, alerts: 0.95, palm: 0.7, pulp: 0.55, mb_palm: 0.85, mb_pulp: 0.85, mb_mine: 0.85, burned: 0.85, loss_palm: 0.85, tmfdef: 0.85, tmfdeg: 0.8, plantation: 0.8, peat: 0.6 };

let protocol: Protocol | null = null;
/** Registers the pmtiles:// protocol (once). Called at app start, before layers.json is read, so fire layers work whatever happens to layers.json. */
export function ensureProtocol() { if (!protocol) { protocol = new Protocol(); maplibregl.addProtocol("pmtiles", protocol.tile); } }
const probes = new Map<string, Promise<boolean>>();
/** A real PMTiles file starts with the ASCII bytes "PMTiles". Dev/preview servers answer a missing path with
 *  index.html and status 200, so the status code alone is not enough. */
function exists(url: string): Promise<boolean> {
  let p = probes.get(url);
  if (!p) {
    p = fetch(url, { headers: { Range: "bytes=0-6" } })
      .then(async (r) => r.ok && new TextDecoder().decode((await r.arrayBuffer()).slice(0, 7)) === "PMTiles")
      .catch(() => false);
    probes.set(url, p);
  }
  return p;
}

export class ContextLayers {
  readonly enabled = new Set<string>();
  private month = "";
  private token = 0;
  private added = new Set<string>();
  private classOff = new Set<string>(); // "row:classId" switched off
  private failed = new Set<string>(); // map source ids (ctx-<layer>-<key>) whose file could not be read
  private variant = new Map<string, string>(); // chosen variant per "variant"-mode layer (absent = default_variant)
  private scale = new Map<string, number>(); // user opacity multiplier per layer (full-screen UI slider)
  /** draw order of panel rows, top of list = drawn on top (see setOrder) */
  private order: string[] = [];
  private groups = new Map<string, (layerId: string) => boolean>();
  onStatus: (id: string, text: string) => void = () => {};
  onChange: () => void = () => {};

  /** `base` = URL prefix of the data folder, ending in "/" (site base + pointer base, e.g. "/data-v2/") */
  constructor(private map: maplibregl.Map, readonly defs: LayerDef[], private base: string, private version = "") {
    ensureProtocol();
    map.on("zoomend", () => void this.sync()); // refresh the "zoom in" note
    map.on("error", (e) => { const id = (e as { sourceId?: string }).sourceId; if (id?.startsWith("ctx-") && !this.failed.has(id)) { this.failed.add(id); void this.sync(); } }); // tile file 404 / unreadable: this layer only
  }
  get anyOn() { return this.enabled.size > 0; }
  toggle(id: string, on: boolean) { on ? this.enabled.add(id) : this.enabled.delete(id); this.onChange(); void this.sync(); }
  setOpacity(id: string, k: number) { this.scale.set(id, k); void this.sync(); }
  getVariant(id: string): string { const d = this.defs.find((x) => x.id === id); return this.variant.get(id) ?? d?.default_variant ?? d?.variants?.[0]?.id ?? ""; }
  setVariant(id: string, v: string) { const d = this.defs.find((x) => x.id === id); if (!d?.variants?.some((x) => x.id === v)) return; this.variant.set(id, v); void this.sync(); }
  setClass(id: string, cls: number, on: boolean) { on ? this.classOff.delete(`${id}:${cls}`) : this.classOff.add(`${id}:${cls}`); void this.sync(); }
  setMonth(m: string) { this.month = m; void this.sync(); }
  /** call after map.setStyle: sources and layers are gone */
  reset() { this.added.clear(); void this.sync(); }

  /** ?v=<layers.json version> makes replaced tile files (same name, new content) bypass the browser's cached ranges */
  private fileUrl(path: string) { const u = new URL(this.base + path, location.href); if (this.version) u.searchParams.set("v", this.version); return u.href; }
  /** Rows that own map layers besides the layers.json ones (e.g. "regions"): match() says which style layer ids belong to the row. */
  registerGroup(rowId: string, match: (layerId: string) => boolean) { this.groups.set(rowId, match); }
  /** Default list, top first: rows not known to Z_ORDER (fire layers) on top, then `extra` rows (regions), then context layers top->bottom. */
  defaultOrder(extra: string[] = []): string[] {
    const ctx = this.defs.map((d) => d.id), known = [...Z_ORDER].reverse().filter((i) => ctx.includes(i));
    return [...ctx.filter((i) => !Z_ORDER.includes(i)), ...extra, ...known];
  }
  /** order = row ids, top of list first. Each row's map layers stay together and in their own order, below the basemap labels. */
  setOrder(ids: string[]) { this.order = ids; this.applyOrder(); }
  private rowOf(layerId: string): string | undefined {
    for (const [id, m] of this.groups) if (m(layerId)) return id;
    for (const d of this.defs) if (layerId.startsWith(`ctx-${d.id}-`)) return d.id;
  }
  applyOrder() {
    if (!this.order.length || !this.map.getStyle()) return;
    const layers = this.map.getStyle().layers, byRow = new Map<string, string[]>();
    let anchor: string | undefined;
    for (const l of layers) {
      const r = this.rowOf(l.id);
      if (r) byRow.set(r, [...(byRow.get(r) ?? []), l.id]);
      else if (!anchor && l.type === "symbol") anchor = l.id; // first basemap label layer: everything of ours goes below it
    }
    const want = [...this.order].reverse().flatMap((r) => byRow.get(r) ?? []);
    for (const [r, ids] of byRow) if (!this.order.includes(r)) want.push(...ids); // unknown rows stay on top
    const ours = layers.map((l) => l.id).filter((id) => this.rowOf(id));
    const ai = anchor ? layers.findIndex((l) => l.id === anchor) : layers.length;
    const lastOurs = layers.map((l) => l.id).lastIndexOf(ours[ours.length - 1]);
    if (ours.length && ours.join() === want.join() && lastOurs < ai) return; // already right
    for (const id of want) this.map.moveLayer(id, anchor);
  }

  private wanted(d: LayerDef): { key: string; path: string }[] {
    const y = Number(this.month.slice(0, 4));
    if (d.mode === "static" || d.mode === "vector") return [{ key: "s", path: d.path }];
    if (d.mode === "variant") { const v = this.getVariant(d.id); return [{ key: v, path: d.path.replace("{variant}", v) }]; }
    if (d.mode === "class") return (d.classes ?? []).filter((c) => !this.classOff.has(`${d.id}:${c.id}`)).map((c) => ({ key: `c${c.id}`, path: d.path.replace("{class}", String(c.id)) }));
    if (d.mode === "month") {
      if (d.min != null && this.month < String(d.min)) return [];
      if (d.max != null && this.month > String(d.max)) return [];
      return [{ key: this.month, path: d.path.replace("{month}", this.month) }];
    }
    if (d.mode === "year") { // only the selected year's file (events of that year, e.g. burned area)
      if ((d.min != null && y < Number(d.min)) || (d.max != null && y > Number(d.max))) return [];
      return [{ key: String(y), path: d.path.replace("{year}", String(y)) }];
    }
    if (d.mode === "cumfile") { // one density file per selected year; the file already holds everything up to that year
      const lo = Number(d.min ?? 0), hi = Number(d.max ?? y);
      if (y < lo) return [];
      let k = Math.min(y, hi);
      if (d.available) { // irregular year list (e.g. every 5 years): nearest available year at or before the selected one
        const ys = d.available.map(Number).filter((v) => v <= k);
        if (!ys.length) return [];
        k = Math.max(...ys);
      }
      return [{ key: String(k), path: d.path.replace("{year}", String(k)) }];
    }
    const lo = Number(d.min ?? 0), hi = Math.min(Number(d.max ?? y), y);
    const out = [];
    for (let k = lo; k <= hi; k++) out.push({ key: String(k), path: d.path.replace("{year}", String(k)) });
    return out;
  }
  private beforeId(id: string): string | undefined {
    const mine = Z_ORDER.indexOf(id);
    for (const l of this.map.getStyle().layers) {
      if (l.id.startsWith("ctx-") && Z_ORDER.indexOf(l.id.split("-")[1]) > mine) return l.id;
    }
    return this.map.getLayer("regions") ? "regions" : undefined;
  }

  async sync() {
    const tok = ++this.token;
    if (!this.month || !this.map.getLayer("regions")) return; // style (re)loading: reset() runs after it
    for (const d of this.defs) {
      const want = this.wanted(d);
      const ok = !this.enabled.has(d.id) ? [] : d.available
        ? want.map((w) => d.available!.includes(w.key)) // listed: no request for files that are not there
        : await Promise.all(want.map((w) => exists(this.fileUrl(w.path))));
      if (tok !== this.token) return; // a newer sync superseded this one
      const shown = new Set<string>();
      want.forEach((w, i) => {
        if (!ok[i]) return;
        shown.add(w.key);
        const lid = `ctx-${d.id}-${w.key}`;
        if (!this.added.has(lid) || !this.map.getLayer(lid)) {
          if (this.map.getSource(lid)) { for (const l of [lid + "-line", lid]) if (this.map.getLayer(l)) this.map.removeLayer(l); this.map.removeSource(lid); }
          if (d.mode === "vector") { // GeoJSON outlines: a translucent fill and a thin line, both removed with the source
            this.map.addSource(lid, { type: "geojson", data: this.fileUrl(w.path) });
            this.map.addLayer({ id: lid, type: "fill", source: lid, minzoom: d.minzoom ?? 0, paint: { "fill-color": d.color, "fill-opacity": 0 } }, this.beforeId(d.id));
            this.map.addLayer({ id: lid + "-line", type: "line", source: lid, minzoom: d.minzoom ?? 0, paint: { "line-color": d.color, "line-width": ["interpolate", ["linear"], ["zoom"], 3, 0.6, 10, 1.2], "line-opacity": 0 } }, this.beforeId(d.id));
            this.added.add(lid); this.added.add(lid + "-line");
          } else {
            this.map.addSource(lid, { type: "raster", url: "pmtiles://" + this.fileUrl(w.path), tileSize: 256 });
            this.map.addLayer({ id: lid, type: "raster", source: lid, minzoom: d.minzoom ?? 0, paint: { "raster-resampling": "nearest", "raster-opacity": 0, "raster-fade-duration": 0 } }, this.beforeId(d.id));
            this.added.add(lid);
          }
        }
      });
      const y = Number(this.month.slice(0, 4)), lo = Number(d.min ?? 0);
      for (const lid of this.added) {
        if (!lid.startsWith(`ctx-${d.id}-`) || !this.map.getLayer(lid)) continue;
        const key = lid.slice(`ctx-${d.id}-`.length).replace(/-line$/, "");
        let op = shown.has(key) ? OPACITY[d.id] ?? 0.8 : 0;
        if (d.mode === "cumfile") op = shown.has(key) ? OPACITY[d.id] ?? 0.9 : 0;
        if (op && d.fade) { const age = (y - Number(key)) / Math.max(1, y - lo); op = 0.95 - 0.7 * Math.min(1, Math.max(0, age)); } // recent = strong
        const prop = d.mode === "vector" ? (lid.endsWith("-line") ? "line-opacity" : "fill-opacity") : "raster-opacity";
        this.map.setPaintProperty(lid, prop, op * (this.scale.get(d.id) ?? 1) * (prop === "fill-opacity" ? 0.55 : 1)); // outlines stay strong, the fill is lighter
      }
      if (d.mode === "cumfile" || d.mode === "year" || d.mode === "variant") { // drop other years' sources once the new one has drawn: one source per layer
        const stale = [...this.added].filter((lid) => lid.startsWith(`ctx-${d.id}-`) && !shown.has(lid.slice(`ctx-${d.id}-`.length)));
        if (stale.length) this.map.once("idle", () => stale.forEach((lid) => {
          if (this.map.getLayer(lid)) this.map.removeLayer(lid);
          if (this.map.getSource(lid)) this.map.removeSource(lid);
          this.added.delete(lid);
        }));
      }
      this.onStatus(d.id, this.status(d, want.length, ok.filter(Boolean).length));
    }
    this.applyOrder();
  }

  private enabledKey(d: LayerDef, key: string) { return !d.available || d.available.includes(key); }
  private status(d: LayerDef, wanted: number, found: number): string {
    if (!this.enabled.has(d.id)) return "";
    if (found > 0 && this.wanted(d).every((w) => !this.enabledKey(d, w.key) || this.failed.has(`ctx-${d.id}-${w.key}`))) return "Data not available (map file missing)";
    if (d.minzoom && this.map.getZoom() < d.minzoom) { const n = Math.max(1, Math.ceil(d.minzoom - this.map.getZoom())); return `Zoom in ${n} more step${n > 1 ? "s" : ""} (to zoom ${d.minzoom}) to see ${d.label.toLowerCase()} \u2014 country-scale view is being rebuilt`; }
    if (d.mode === "class") { // count files that really loaded, not boxes that are ticked
      const miss = this.wanted(d).filter((w) => this.failed.has(`ctx-${d.id}-${w.key}`)).length, ok = found - miss;
      return found === 0 ? "No class selected" : ok === 0 ? "Data not available (map files missing)" : `Shown (${ok} of ${d.classes?.length ?? found} classes${miss ? `; ${miss} map file${miss > 1 ? "s" : ""} missing` : ""})`;
    }
    if (found === 0) return "Not available for this month";
    if (d.mode === "year") return `Showing ${this.month.slice(0, 4)} only (share of area burned that year)`;
    if (d.mode === "cumfile") {
      const k = this.wanted(d)[0]?.key ?? "";
      const sel = this.month.slice(0, 4);
      return d.available && k !== sel ? `Showing ${k}: nearest available year at or before ${sel} (this layer has no file for ${sel})` : `Showing share of area, up to ${k}`;
    }
    if (d.mode === "cumulative" && found < wanted) return `${found} of ${wanted} yearly files available so far`;
    return d.mode === "static" || d.mode === "vector" || d.mode === "variant" ? "Shown" : d.mode === "month" ? `Showing ${this.month}` : `Showing up to ${this.month.slice(0, 4)}`;
  }
}
