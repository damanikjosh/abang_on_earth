import * as maplibregl from "maplibre-gl";

/** A fire-detection map layer from manifest.json "fire_layers". Real layers read one PMTiles (MVT) file per month:
 *  layer "dens" (z0-8, density cells, bin b 0..31 on a fixed sqrt scale) and layer "pts" (z9+, the detections, s = footprint in 0.1 km). */
import type { Covered } from "./coverage";
import type { Described } from "./layerinfo";
import { splitMonth, splitMonths, tiledClasses, ownClasses, classEditable, densValue, densFilter, isMerged, type FireClass } from "./fireclasses";
export { splitMonth, splitMonths, type FireClass };
export interface FireDef extends Covered, Described {
  id: string; label: string; sensor: string; /** file template of the layer itself; absent when the layer is drawn from its class files only (MODIS and VIIRS day / night) */ path?: string; min: string; max: string; color: string[]; legend: string;
  placeholder?: boolean; clearing?: boolean; available?: string[]; note?: string; pointsFrom?: number;
  /** Optional sub-selection. A month in which EVERY class has tiles (`available`) is drawn from the class files, one source per ticked class; any other month is drawn from `path` exactly as before. */
  classes?: FireClass[];
}
/** One drawable source family: the layer itself (`cls` undefined) or one of its classes. `group` = id of the layer row it belongs to. */
interface Unit extends FireDef { group: string; cls?: number }
export interface FireFile { dmax_per_100km2: number; ptsMinZoom: number; layers: FireDef[] }

