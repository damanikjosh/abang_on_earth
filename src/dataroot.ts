/** Which data folder the app reads. public/data-version.json points at it: {"version":"v2","base":"data-v2/","fallback":"data-v2/"}.
 *  Switching versions (or rolling back) = editing that one small file; no code change. Pure functions, no DOM: see tests/dataroot.test.ts. */
export interface Pointer { version: string; base: string; fallback: string }
export const DEFAULT_BASE = "data-v4/"; // what a missing or broken pointer means (v3 is the fallback of v4)
export const V1: Pointer = { version: "v3", base: DEFAULT_BASE, fallback: DEFAULT_BASE };
export type FetchFn = (url: string, init?: { cache?: "no-cache"; signal?: AbortSignal }) => Promise<{ ok: boolean; status: number; json(): Promise<unknown> }>;

/** A folder relative to the site root ("data-v2/"): no scheme, no leading slash, no "..". Anything else -> fallback. Always ends with "/". */
export function cleanBase(b: unknown, dflt: string = DEFAULT_BASE): string {
  if (typeof b !== "string") return dflt;
  const s = b.trim();
  if (!s || /^[a-z][a-z0-9+.-]*:|^\/|\\|(^|\/)\.\.(\/|$)/i.test(s)) return dflt;
  return s.endsWith("/") ? s : s + "/";
}
export function parsePointer(j: unknown): Pointer {
  if (!j || typeof j !== "object") return V1;
  const o = j as Record<string, unknown>, fallback = cleanBase(o.fallback), base = cleanBase(o.base, fallback);
  return { version: typeof o.version === "string" && o.version ? o.version : "v3", base, fallback };
}
/** `siteBase` = Vite BASE_URL ("/" or "/abang_on_earth/"); `dataBase` = pointer base; `path` = file inside the data folder. */
export function dataUrl(siteBase: string, dataBase: string, path: string): string { return siteBase + dataBase + path.replace(/^\/+/, ""); }

/** Never throws: a missing or broken pointer means the default (v2). */
export async function loadPointer(siteBase: string, f: FetchFn, now: () => number = Date.now): Promise<Pointer> {
  try {
    // "?_=<time>" gives every load its own URL: browser and CDN caches (GitHub Pages sends max-age=600) cannot serve a pointer older than the request
    const r = await f(siteBase + "data-version.json?_=" + now(), { cache: "no-cache" });
    return r.ok ? parsePointer(await r.json()) : V1;
  } catch { return V1; }
}
export interface Root { version: string; base: string; fellBack: boolean }
/** Loads `path` (the manifest) from the pointer's base; if that fails, from the fallback. The folder that answered becomes the data root. */
export async function loadFirst<T>(siteBase: string, p: Pointer, path: string, f: FetchFn): Promise<{ data: T; root: Root }> {
  const tries = p.base === p.fallback ? [p.base] : [p.base, p.fallback];
  let err: unknown;
  for (const base of tries) {
    try {
      const r = await f(dataUrl(siteBase, base, path), { cache: "no-cache" });
      if (!r.ok) throw new Error(`${path}: HTTP ${r.status}`);
      return { data: (await r.json()) as T, root: { version: base === p.base ? p.version : "fallback", base, fellBack: base !== p.base } };
    } catch (e) { err = e; }
  }
  throw err;
}

// ---- the data root as ONE unit -------------------------------------------------------------------------------------------
/** Files the app cannot start without. Any of them missing or malformed in the pointed folder = that folder is rejected as a whole. */
export interface CoreData<M, R, Mo, L> { manifest: M; regions: R; monthly: Mo; layersFile: L }
const isObj = (x: unknown): x is Record<string, unknown> => !!x && typeof x === "object" && !Array.isArray(x);
export const isManifest = (x: unknown): boolean => isObj(x) && isObj(x.files) && typeof x.files.regions === "string" && typeof x.files.monthly === "string" && (x.fire_layers === undefined || (isObj(x.fire_layers) && Array.isArray(x.fire_layers.layers)));
export const isRegions = (x: unknown): boolean => isObj(x) && Array.isArray(x.features) && x.features.every((f) => isObj(f) && isObj(f.properties) && typeof f.properties.id === "string");
export const isMonthly = (x: unknown): boolean => isObj(x) && Array.isArray(x.months) && x.months.length > 0 && isObj(x.series);
export const isLayersFile = (x: unknown): boolean => isObj(x) && Array.isArray(x.layers) && x.layers.every((d) => isObj(d) && typeof d.id === "string" && typeof d.legend === "string" && typeof d.path === "string");

async function getChecked<T>(siteBase: string, base: string, path: string, f: FetchFn, check: (x: unknown) => boolean): Promise<T> {
  const r = await f(dataUrl(siteBase, base, path), { cache: "no-cache" });
  if (!r.ok) throw new Error(`${base}${path}: HTTP ${r.status}`);
  const j = await r.json();
  if (!check(j)) throw new Error(`${base}${path}: unexpected content`);
  return j as T;
}
/** Loads manifest, regions, monthly and layers.json from the pointer's base; if ANY of the four fails (HTTP error, network error, bad JSON,
 *  wrong shape) the whole folder is dropped and all four are loaded from the fallback. Nothing is ever mixed between folders.
 *  Per-layer tile files are not part of this: a missing tile file only affects its own layer row. */
export async function loadCore<M, R, Mo, L>(siteBase: string, p: Pointer, f: FetchFn, onManifest?: (manifest: M, base: string) => void): Promise<{ data: CoreData<M, R, Mo, L>; root: Root }> {
  const tries = p.base === p.fallback ? [p.base] : [p.base, p.fallback];
  const errs: string[] = [];
  for (const base of tries) {
    try {
      const manifest = await getChecked<M & { files: { regions: string; monthly: string } }>(siteBase, base, "manifest.json", f, isManifest);
      onManifest?.(manifest as unknown as M, base); // lets the app start the map from the manifest alone while regions, monthly and layers.json are still on their way
      const [regions, monthly, layersFile] = await Promise.all([
        getChecked<R>(siteBase, base, manifest.files.regions, f, isRegions),
        getChecked<Mo>(siteBase, base, manifest.files.monthly, f, isMonthly),
        getChecked<L>(siteBase, base, "layers.json", f, isLayersFile),
      ]);
      return { data: { manifest, regions, monthly, layersFile }, root: { version: base === p.base ? p.version : "fallback", base, fellBack: base !== p.base } };
    } catch (e) { errs.push((e as Error).message); }
  }
  throw new Error(errs.join("; "));
}

/** A request that hangs (not fails) kept the loader up for ever (R3). Every data request gets a deadline covering the answer AND the body; on expiry it is
 *  aborted and rejects with a plain message, so loadCore falls back to the other folder or the app shows the error state with Try again. */
export function withTimeout(f: FetchFn, ms: number): FetchFn {
  return (url, init) => {
    const c = new AbortController(); let timer: ReturnType<typeof setTimeout> | undefined = setTimeout(() => c.abort(), ms);
    const done = () => { if (timer !== undefined) { clearTimeout(timer); timer = undefined; } };
    const late = (e: unknown) => { done(); throw c.signal.aborted ? new Error(`${url.replace(/\?.*$/, "")}: no answer after ${Math.round(ms / 1000)} s`) : e; };
    return f(url, { ...init, signal: c.signal }).then((r) => {
      if (!r.ok) done();
      return { ok: r.ok, status: r.status, json: () => r.json().then((j) => { done(); return j; }, late) };
    }, late);
  };
}
