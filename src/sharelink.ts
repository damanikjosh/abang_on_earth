/** Share-link keys added in on top of m r c k v l o f: pure functions, no DOM. A link without these keys means the defaults, so every older link still opens as before.
 *  x = classes switched off per layer:  x=drivers:3.5~mines:1   (layer id, then class numbers joined by ".")
 *  p = opacity slider per layer, only when not 1:  p=loss:0.5~fire-viirs:0.35
 *  t = open tab on a phone / tablet: layers | details (timeline is the default and is left out) */
export const TABS = ["layers", "timeline", "details"] as const;
export type Tab = (typeof TABS)[number];
const pairs = (s: string | undefined): [string, string][] => (s ?? "").split("~").map((p) => { const i = p.indexOf(":"); return i > 0 ? ([p.slice(0, i), p.slice(i + 1)] as [string, string]) : null; }).filter((x): x is [string, string] => x !== null);

export function encodeOff(off: Record<string, number[]>): string {
  return Object.entries(off).filter(([, c]) => c.length).map(([row, c]) => `${row}:${[...c].sort((a, b) => a - b).join(".")}`).join("~");
}
/** Only rows and classes that exist (`valid`) are kept; anything else in the link is ignored. */
export function parseOff(s: string | undefined, valid: (row: string, cls: number) => boolean): Record<string, number[]> {
  const out: Record<string, number[]> = {};
  for (const [row, v] of pairs(s)) {
    const c = [...new Set(v.split(".").map(Number).filter((n) => Number.isInteger(n) && valid(row, n)))];
    if (c.length) out[row] = c;
  }
  return out;
}
export const clampOpacity = (x: number): number => Math.min(1, Math.max(0.1, Math.round(x * 20) / 20)); // the slider: 0.1 to 1 in steps of 0.05
export function encodeOpacity(m: Record<string, number>): string {
  return Object.entries(m).filter(([, v]) => Number.isFinite(v) && Math.abs(v - 1) > 1e-9).map(([id, v]) => `${id}:${+v.toFixed(2)}`).join("~");
}
export function parseOpacity(s: string | undefined, valid: (id: string) => boolean): Record<string, number> {
  const out: Record<string, number> = {};
  for (const [id, v] of pairs(s)) { const n = Number(v); if (valid(id) && v.trim() !== "" && Number.isFinite(n)) out[id] = clampOpacity(n); }
  return out;
}
/** vr = chosen variant of a layer with a picker, only when not the default:  vr=mb_palm:share~mb_mine:forest */
export function encodeVariants(m: Record<string, string>): string { return Object.entries(m).map(([id, v]) => `${id}:${v}`).join("~"); }
export function parseVariants(s: string | undefined, valid: (id: string, v: string) => boolean): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [id, v] of pairs(s)) if (valid(id, v)) out[id] = v;
  return out;
}
export const parseTab = (s: string | undefined): Tab | null => ((TABS as readonly string[]).includes(s ?? "") ? (s as Tab) : null);

/** b = map type: "sat" = satellite; plain map is the default and is left out of the link. */
export type BaseMode = "plain" | "sat";
export const parseBase = (s: string | undefined): BaseMode => (s === "sat" ? "sat" : "plain");

/** rg = the metric colour overlay row: "0" = off; anything else, or no key (every older link), = on. */
export const parseRegionsOn = (s: string | undefined): boolean => s !== "0";
