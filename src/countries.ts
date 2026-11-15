/** More than one country in the data. Everything here is driven by manifest.json, so adding countries later is data-only:
 *  manifest.countries = [{code, name, total, bounds:[w,s,e,n], viirs_eq_loyo_rel_err?}, ...] (total = id of that country's national series in monthly.json)
 *  manifest.all       = {id, name} (id of the "all countries" series; optional)
 *  monthly.series[id].country = ISO-3 code (regions and national series); series[id].viirs_eq_unreliable = true -> the VIIRS-equivalent before VIIRS is hidden.
 *  Without manifest.countries (Indonesia-only data folders such as data-v2) nothing in this file is used and the app behaves exactly as before. Pure functions, no DOM. */
export interface CountryDef { code: string; name: string; total: string; bounds: [number, number, number, number]; viirs_eq_loyo_rel_err?: number }
export interface AllDef { id: string; name: string }
export interface Multi { countries: CountryDef[]; all: AllDef | null }
const isObj = (x: unknown): x is Record<string, unknown> => !!x && typeof x === "object" && !Array.isArray(x);
const isCountry = (c: unknown): c is CountryDef => isObj(c) && typeof c.code === "string" && typeof c.name === "string" && typeof c.total === "string"
  && Array.isArray(c.bounds) && c.bounds.length === 4 && c.bounds.every((n) => typeof n === "number" && Number.isFinite(n));

/** null = single-country data (legacy behaviour). Needs at least two well-formed countries. */
export function parseCountries(manifest: unknown): Multi | null {
  if (!isObj(manifest) || !Array.isArray(manifest.countries)) return null;
  const countries = manifest.countries.filter(isCountry);
  if (countries.length < 2 || countries.length !== manifest.countries.length) return null;
  const a = manifest.all, all = isObj(a) && typeof a.id === "string" && typeof a.name === "string" ? { id: a.id, name: a.name } : null;
  return { countries, all };
}
/** Map bounds containing every country: [[w,s],[e,n]]. */
export function unionBounds(cs: { bounds: [number, number, number, number] }[]): [[number, number], [number, number]] {
  const b = cs.map((c) => c.bounds);
  return [[Math.min(...b.map((x) => x[0])), Math.min(...b.map((x) => x[1]))], [Math.max(...b.map((x) => x[2])), Math.max(...b.map((x) => x[3]))]];
}
export const boundsOf = (c: CountryDef): [[number, number], [number, number]] => [[c.bounds[0], c.bounds[1]], [c.bounds[2], c.bounds[3]]];

export interface RegionGroup { label: string | null; ids: string[] }
/** Ids for the region list. country "all": the all-total, then one group per country (its national total, then its regions); a country code: that country only. */
export function regionGroups(m: Multi, country: string, regionsOf: (code: string) => string[]): RegionGroup[] {
  const one = (c: CountryDef): RegionGroup => ({ label: c.name, ids: [c.total, ...regionsOf(c.code)] });
  if (country === "all") return [...(m.all ? [{ label: null, ids: [m.all.id] }] : []), ...m.countries.map(one)];
  const c = m.countries.find((x) => x.code === country);
  return c ? [{ label: null, ids: one(c).ids }] : [];
}
/** Country selected after a deep link: the region's country wins, then the c= value, then "all" (or the first country when the data has no all-series). */
export function startCountry(m: Multi, region: string | undefined, c: string | undefined, countryOfId: (id: string) => string | undefined): string {
  const ok = (x: string | undefined) => !!x && (x === "all" ? !!m.all : m.countries.some((k) => k.code === x));
  if (region && m.all && region === m.all.id) return "all";
  const rc = region ? countryOfId(region) : undefined;
  if (rc && ok(rc)) return rc;
  if (ok(c)) return c!;
  return m.all ? "all" : m.countries[0].code;
}
/** A series whose VIIRS-equivalent before VIIRS existed (months flagged estimated) must not be shown: the ratio is fitted on too few detections. */
export function hiddenEstimate(series: Record<string, unknown> | undefined, metric: string, i: number): boolean {
  if (!series || metric !== "viirs_eq" || series.viirs_eq_unreliable !== true) return false;
  const fl = series.viirs_eq_flag; return Array.isArray(fl) && fl[i] === 1;
}
/** Region-level "no data here" note of a layer def (e.g. Descals has no oil-palm tiles over part of Sarawak): layers.json `region_gaps: {"<region id>": "<note>"}`. */
export const regionGap = (d: { region_gaps?: Record<string, string> }, rid: string): string => d.region_gaps?.[rid] ?? "";

/** The full 11-country set (the ASEAN members: IDN MYS BRN SGP THA MMR LAO KHM VNM PHL TLS). */
export const ASEAN = ["IDN", "MYS", "BRN", "SGP", "THA", "MMR", "LAO", "KHM", "VNM", "PHL", "TLS"];
const andList = (n: string[]) => (n.length > 1 ? `${n.slice(0, -1).join(", ")} and ${n[n.length - 1]}` : n[0]);
/** Coverage phrase of the home page. Exactly the 11-country set -> "Southeast Asia" (headline "across Southeast Asia"); 1-4 countries -> their names; any other set -> "N countries in Southeast Asia". `full` = the plain list (shown under the headline when the phrase is shorter). */
export function coveragePhrase(cs: { code: string; name: string }[]): { phrase: string; full: string; prep: string } {
  const full = andList(cs.map((c) => c.name));
  if (cs.length === ASEAN.length && ASEAN.every((a) => cs.some((c) => c.code === a))) return { phrase: "Southeast Asia", full, prep: "across" };
  if (cs.length <= 4) return { phrase: full, full, prep: "in" };
  return { phrase: `${cs.length} countries in Southeast Asia`, full, prep: "in" };
}

/** Bounding box [[w,s],[e,n]] of a GeoJSON Polygon / MultiPolygon; null for anything else or an empty geometry. Used to fly to a region. */
export function geomBounds(g: unknown): [[number, number], [number, number]] | null {
  if (!isObj(g) || !Array.isArray(g.coordinates) || (g.type !== "Polygon" && g.type !== "MultiPolygon")) return null;
  let w = Infinity, s = Infinity, e = -Infinity, n = -Infinity;
  const walk = (c: unknown): void => {
    if (!Array.isArray(c)) return;
    if (typeof c[0] === "number" && typeof c[1] === "number") { w = Math.min(w, c[0]); e = Math.max(e, c[0]); s = Math.min(s, c[1]); n = Math.max(n, c[1]); return; }
    c.forEach(walk);
  };
  walk(g.coordinates);
  return Number.isFinite(w) && Number.isFinite(s) ? [[w, s], [e, n]] : null;
}
