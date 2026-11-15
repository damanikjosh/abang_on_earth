/** Sub-selection of one fire layer: pure helpers, no DOM, no map.
 *  manifest.json, in a fire layer:  "classes": [ {"id": 1, "label": "Day", "path": "fire/modis-day/{month}.pmtiles", "available": ["2002-09"]}, {"id": 2, "label": "Night", "path": "..."} ]
 *  - a class with `path` ("tiled") has its own tile file per month, drawn with the layer's colours;
 *  - a class without `path` ("own") stands for the layer's own file: unticking it hides the layer (e.g. the harmonized layer is night only: only a Night box);
 *  - `disabled: true` (+ `hint`) shows the box greyed and not tickable; it is never on, whatever the link says.
 *  `id` is a whole number: the share link `x=` lists the class numbers switched off, e.g. x=fire-modis:2. */
export interface FireClass { id: number; label: string; path?: string; available?: string[]; disabled?: boolean; hint?: string }
type WithClasses = { classes?: FireClass[] };
export const tiledClasses = (d: WithClasses): FireClass[] => (d.classes ?? []).filter((c) => !!c.path && !c.disabled);
export const ownClasses = (d: WithClasses): FireClass[] => (d.classes ?? []).filter((c) => !c.path && !c.disabled);
/** true when `m` is drawn from the class files of `d` (it has tiled classes and every one has tiles for that month) */
export const splitMonth = (d: WithClasses, m: string): boolean => { const t = tiledClasses(d); return t.length > 0 && t.every((c) => !c.available || c.available.includes(m)); };
/** months in which all tiled classes have tiles */
export const splitMonths = (d: WithClasses): string[] => { const t = tiledClasses(d), a = t[0]?.available; return a ? a.filter((m) => t.every((c) => !c.available || c.available.includes(m))) : []; };
/** may the user (or a link) switch this class on or off? */
export const classEditable = (d: WithClasses, id: number): boolean => !!d.classes?.some((c) => c.id === id && !c.disabled);

// ---- density cells of a layer drawn from two class files (day + night) --------------------------------------------------------------------------------------------------
// Two translucent density layers on top of each other would not look like the combined layer (overlapping cells add up their opacity, a cell with both day and night counts would
// show two light bins instead of one darker one). The class tiles therefore carry, on every `dens` cell, `b` = this class's bin and `bt` = the bin of day + night together, and `o` = 1 when
// the OTHER class has detections in the same cell. With every tiled class ticked: the first class draws all its cells by `bt`; the other class draws only the cells the first one lacks
// (`o` = 0), also by `bt`: every cell is drawn once, with the combined layer's colour. With one class ticked each cell is drawn by its own `b`. Tiles without bt / o fall back to `b`.
export type Expr = unknown[];
/** Which bin value colours (and fades) a density cell: the combined bin when every tiled class is ticked, the class's own bin otherwise. */
export const densValue = (merged: boolean): Expr => (merged ? ["coalesce", ["get", "bt"], ["get", "b"]] : ["get", "b"]);
/** Filter of a class's density layer: with all classes ticked, only the first class draws every cell, the others draw the cells the first lacks. null = no filter. */
export function densFilter(d: WithClasses, clsId: number, merged: boolean): Expr | null {
  const t = tiledClasses(d); return merged && t.length > 1 && t[0].id !== clsId ? ["==", ["coalesce", ["get", "o"], 0], 0] : null;
}
/** True when every tiled class (there are at least two) is on. */
export const isMerged = (d: WithClasses, on: (id: number) => boolean): boolean => { const t = tiledClasses(d); return t.length > 1 && t.every((c) => on(c.id)); };
