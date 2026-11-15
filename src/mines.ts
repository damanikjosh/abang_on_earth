/** Mine-outline pop-up: text for a clicked outline of the "mines" layer. Pure function plus one wiring helper. */
import * as maplibregl from "maplibre-gl";
import { esc } from "./layerinfo.ts";

export interface MineProps { id?: string; cc?: string; a?: number; c?: string }
const nf = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
/** "61 ha", "0.3 ha", "1,240 ha" */
export function hectares(a: number): string { return a >= 10 ? `${nf.format(a)} ha` : `${(Math.round(a * 10) / 10).toString()} ha`; }
/** HTML for the pop-up; values are escaped. Commodity list is the source's own ("Coal, Gold"); empty = the source records none. */
export function mineHtml(p: MineProps, countryName: (cc: string) => string = (c) => c): string {
  const c = (p.c ?? "").trim(), size = typeof p.a === "number" ? hectares(p.a) : "";
  return `<b>Mine outline</b><br>${c ? `Commodities: ${esc(c)}` : "Commodity not recorded in the source"}` +
    `${size ? `<br>Outline area: ${esc(size)}` : ""}${p.cc ? `<br>${esc(countryName(p.cc))}` : ""}` +
    `<br><span class="mine-note">Outline from about 2019 satellite imagery plus OpenStreetMap mining areas. Mines opened or closed since are not reflected.</span>`;
}
/** Click an outline -> pop-up; pointer cursor on hover. `layerId` = the fill layer ("ctx-mines-s"). Returns a function that says whether a point hits an outline. */
export function attachMinePopup(map: maplibregl.Map, layerId: string, countryName: (cc: string) => string): (pt: maplibregl.PointLike) => boolean {
  const hit = (pt: maplibregl.PointLike) => !!map.getLayer(layerId) && map.queryRenderedFeatures(pt, { layers: [layerId] }).length > 0;
  map.on("click", layerId, (e) => {
    const f = e.features?.[0]; if (!f) return;
    new maplibregl.Popup({ maxWidth: "280px", className: "mine-pop" }).setLngLat(e.lngLat).setHTML(mineHtml(f.properties as MineProps, countryName)).addTo(map);
  });
  map.on("mouseenter", layerId, () => (map.getCanvas().style.cursor = "pointer"));
  map.on("mouseleave", layerId, () => (map.getCanvas().style.cursor = ""));
  return hit;
}
