/** Map type: "plain" = the OpenFreeMap style as before; "sat" = NASA GIBS Blue Marble (cloud-free) under our layers.
 *  The plain style stays loaded: on satellite its fills and lines are hidden and its place names get a white text with a dark halo; the imagery is one raster
 *  layer at the very bottom. Switching back restores every property it touched, so the plain look is unchanged. No setStyle, so our own layers are never reloaded. */
import type * as maplibregl from "maplibre-gl";
import type { BaseMode } from "./sharelink";

export const SAT = {
  source: "sat", layer: "sat-raster", maxzoom: 8, // Blue Marble Next Generation is ~500 m: GIBS serves it to zoom 8, MapLibre stretches it beyond
  tiles: "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/BlueMarble_NextGeneration/default/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpeg",
  attribution: `Imagery: <a href="https://nasa-gibs.github.io/gibs-api-docs/" target="_blank" rel="noopener">NASA GIBS</a> (Blue Marble: Next Generation)`,
};
/** Colours drawn on top of the imagery (borders and selection); the plain map keeps its own. */
export const SAT_LINE = "#f4f4f4";
export const NOTE: Record<BaseMode, string> = { plain: "OpenFreeMap, OpenStreetMap contributors", sat: "NASA GIBS Blue Marble (about 500 m, cloud-free)" };
export const FAIL_NOTE = "Satellite imagery could not be loaded. Showing the plain map.";

type Saved = { vis?: unknown; tc?: unknown; hc?: unknown; hw?: unknown };
export class Basemap {
  mode: BaseMode = "plain";
  private base: string[] = [];
  private saved = new Map<string, Saved>();
  private errs = 0;
  onFail: () => void = () => {};
  constructor(private map: maplibregl.Map) {
    map.on("error", (e) => { if ((e as { sourceId?: string }).sourceId === SAT.source && this.mode === "sat" && ++this.errs >= 3) this.onFail(); });
    map.on("data", (e) => { if ((e as { sourceId?: string; tile?: unknown }).sourceId === SAT.source && (e as { tile?: unknown }).tile) this.errs = 0; });
  }
  /** Call right after a style loaded, before our own layers are added: remembers the basemap's layers and how they were painted. */
  snapshot() {
    const m = this.map; this.base = m.getStyle().layers.map((l) => l.id); this.saved.clear();
    for (const id of this.base) {
      const l = m.getLayer(id)!;
      this.saved.set(id, l.type === "symbol"
        ? { vis: m.getLayoutProperty(id, "visibility"), tc: m.getPaintProperty(id, "text-color"), hc: m.getPaintProperty(id, "text-halo-color"), hw: m.getPaintProperty(id, "text-halo-width") }
        : { vis: m.getLayoutProperty(id, "visibility") });
    }
  }
  apply() {
    const m = this.map; if (!m.getStyle() || !this.base.length) return;
    const sat = this.mode === "sat";
    if (sat && !m.getSource(SAT.source)) {
      m.addSource(SAT.source, { type: "raster", tiles: [SAT.tiles], tileSize: 256, maxzoom: SAT.maxzoom, attribution: SAT.attribution });
      m.addLayer({ id: SAT.layer, type: "raster", source: SAT.source, paint: { "raster-fade-duration": 0 } }, this.base[0]);
    } else if (!sat && m.getSource(SAT.source)) { if (m.getLayer(SAT.layer)) m.removeLayer(SAT.layer); m.removeSource(SAT.source); }
    for (const id of this.base) {
      const l = m.getLayer(id), s = this.saved.get(id); if (!l || !s) continue;
      if (l.type !== "symbol") { m.setLayoutProperty(id, "visibility", sat ? "none" : ((s.vis as "visible" | "none" | undefined) ?? "visible")); continue; }
      if (sat) { m.setPaintProperty(id, "text-color", "#ffffff"); m.setPaintProperty(id, "text-halo-color", "rgba(0,0,0,0.85)"); m.setPaintProperty(id, "text-halo-width", 1.6); }
      else { m.setPaintProperty(id, "text-color", s.tc as never); m.setPaintProperty(id, "text-halo-color", s.hc as never); m.setPaintProperty(id, "text-halo-width", s.hw as never); }
    }
  }
}
