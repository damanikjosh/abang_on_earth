/** Everything the app can start before its own big script has arrived. `early.ts` is a tiny separate script: it runs as soon as it
 *  is downloaded and begins the data requests (pointer, then manifest, then regions / monthly / layers.json) and the basemap style, while the 315 kB app
 *  script is still downloading. app.ts then takes the results with takeEarly(). Same files, same checks, same 15 s deadline as before: only the start moves. */
import { loadPointer, loadCore, withTimeout, type Pointer, type Root, type CoreData } from "./dataroot";
import { applyStoredTheme, isDark } from "./theme";

export const BASE = import.meta.env.BASE_URL; // "/" on abang.earth
/** Deadline for every data request, in ms (default 15 s; `?load_timeout_ms=2000` shortens it for the failure checks). */
export const LOAD_TIMEOUT_MS = (() => { const v = Number(new URLSearchParams(location.search).get("load_timeout_ms")); return v >= 500 && v <= 120000 ? v : 15000; })();
export const fetchT = withTimeout((u, i) => fetch(u, i), LOAD_TIMEOUT_MS);
export const STYLES = { light: "https://tiles.openfreemap.org/styles/positron", dark: "https://tiles.openfreemap.org/styles/dark" };

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Any = any;
export interface Early { ptr: Promise<Pointer>; /** manifest of the first folder tried (null when no folder answered) */ manifest: Promise<Any | null>; core: Promise<{ data: CoreData<Any, Any, Any, Any>; root: Root }> }

/** Warms the browser cache with what MapLibre asks for in a chain after it is created (style, then tile index, sprite index and image), so that chain does
 *  not start from zero when the map is built. Never throws; a miss only costs the request. The tiles and glyphs are left to the map (they depend on the view). */
async function warmBasemap(): Promise<void> {
  try {
    const style = (await (await fetch(STYLES[isDark() ? "dark" : "light"])).json()) as { sources?: Record<string, { url?: unknown }>; sprite?: unknown };
    const urls: string[] = [];
    for (const s of Object.values(style.sources ?? {})) if (typeof s?.url === "string") urls.push(s.url);
    if (typeof style.sprite === "string") { const sp = style.sprite + (devicePixelRatio > 1 ? "@2x" : ""); urls.push(sp + ".json", sp + ".png"); } // the style is not "loaded" (no tile is requested) until the sprite image is in
    await Promise.all(urls.map((u) => fetch(u).then((r) => r.arrayBuffer())));
  } catch { /* the map fetches them itself */ }
}

/** Starts the load once; later callers get the same promises. */
export function startEarly(): Early {
  const w = window as unknown as { __early?: Early };
  if (w.__early) return w.__early;
  applyStoredTheme(); // the basemap style depends on it
  let resolveManifest!: (m: Any | null) => void;
  const manifest = new Promise<Any | null>((r) => (resolveManifest = r));
  const ptr = loadPointer(BASE, fetchT);
  const core = ptr.then((p) => loadCore<Any, Any, Any, Any>(BASE, p, fetchT, (m) => resolveManifest(m)));
  core.then(undefined, () => resolveManifest(null));
  core.catch(() => {}); ptr.catch(() => {}); // the app reports a failure itself; no "unhandled rejection" while it is still loading
  void warmBasemap();
  return (w.__early = { ptr, manifest, core });
}