const Z_PTS_DEFAULT = 9;
const MAX_STALE = 6; // leftover month sources tolerated while the user is scrubbing
export class FireLayers {
  readonly enabled = new Set<string>();
  private month = "";
  private scale = new Map<string, number>();
  private shown = new Map<string, string>(); // def id -> month currently drawn
  private pending = new Map<string, string>(); // def id -> month being loaded
  private classOff = new Map<string, Set<number>>(); // layer id -> class numbers switched off (all on by default)
  private readonly units: Unit[]; // the layers, each followed by its classes as units of their own (ids "<layer>_<class>")
  private failed = new Set<string>(); // source ids (fire-<layer>-<month>) whose file could not be read
  onStatus: (id: string, text: string) => void = () => {};
  onChange: () => void = () => {};
  onAdded: () => void = () => {}; // after layers were added (the app re-applies the user's layer order)
  version = ""; // layers.json version: cache-busts replaced tile files
  /** `base` = URL prefix of the data folder ending in "/"; `zPts` = first zoom that shows single detections (manifest ptsMinZoom).
   *  Tile source maxzoom is not set here: MapLibre takes it from each PMTiles header, so v1 (points z9-11) and v2 (points z9 only, overzoomed) both work. */
  private readonly Z_PTS: number;
  constructor(private map: maplibregl.Map, readonly defs: FireDef[], private base: string, zPts = Z_PTS_DEFAULT) {
    this.Z_PTS = zPts;
    this.units = defs.flatMap((d): Unit[] => [...(d.path ? [{ ...d, group: d.id }] : []), ...tiledClasses(d).map((c): Unit => ({ ...d, id: `${d.id}_${c.id}`, path: c.path!, available: c.available, classes: undefined, group: d.id, cls: c.id }))]);
    map.on("sourcedata", () => this.promote());
    map.on("error", (e) => { // a month file that cannot be read: hide this layer for that month, say so in its row; other layers and months are unaffected
      const id = (e as { sourceId?: string }).sourceId; if (!id?.startsWith("fire-") || this.failed.has(id)) return;
      this.failed.add(id);
      for (const d of this.units) if (id === this.lid(d, this.month)) { this.vis(d, false); this.shown.delete(d.id); }
      this.status();
    });
    map.on("zoomend", () => this.status());
    map.on("idle", () => this.sweep(0)); // nothing is loading now: drop every month nobody needs
  }
  get anyOn() { return this.defs.some((d) => !d.placeholder && this.enabled.has(d.id)); }
  toggle(id: string, on: boolean) { on ? this.enabled.add(id) : this.enabled.delete(id); this.onChange(); this.sync(); }
  setOpacity(id: string, k: number) { this.scale.set(id, k); for (const d of this.units) if (d.group === id) this.opacity(d); }
  /** Classes switched off by the user, per layer id: the share link `x=` is written from this (not from the boxes, which are greyed in months without class tiles). */
  offClasses(): Record<string, number[]> { const o: Record<string, number[]> = {}; for (const [id, s] of this.classOff) { const d = this.defs.find((x) => x.id === id); const a = [...s].filter((c) => d && classEditable(d, c)); if (a.length) o[id] = a; } return o; }
  /** A disabled class is never on, whatever a link or a caller says. */
  classOn(id: string, cls: number) { const d = this.defs.find((x) => x.id === id); return !!d && classEditable(d, cls) && !this.classOff.get(id)?.has(cls); }
  /** Ticks or unticks one class (day / night ...) of a layer; takes effect at once, no tile is loaded again. */
  setClass(id: string, cls: number, on: boolean) { const d = this.defs.find((x) => x.id === id); if (!d || !classEditable(d, cls)) return; const s = this.classOff.get(id) ?? new Set<number>(); on ? s.delete(cls) : s.add(cls); this.classOff.set(id, s); this.sync(); }
  /** Is this unit drawn now? A layer with classes is drawn from its own file, or, in a month where every class has tiles, from the ticked classes' files. */
  private unitOn(u: Unit, m: string) {
    if (!this.enabled.has(u.group)) return false;
    const parent = this.defs.find((d) => d.id === u.group)!, split = splitMonth(parent, m);
    return u.cls === undefined ? !split && ownClasses(parent).every((c) => this.classOn(u.group, c.id)) : split && this.classOn(u.group, u.cls);
  }
  setMonth(m: string) { this.month = m; this.sync(); }
  reset() { this.shown.clear(); this.pending.clear(); this.sync(); } // after map.setStyle everything is gone
  private url(d: FireDef, m: string) { const u = new URL(this.base + d.path!.replace("{month}", m), location.href); if (this.version) u.searchParams.set("v", this.version); return "pmtiles://" + u.href; }
  private lid(d: FireDef, m: string) { return `fire-${d.id}-${m}`; }
  private anchor() { return this.map.getLayer("regions-sel") ? "regions-sel" : undefined; }
  private have(d: FireDef, m: string) { return !d.placeholder && (!d.available || d.available.includes(m)); }

