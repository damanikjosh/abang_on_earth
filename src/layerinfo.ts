/** Pure helpers for the compact layer list: what the info popover of a row says and which small chip a row wears.
 *  Everything is derived from the layer definitions (layers.json layers[], manifest fire_layers.layers[]); no layer text is written here. No DOM. */
import { covered, DEFAULT_GAP, type Covered } from "./coverage.ts";

/** Optional fields a layer definition may carry for its popover. `long` = longer "How to read this" text (empty until someone writes it). */
/** `important`: the one or two sentences a user must not miss for this layer; shown in a highlighted block at the top of its (i) panel and flagged with a red badge on the (i) button. A string or a list of strings. */
export interface Described { long?: string; source?: string; licence?: string; important?: string | string[] }
export interface InfoDef extends Covered, Described { min?: number | string; max?: number | string; placeholder?: boolean; note?: string }
export interface Cty { code: string; name: string }

export const esc = (s: string): string => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

/** First sentence of a description (for a one-line hover tooltip). */
export function firstSentence(t: string): string {
  const m = /^(.+?[.!?])(\s|$)/.exec(t.trim());
  return m ? m[1] : t.trim();
}
/** "2001-01 to 2025-12", "from 2001-01", "up to 2025"; "" when the definition has no range. */
export function rangeText(d: Pick<InfoDef, "min" | "max">): string {
  const a = d.min, b = d.max;
  if (a != null && b != null) return String(a) === String(b) ? String(a) : `${a} to ${b}`;
  if (a != null) return `from ${a}`;
  if (b != null) return `up to ${b}`;
  return "";
}
/** Countries without data for this layer, with the note to show for them; [] when it covers everything (or the countries are unknown). */
export function coverageNotes(d: InfoDef, countries: Cty[]): string[] {
  if (!d.coverage) return [];
  const out = countries.filter((c) => !covered(d, c.code));
  // "<note> Not available in: Malaysia, Brunei." (was "<note> (Malaysia, Brunei)", which read as if Indonesia contained those countries)
  return out.length ? [`${(d.gap_note || DEFAULT_GAP).replace(/[.\s]+$/, "")}. Not available in: ${out.map((c) => c.name).join(", ")}.`] : [];
}
/** region_gaps grouped by identical text: "<text> (Sarawak)" or "(12 regions)" */
export function regionGapNotes(d: Covered, regionName: (id: string) => string): string[] {
  const by = new Map<string, string[]>();
  for (const [id, t] of Object.entries(d.region_gaps ?? {})) by.set(t, [...(by.get(t) ?? []), id]);
  return [...by].map(([t, ids]) => `${t} (${ids.length <= 3 ? ids.map(regionName).join(", ") : `${ids.length} regions`})`);
}
export interface Chip { text: string; kind: "ph" | "gap" | "only" }
/** The one small chip of a row, or null for ordinary real data. cc = country of the selected region (undefined for "all countries"), gap = the note that applies to the selected region now. */
export function chipFor(d: InfoDef, countries: Cty[], cc: string | undefined, regionGapNow: string): Chip | null {
  if (d.placeholder) return { text: "placeholder", kind: "ph" };
  if (cc && !covered(d, cc)) return { text: "no data here", kind: "gap" };
  if (regionGapNow) return { text: "partial data", kind: "gap" };
  if (d.coverage?.length === 1) return { text: `${countries.find((c) => c.code === d.coverage![0])?.name ?? d.coverage[0]} only`, kind: "only" };
  return null;
}
/** Statuses that just describe what is drawn ("Showing 2019-05") are not warnings: the row keeps them for screen readers and the popover ("Right now"), not as a visible line. */
const ROUTINE = /^(Shown\b|Showing (up to \d{4}|share of area, up to \d{4}|\d{4}-\d{2}$|\d{4} only)|Individual detections|Placeholder:|Slot for)/;
export const isRoutineStatus = (t: string): boolean => !t || ROUTINE.test(t.replace(/^Forest-loss fires only\.\s*/, ""));