  sync() {
    if (!this.month || !this.map.getLayer("regions")) return;
    for (const d of this.units) {
      if (d.placeholder) continue;
      const m = this.month, on = this.unitOn(d, m);
      if (!on || !this.have(d, m)) { this.vis(d, false); this.pending.delete(d.id); if (on) this.shown.delete(d.id); continue; } // hidden, not removed: removing a source mid-load aborts its tile requests
      if (this.shown.get(d.id) === m) { this.vis(d, true); this.opacity(d); continue; }
      if (this.pending.get(d.id) !== m) {
        this.pending.set(d.id, m);
        const id = this.lid(d, m);
        if (!this.map.getSource(id)) this.map.addSource(id, { type: "vector", url: this.url(d, m) });
        const [c0, c1, c2, c3] = d.color;
        if (!this.map.getLayer(id + "-dens")) this.map.addLayer({ id: id + "-dens", type: "fill", source: id, "source-layer": d.clearing ? "cdens" : "dens", maxzoom: this.Z_PTS,
          paint: { "fill-antialias": false, "fill-color": ["interpolate", ["linear"], ["get", "b"], 0, c0, 10, c1, 20, c2, 31, c3], "fill-opacity": 0 } }, this.anchor());
        this.restyle(d);
        if (!this.map.getLayer(id + "-pts")) this.map.addLayer({ id: id + "-pts", type: "circle", source: id, "source-layer": "pts", minzoom: this.Z_PTS, ...(d.clearing ? { filter: ["==", ["get", "c"], 1] } : {}),
          paint: { "circle-color": c2, "circle-stroke-color": c3, "circle-stroke-width": 1, "circle-opacity": 0, "circle-stroke-opacity": 0,
            "circle-radius": ["interpolate", ["exponential", 2], ["zoom"], this.Z_PTS, ["max", 1.6, ["*", ["get", "s"], 0.327]], 22, ["*", ["get", "s"], 2678]] } }, this.anchor());
        this.onAdded();
      }
    }
    for (const d of this.units) if (d.cls !== undefined) this.restyle(d);
    this.sweep(MAX_STALE); // scrubbing: a new month replaces `pending`, so superseded months never reach promote(); cap them here
    this.status(); this.promote();
  }
  /** once the new month's tiles are in, show it and drop the previous one (no blank flash while playing) */
  private promote() {
    for (const [id, m] of [...this.pending]) {
      const d = this.units.find((x) => x.id === id)!, lid = this.lid(d, m);
      if (m !== this.month) { this.pending.delete(id); this.sweep(MAX_STALE); continue; } // superseded: leave it for now (invisible, opacity 0); sweep() removes it at idle, or at once when too many pile up
      if (!this.map.getSource(lid) || !this.map.isSourceLoaded(lid)) continue;
      this.pending.delete(id); this.shown.set(id, m); this.clear(d, m); this.vis(d, true); this.opacity(d); this.status();
    }
  }
  /** Remove months nobody needs: every fire-<layer>-<month> source/layer other than the shown, pending and current month of its layer. `allow` = how many such leftovers may stay.
   *  Scrubbing the timeline used to leave one source + 2 style layers per visited month (299 sources after 2 minutes) because only promote() cleaned up, and only for loaded sources.
   *  Called with 0 on map "idle" (every load has finished, so no tile request is aborted) and with MAX_STALE while scrubbing (oldest-visited first is not tracked: any leftovers go once over the limit). */
  private sweep(allow: number) {
    const st = this.map.getStyle(); if (!st) return;
    const needed = new Set<string>([...this.shown, ...this.pending].map(([id, m]) => `fire-${id}-${m}`));
    for (const d of this.units) needed.add(this.lid(d, this.month));
    const stale = Object.keys(st.sources).filter((s) => /^fire-[a-z0-9_]+-\d{4}-\d{2}$/i.test(s) && !needed.has(s));
    if (stale.length <= allow) return;
    for (const s of stale) {
      for (const l of st.layers) if ("source" in l && l.source === s && this.map.getLayer(l.id)) this.map.removeLayer(l.id);
      if (this.map.getSource(s)) this.map.removeSource(s);
    }
  }
  /** remove every month of this layer except `keep` (and `keep2`) */
  private clear(d: FireDef, keep: string | null, keep2?: string) {
    const st = this.map.getStyle(); if (!st) return;
    for (const l of st.layers) if (l.id.startsWith(`fire-${d.id}-`)) {
      const m = l.id.slice(`fire-${d.id}-`.length, `fire-${d.id}-`.length + 7);
      if (m !== keep && m !== keep2 && "source" in l && this.map.isSourceLoaded(l.source as string)) this.map.removeLayer(l.id); // never drop a source that is still loading: it logs aborted-fetch errors
    }
    for (const s of Object.keys(st.sources)) if (s.startsWith(`fire-${d.id}-`)) {
      const m = s.slice(`fire-${d.id}-`.length);
      if (m !== keep && m !== keep2 && this.map.isSourceLoaded(s) && !this.map.getStyle().layers.some((l) => "source" in l && l.source === s)) this.map.removeSource(s);
    }
  }
  /** Density cells of a class unit: combined colour when every class is ticked (see src/fireclasses.ts), the class's own colour otherwise; also the filter that draws every cell once. */
  private restyle(u: Unit) {
    if (u.cls === undefined) return;
    const parent = this.defs.find((x) => x.id === u.group)!, merged = isMerged(parent, (c) => this.classOn(parent.id, c)), st = this.map.getStyle(); if (!st) return;
    const [c0, c1, c2, c3] = u.color, v = densValue(merged) as unknown as maplibregl.ExpressionSpecification;
    for (const l of st.layers) if (l.id.startsWith(`fire-${u.id}-`) && l.id.endsWith("-dens")) {
      this.map.setPaintProperty(l.id, "fill-color", ["interpolate", ["linear"], v, 0, c0, 10, c1, 20, c2, 31, c3] as unknown as maplibregl.ExpressionSpecification);
      this.map.setFilter(l.id, densFilter(parent, u.cls, merged) as maplibregl.FilterSpecification | null);
    }
    this.opacity(u);
  }
  private vis(d: FireDef, on: boolean) {
    const st = this.map.getStyle(); if (!st) return;
    for (const l of st.layers) if (l.id.startsWith(`fire-${d.id}-`)) this.map.setLayoutProperty(l.id, "visibility", on ? "visible" : "none");
  }
  private opacity(d: FireDef | Unit, only?: string) {
    const k = this.scale.get((d as Unit).group ?? d.id) ?? 1, m = only ? only.slice(`fire-${d.id}-`.length) : this.shown.get(d.id);
    if (!m) return;
    const id = this.lid(d, m);
    const par = (d as Unit).cls !== undefined ? this.defs.find((x) => x.id === (d as Unit).group) : undefined, v = densValue(!!par && isMerged(par, (c) => this.classOn(par.id, c))) as unknown as maplibregl.ExpressionSpecification; // the combined bin fades the cell too
    if (this.map.getLayer(id + "-dens")) this.map.setPaintProperty(id + "-dens", "fill-opacity", ["interpolate", ["linear"], v, 0, 0.28 * k, 5, 0.6 * k, 31, 0.92 * k] as unknown as maplibregl.ExpressionSpecification);
    if (this.map.getLayer(id + "-pts")) { this.map.setPaintProperty(id + "-pts", "circle-opacity", 0.35 * k); this.map.setPaintProperty(id + "-pts", "circle-stroke-opacity", 0.95 * k); }
  }
  private status() {
    for (const d of this.defs) {
      let t = "";
      if (d.placeholder) t = this.month >= d.min && this.month <= d.max ? "Placeholder: the model's gridded output will fill this slot" : "";
      else if (this.enabled.has(d.id)) {
        const split = splitMonth(d, this.month), bad = this.units.some((u) => u.group === d.id && this.unitOn(u, this.month) && this.failed.has(this.lid(u, this.month)));
        if (this.have(d, this.month) && bad) t = "Data not available (map file missing)";
        else if (!this.have(d, this.month)) t = this.month < d.min ? `No ${d.sensor.toUpperCase()} data before ${d.min}` : "Not available for this month";
        else t = this.map.getZoom() < this.Z_PTS ? `Colored cells count detections per area; zoom in to zoom ${this.Z_PTS} for individual detections` : "Individual detections (size = sensor footprint)"; if (d.clearing && t) t = "Forest-loss fires only. " + t;
        if (d.classes?.length && t && this.have(d, this.month)) { // sub-selection: say what the boxes do in this month
          const tiled = tiledClasses(d), own = ownClasses(d), lab = (cs: FireClass[]) => cs.map((c) => c.label).join(" and ");
          const on = tiled.filter((c) => this.classOn(d.id, c.id));
          if (tiled.length && !split) t += ` ${lab(tiled)} can be told apart only in ${splitMonths(d).join(", ") || "months with split tiles"}.`;
          else if (tiled.length && !on.length) t = `${lab(tiled)} are both off: nothing is drawn.`;
          else if (tiled.length && on.length < tiled.length) t += ` ${lab(on)} only.`;
          if (own.length && !own.every((c) => this.classOn(d.id, c.id))) t = `${lab(own)} is off: nothing is drawn.`;
        }
      }
      this.onStatus(d.id, t);
    }
  }
}
