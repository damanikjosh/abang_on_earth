import "./common";
import "./app.css";
import "maplibre-gl/dist/maplibre-gl.css";
import * as maplibregl from "maplibre-gl";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import { initTheme, isDark } from "./theme";
import { ContextLayers, ensureProtocol, type LayersFile } from "./layers";
import { attachMinePopup } from "./mines";
import { displayName } from "./names";
import { DOCK_QUERY, isDockLayout, isSideLayout } from "./layout";
import { FireLayers, type FireFile, type FireDef } from "./fire";
import { dataUrl, DEFAULT_BASE } from "./dataroot";
import { fetchT, STYLES, startEarly } from "./boot";
import { encodeOff, parseOff, parseTab, parseBase, parseRegionsOn, encodeVariants, parseVariants } from "./sharelink";
import "./layerpanel/layerpanel.css";
import { classEditable, splitMonth, tiledClasses } from "./fireclasses";
import { OnTheMapList, LayerCatalogue, InfoPopover, decodeState, encodeState, activeOrder, setActive, applyActiveOrder, setOpacity, opacityOf, setOpenGroups, type PanelState, type Defaults, type InfoContent } from "./layerpanel/index.ts";
import { GROUPS, HIDDEN_ROWS, REMOVED_ROWS, DEFAULT_OPEN } from "./layergroups";
import { Basemap, SAT_LINE, NOTE, FAIL_NOTE } from "./basemap";
import { countryOf, gapNote } from "./coverage";
import { parseCountries, unionBounds, boundsOf, regionGroups, startCountry, hiddenEstimate, regionGap, geomBounds, type CountryDef } from "./countries";
import { esc, firstSentence, rangeText, coverageNotes, regionGapNotes, chipFor, isRoutineStatus, type Cty, type InfoDef } from "./layerinfo";

type Series = Record<string, any>; // arrays of numbers, plus per-series scalars (loyo_rel_err, country, viirs_eq_unreliable)
interface Regions { type: "FeatureCollection"; features: { properties: { id: string; name: string; country?: string }; geometry?: unknown }[] }
interface Monthly { months: string[]; series: Record<string, Series> }
interface Harm { method: string; note: string; label?: string }
interface Manifest { schema_version: number; sources?: string; countries?: unknown; all?: unknown; notes_ui?: { regions_note?: string }; placeholder?: boolean; title: string; harmonization?: Harm; fire_layers?: FireFile; files: { regions: string; monthly: string; annual?: string; borders?: string; outlines?: string } }
interface StudyAgg { years?: number[]; months?: string[]; series: Record<string, Record<string, number[] | number>> }
interface Annual { years: number[]; units: Record<string, string>; series: Record<string, { loss_ha: number[]; palm_ha_cum: (number | null)[] }> }

maplibregl.setWorkerUrl(workerUrl);
const BASE = import.meta.env.BASE_URL; // "/abang_on_earth/" on a project Pages URL, "/" in dev if BASE=/
const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
let dataBase = BASE + DEFAULT_BASE; // URL prefix of the data folder; set from public/data-version.json in main() (default = data-v3/)
const getJSON = async <T,>(p: string): Promise<T> => {
  const r = await fetchT(dataBase + p, { cache: "no-cache" }); // revalidate (ETag) so a deploy shows up without a hard refresh
  if (!r.ok) throw new Error(`${p}: HTTP ${r.status}`);
  return (await r.json()) as T;
};

function heat(t: number): string {
  const cs = getComputedStyle(document.documentElement);
  const stops = ["--heat0", "--heat1", "--heat2", "--heat3"].map((v) => hex(cs.getPropertyValue(v).trim()));
  const x = Math.min(1, Math.max(0, t)) * 3, i = Math.min(2, Math.floor(x)), f = x - i;
  const c = stops[i].map((a, k) => Math.round(a + (stops[i + 1][k] - a) * f));
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}
function hex(h: string): number[] {
  const m = h.replace("#", "");
  return [0, 2, 4].map((k) => parseInt(m.slice(k, k + 2), 16));
}

function readHash(): Record<string, string> {
  try { return Object.fromEntries(new URLSearchParams(location.hash.slice(1))); } catch { return {}; }
}
/** Padding for fitBounds so a country is framed in the part of the map that no panel covers (was a fixed 230 px on phones while the open Layers dock is ~440 px).
 *  Phone: top = bottom of the top bar, bottom = height of the dock as it is NOW; desktop: the floating panels. */
function fitPadding() {
  const h = innerHeight;
  if (isDockLayout()) {
    const top = (document.querySelector(".topbar")?.getBoundingClientRect().bottom ?? 64) + 8, r = document.getElementById("dock")?.getBoundingClientRect();
    if (isSideLayout()) return { top, bottom: 16, left: (r?.right ?? 360) + 12, right: 12 }; // short landscape: the dock is a left side sheet
    return { top, bottom: Math.max(60, h - (r?.top ?? h - 230) + 8), left: 12, right: 12 };
  }
  return { top: 80, bottom: h >= 820 ? 300 : 150, left: 380, right: 300 };
}

type Bounds = [[number, number], [number, number]];
const DEFAULT_BOUNDS: Bounds = [[94.5, -11.5], [141.5, 6.5]];
// credits that must be visible on the map (licence audit); the basemap adds "OpenFreeMap / OpenMapTiles / OpenStreetMap contributors" itself
const CREDITS = ["Source: EC JRC (TMF)", "Hansen et al. 2013, GFC v1.13, CC BY 4.0", "Descals et al. 2024, CC BY 4.0", "Gumbricht et al., CIFOR, CC BY 4.0", "MCD64A1, NASA LP DAAC", "NASA FIRMS", "Sims et al. 2025, CC BY 4.0", "MapBiomas Indonesia Collection 4 v2, CC BY-SA",
  `\u00a9 <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap contributors</a> (ODbL 1.0), via geoBoundaries &middot; <a href="../credits/">all credits</a>`];

/** The map with its controls. Created as soon as the opening view is known (see main). */
function makeMap(view: { center: [number, number]; zoom: number } | { bounds: Bounds }): maplibregl.Map {
  const map = new maplibregl.Map({ container: "map", style: isDark() ? STYLES.dark : STYLES.light, ..."bounds" in view ? { bounds: view.bounds, fitBoundsOptions: { padding: fitPadding() } } : view, attributionControl: { compact: isDockLayout(), customAttribution: CREDITS } });
  // phones: the credits control starts collapsed behind its "i" button (MapLibre opens a compact control by default = ~6 lines over the map). One tap shows every credit incl. the OpenStreetMap notice; full list on /credits/ (Menu).
  if (isDockLayout()) { const fold = () => { const a = document.querySelector(".maplibregl-ctrl-attrib"); a?.classList.remove("maplibregl-compact-show"); a?.removeAttribute("open"); }; fold(); map.once("load", fold); } // at once (the control exists after the constructor) and once more after load
  map.setMissingStyleImageResolver(async (id) => { if (!map.hasImage(id)) map.addImage(id, { width: 1, height: 1, data: new Uint8Array(4) }); }); // the OpenFreeMap dark style names a sprite it lacks ("circle-11"); an empty pixel replaces the console warning (the styleimagemissing event cannot: MapLibre 6 warns after firing it)
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");
  Object.assign(window, { __map: map }); // for scripts/trace_load.py and perf_layers.py; app-ready is signalled separately (__appReady)
  return map;
}

/** What a row's popover shows (from the layer definition) and what is true about it right now (status line, gap note). */
interface RowInfo { name: string; desc: string; extraDesc?: string; def?: InfoDef; range?: string; real: boolean; cov?: string[] }
const infos = new Map<string, RowInfo>();
const now = new Map<string, { status: string; gap: string }>();
let popRefresh: (rowId: string) => void = () => {};
let markNa: (rowId: string, na: boolean) => void = () => {};
let syncBoxes: () => void = () => {}; // fire class boxes follow the selected month: greyed (and ticked) in a month without per-class tiles
let impRefresh: (rowId: string) => void = () => {}; // the row's important block / badge may have changed (status, chip)
const impChip = new Map<string, string>(); // row id -> must-know sentence from the coverage chip ("Indonesia only", "No data here", "Partial data"), set by refreshGaps
const isProblem = (t: string) => /Data not available|Not available for this month|^No \w+ data before|No class selected/.test(t);
let refreshExtra: (rowId: string) => void = () => {}; // set when the layer panel is built (the row's status line changed)
/** Writes a layer row's status line. A routine status ("Showing 2019-05") stays in the DOM for screen readers and the popover but is not drawn under the row; anything that needs attention (zoom in, no data this month, fallback) is. A layer whose tile files are missing shows "Data not available" and the row is greyed (the rest of the app is unaffected). */
const MIN_FOR_PCT = 20;
function setStatus(rowId: string, t: string) {
  const e = document.getElementById("ls-" + rowId); if (e) { e.textContent = t; e.classList.toggle("routine", isRoutineStatus(t)); }
  markNa(rowId, isProblem(t));
  now.set(rowId, { status: t, gap: now.get(rowId)?.gap ?? "" }); popRefresh(rowId); refreshExtra(rowId); impRefresh(rowId);
}

async function main() {
  let hashT = 0; // debounce timer of writeHash (declared first: setTab may call it during start-up)
  // version pointer first (no-cache); a missing/broken pointer or data folder silently falls back to data-v3/
  ensureProtocol(); // pmtiles:// must exist before any layer, whatever happens to layers.json
  // The load itself was started by early.ts (or starts now) while the app script was still downloading: pointer, then manifest + regions + monthly + layers.json as one unit
  // from the pointed folder, or all four from the fallback (src/boot.ts, src/dataroot.ts).
  const early = startEarly(), H = readHash(); // deep link: #m=2024-05&r=riau&k=modis_eq&l=loss,alerts&v=lng,lat,zoom
  const hv = H.v?.split(",").map(Number), hasView = !!hv && hv.length === 3 && hv.every(Number.isFinite);
  // The basemap does not need the data, only the opening view. A saved view (v=) or the default view (all countries = the union of the countries in the manifest) is known from the
  // manifest alone, so the map starts then, in parallel with regions / monthly / layers.json. Any other link (a region or country in the hash) waits for the data, as before.
  let map!: maplibregl.Map;
  const manifest0 = hasView || (!H.r && !H.c) ? (await early.manifest) as Manifest | null : null, multi0 = manifest0 ? parseCountries(manifest0) : null;
  if (manifest0 && (hasView || multi0?.all)) map = makeMap(hasView ? { center: [hv![0], hv![1]], zoom: hv![2] } : { bounds: unionBounds(multi0!.countries) });
  const first = await early.core as { data: { manifest: Manifest; regions: Regions; monthly: Monthly; layersFile: LayersFile }; root: { version: string; base: string; fellBack: boolean } };
  const ptr = await early.ptr;
  const { manifest, regions, monthly, layersFile: lf } = first.data; dataBase = dataUrl(BASE, first.root.base, "");
  Object.assign(window, { __dataRoot: first.root });
  if (first.root.fellBack) console.info(`data folder ${ptr.base} not available; using ${first.root.base}`);
  // the forest-loss fire layers (clrm, clrv) are no longer offered; their tiles and series stay in the data folder (one commit brings them back)
  if (manifest.fire_layers) manifest.fire_layers.layers = manifest.fire_layers.layers.filter((d) => !d.clearing);
  if (manifest.placeholder) {
    const b = $("banner"); b.hidden = false; b.textContent = "Fire counts: placeholder data"; b.title = manifest.title;
  }
  // Yearly and study aggregates (annual.json, peat, burned-area, tmf) only feed the Details card, not the opening view: they load once the map is idle or the Details tab
  // is opened, whichever comes first (loadStudy below), and the card says "…" until then. A file that is missing still shows "–".
  const study: { annual: Annual | null; peat: StudyAgg | null; burn: StudyAgg | null; tmf: StudyAgg | null; state: "idle" | "loading" | "done" } = { annual: null, peat: null, burn: null, tmf: null, state: "idle" };
  const names: Record<string, string> = {};
  regions.features.forEach((f) => (names[f.properties.id] = displayName(f.properties.name)));
  names["indonesia"] = "Indonesia (national)";
  // more than one country in the data (manifest.countries): country selector, national series per country, "all countries" total. Absent = Indonesia-only, unchanged behaviour.
  const multi = parseCountries(manifest);
  if (multi) { for (const c of multi.countries) names[c.total] = `${c.name} (national)`; if (multi.all) names[multi.all.id] = `${multi.all.name} (total)`; }
  const ids = regions.features.map((f) => f.properties.id).filter((i) => i in monthly.series); // regions drawn on the map / used for the colour scale
  const allIds = Object.keys(monthly.series).sort((a, b) => (a === "indonesia" ? -1 : b === "indonesia" ? 1 : (names[a] ?? a).localeCompare(names[b] ?? b)));
  const cOfId = (id: string): string | undefined => (multi ? (monthly.series[id]?.country as string | undefined) ?? regions.features.find((f) => f.properties.id === id)?.properties.country : undefined);
  const cDef = (code: string): CountryDef | undefined => multi?.countries.find((c) => c.code === code);
  let country = "all"; // selected country code, or "all"; only meaningful when `multi`
  const boundsCache = new Map<string, [[number, number], [number, number]] | null>();
  /** Where the map goes for a region id: a country total = the country, the all-total = every country, otherwise the region's own outline. null = unknown (no move). */
  const boundsFor = (id: string): [[number, number], [number, number]] | null => {
    if (!boundsCache.has(id)) {
      let b: [[number, number], [number, number]] | null = null;
      if (multi && multi.all && id === multi.all.id) b = unionBounds(multi.countries);
      else if (multi && cDef(cOfId(id) ?? "")?.total === id) b = boundsOf(cDef(cOfId(id)!)!);
      else b = geomBounds(regions.features.find((f) => f.properties.id === id)?.geometry);
      boundsCache.set(id, b);
    }
    return boundsCache.get(id)!;
  };

  let resetHover: () => void = () => {}; // clears the click-preview outline (assigned where the click rule is set up)
  let countryOn = false, countryOp = 1; // "Countries" row: the same overlay at country level, its own metric (kc= in the link)
  let regionsOn = parseRegionsOn(H.rg), regionsOp = 1; // regionsOn: the colour overlay row is on; regionsOp: its opacity from the (i) panel // the metric colour overlay is a layer row: rg=0 in the link = off; default on
  const countrySel = document.createElement("select"); // metric of the Countries overlay: same options as Provinces
  countrySel.id = "metric-country"; countrySel.innerHTML = $<HTMLSelectElement>("metric").innerHTML;
  const metricSel = $<HTMLSelectElement>("metric"), regionSel = $<HTMLSelectElement>("region");
  const optHtml = (i: string) => `<option value="${i}">${names[i] ?? i}</option>`;
  const byName = (a: string, b: string) => (names[a] ?? a).localeCompare(names[b] ?? b);
  const regionsOf = (code: string) => ids.filter((i) => cOfId(i) === code).sort(byName);
  function fillRegions() { // legacy: one flat list; multi: the selected country (or all, grouped by country)
    if (!multi) { regionSel.innerHTML = allIds.map(optHtml).join(""); return; }
    regionSel.innerHTML = regionGroups(multi, country, regionsOf).map((g) => g.label ? `<optgroup label="${g.label}">${g.ids.map(optHtml).join("")}</optgroup>` : g.ids.map(optHtml).join("")).join("");
  }
  let month = monthly.months[monthly.months.length - 1];
  if (H.m && monthly.months.includes(H.m)) month = H.m;
  if (multi) country = startCountry(multi, H.r && H.r in monthly.series ? H.r : undefined, H.c, cOfId);
  fillRegions();
  if (multi && !(H.r && H.r in monthly.series)) regionSel.value = country === "all" ? multi.all!.id : cDef(country)!.total;
  if (H.r && [...regionSel.options].some((o) => o.value === H.r)) regionSel.value = H.r;
  const baselineName = manifest.harmonization ? manifest.harmonization.method : "";
  if (manifest.harmonization?.label) $("d-estnote").innerHTML = `<i class="est-sw"></i> ${manifest.harmonization.label}`; // the data folder says which ratio was fitted and where
  if (manifest.notes_ui?.regions_note) $("lnote").textContent = manifest.notes_ui.regions_note;
  if (H.k && [...metricSel.options].some((o) => o.value === H.k)) metricSel.value = H.k;
  if (H.kc && [...countrySel.options].some((o) => o.value === H.kc)) countrySel.value = H.kc;

  const val = (rid: string, ym: string, k = metricSel.value): number | null => {
    const arr = monthly.series[rid]?.[k];
    const i = monthly.months.indexOf(ym);
    if (hiddenEstimate(monthly.series[rid], k, i)) return null; // Brunei / Singapore: no VIIRS-equivalent before VIIRS (unreliable ratio)
    return Array.isArray(arr) && i >= 0 ? arr[i] : null;
  };
  const est = (rid: string, ym: string, k = metricSel.value): boolean => {
    const i = monthly.months.indexOf(ym);
    return i >= 0 && monthly.series[rid]?.[k + "_flag"]?.[i] === 1;
  };
  const scaleIds = () => (multi && country !== "all" ? regionsOf(country) : ids); // colour scale: the selected country's regions (Indonesia alone = as before)
  const maxAll = () => {
    let m = 1;
    for (const rid of scaleIds()) for (const v of monthly.series[rid][metricSel.value] ?? []) if (v != null && v > m) m = v;
    return m;
  };
  const norm = (v: number | null, mx: number) => (v == null ? -1 : Math.sqrt(v / mx));

  const years = [...new Set(monthly.months.map((m) => m.slice(0, 4)))];
  const MON = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  const label = (ym: string) => `${MON[Number(ym.slice(5)) - 1]} ${ym.slice(0, 4)}`;
  function drawCalendar() { // years = columns, months = rows; a compact heat grid
    const mx = maxAll(), rid = regionSel.value;
    let h = `<div></div>` + years.map((y, i) => `<div class="yh">${i % 5 === 0 ? "'" + y.slice(2) : ""}</div>`).join("");
    for (let m = 1; m <= 12; m++) {
      h += `<div class="yl">${MON[m - 1][0]}</div>`;
      for (const y of years) {
        const ym = `${y}-${String(m).padStart(2, "0")}`, v = val(rid, ym), t = norm(v, mx);
        const e = est(rid, ym);
        const style = t < 0 ? `background:repeating-linear-gradient(45deg,transparent 0 3px,var(--line) 3px 4px)` : e ? `background:repeating-linear-gradient(135deg,var(--hatch) 0 1.5px,transparent 1.5px 3.5px),${heat(t)}` : `background:${heat(t)}`;
        h += `<div class="c${ym === month ? " sel" : ""}${e ? " est" : ""}" data-m="${ym}" style="${style}" title="${label(ym)}: ${v ?? "no data"}${e ? " (estimated, ratio baseline)" : ""}"></div>`;
      }
    }
    $("cal").style.gridTemplateColumns = `16px repeat(${years.length},minmax(0,1fr))`;
    $("cal").innerHTML = h;
  }
  $("cal").addEventListener("click", (e) => {
    const el = (e.target as HTMLElement).closest<HTMLElement>(".c");
    if (el) { month = el.dataset.m!; refresh(); }
  });
  const optText = (e: HTMLSelectElement) => e.selectedOptions[0]?.textContent ?? "";
  const METRICS = ["modis_raw", "viirs_raw", "modis_eq", "viirs_eq"];
  function drawDetails() {
    const { annual, peat: peatAgg, burn: burnAgg, tmf: tmfAgg } = study;
    const rid = regionSel.value, v = val(rid, month);
    $("d-name").textContent = names[rid] ?? rid;
    $("d-month").textContent = label(month); $("d-unit").textContent = "Counts are detections in this month, added up over the region.";
    const fmt = (x: number | null | undefined) => (x == null ? "no data" : x.toLocaleString());
    $("d-modis").textContent = fmt(val(rid, month, "modis_raw")); $("d-viirs").textContent = fmt(val(rid, month, "viirs_raw"));
    const e = est(rid, month), i = monthly.months.indexOf(month);
    // Details never depend on the metric: the same rows for every metric; the metric only highlights its row (.hl) and the chip names it
    const eqText = (k: "modis_eq" | "viirs_eq", flagId: string, valId: string) => {
      const h = k === "viirs_eq" && hiddenEstimate(monthly.series[rid], k, i), ee = est(rid, month, k), er = monthly.series[rid]?.[k + "_err"]?.[i];
      $(valId).textContent = h ? "not shown" : fmt(val(rid, month, k)) + (ee && er != null ? ` \u00b1${er.toLocaleString()}` : "");
      const fl = $(flagId); fl.textContent = h ? "" : ee ? "estimated (ratio baseline)" : "observed"; fl.className = "flag" + (ee && !h ? " est" : ""); // hid: the warning above already says nothing is estimated here
      return h;
    };
    const hid = eqText("viirs_eq", "d-flag", "d-det"); eqText("modis_eq", "d-meqf", "d-meq");
    const wn = $("d-warn"), cdef = cDef(cOfId(rid) ?? ""), ownErr = monthly.series[rid]?.loyo_rel_err as number | undefined, who = cdef && cdef.total === rid ? cdef.name : names[rid] ?? "this region"; // the region's OWN leave-one-year-out error, not its country's
    wn.hidden = !hid; wn.textContent = hid ? `Before 2012 there is no VIIRS to compare with, and for ${who} the MODIS-to-VIIRS ratio is too uncertain to use${ownErr != null ? ` (leave-one-year-out error ${Math.round(ownErr * 100)} %)` : ""}. Nothing is shown instead of a guess; the MODIS counts above are observed.` : "";
    const cm_ = regionsOn ? metricSel.value : countryOn ? countrySel.value : ""; // the metric of whichever overlay is on
    for (const k of METRICS) $("dr-" + k).classList.toggle("hl", cm_ === k);
    $("d-chip").textContent = `Map colour: ${regionsOn ? optText(metricSel) : countryOn ? `${optText(countrySel)} by country` : "off"}`;
    if (hid) $<HTMLDetailsElement>("ds-fires").open = true; // a section with a warning opens itself
    const ar = annual?.series[rid], yi = annual ? annual.years.indexOf(Number(month.slice(0, 4))) : -1; // yearly aggregates: Indonesia-only
    const palmDef = lf.layers.find((d) => d.id === "palm"), pgap = palmDef ? regionGap(palmDef, rid) : "";
    // the oil-palm map ends in palmDef.max (2021): later months show that last year, labelled as such (the row used to show "–" for 2022-2025 with no reason)
    const calYear = Number(month.slice(0, 4)), palmLast = Number(palmDef?.max), pyr = Number.isFinite(palmLast) ? Math.min(calYear, palmLast) : calYear;
    const pyi = annual ? annual.years.indexOf(pyr) : -1, pc = ar && pyi >= 0 ? ar.palm_ha_cum[pyi] : null;
    $("d-loss-l").textContent = `Forest loss in ${calYear}`; $("d-palm-l").textContent = `Oil palm planted up to ${pyr}`; // the period is in the label, the hint line is hidden on most laptops
    $("d-loss").textContent = ar && yi >= 0 ? Math.round(ar.loss_ha[yi]).toLocaleString() + " ha" : "–";
    const palmCc = rid === multi?.all?.id ? undefined : cOfId(rid), palmNone = !!(palmDef && palmCc && gapNote(palmDef, palmCc)); // country the oil-palm layer does not cover (layers.json coverage): no figure, even if stray map pixels exist
    // "All countries": the sum over the countries the oil-palm map covers, with the others named (the total showed "–" because annual.json cannot sum countries that have no dated map)
    let allPalm: { ha: number; n: number; missing: string[] } | null = null;
    if (multi && rid === multi.all?.id && palmDef && annual && pyi >= 0) {
      const cov = multi.countries.filter((c) => !gapNote(palmDef, c.code) && annual.series[c.total]?.palm_ha_cum[pyi] != null);
      if (cov.length) allPalm = { ha: cov.reduce((t, c) => t + (annual.series[c.total].palm_ha_cum[pyi] as number), 0), n: cov.length, missing: multi.countries.filter((c) => !cov.includes(c)).map((c) => c.name) };
    }
    $("d-palm").textContent = allPalm ? Math.round(allPalm.ha).toLocaleString() + " ha" : pc != null && !palmNone ? Math.round(pc).toLocaleString() + " ha" : "–";
    if (allPalm) { const sm = document.createElement("small"); sm.className = "gapnote"; sm.textContent = `${allPalm.n} of ${multi!.countries.length} countries; no dated oil-palm map for ${allPalm.missing.join(", ")}`; $("d-palm").append(document.createElement("br"), sm); }
    if (calYear > pyr && (pc != null || allPalm) && !palmNone) { const sm = document.createElement("small"); sm.className = "gapnote"; sm.textContent = `no oil-palm map after ${pyr}`; $("d-palm").append(document.createElement("br"), sm); }
    if (pgap) { const s = document.createElement("small"); s.className = "gapnote"; s.textContent = pgap; $("d-palm").append(document.createElement("br"), s); } // e.g. Sarawak: part of the area has no palm data
    const ha = (n: number | undefined | null) => (n == null ? "–" : Math.round(n).toLocaleString() + " ha");
    const yr = Number(month.slice(0, 4));
    const peatOf = (r: string) => peatAgg?.series[r]?.peat_ha as number | undefined;
    $("d-peat").textContent = ha(peatOf(rid) ?? (rid === "indonesia" && peatAgg ? Object.keys(peatAgg.series).reduce((t, r) => t + (peatOf(r) ?? 0), 0) : undefined)); // national = sum of provinces
    const bi = burnAgg?.years ? burnAgg.years.indexOf(yr) : -1, mi = burnAgg?.months ? burnAgg.months.indexOf(month) : -1;
    $("d-burn-l").textContent = `Burned in ${yr}`; $("d-burnm-l").textContent = `Burned in ${label(month)}`;
    $("d-burn").textContent = bi >= 0 ? ha((burnAgg!.series[rid]?.burned_ha as number[] | undefined)?.[bi]) : "–";
    $("d-burnm").textContent = mi >= 0 ? ha((burnAgg!.series[rid]?.burned_ha_monthly as number[] | undefined)?.[mi]) : "–";
    const dy = tmfAgg?.years, dd = tmfAgg?.series[rid]?.deforested_ha as number[] | undefined; // first-deforestation hectares per year, 1990 bucket = 1984-1990
    $("d-tmf-l").textContent = `Forest cleared 1990 to ${yr}`;
    $("d-tmf").textContent = dy && dd ? ha(dd.filter((_, i) => dy[i] <= yr).reduce((s, v) => s + v, 0)) : "–";
    if (study.state !== "done") for (const id of ["d-loss", "d-palm", "d-peat", "d-burn", "d-burnm", "d-tmf"]) $(id).textContent = "…"; // yearly figures still on their way (loadStudy)
  }
  let studyLoad: Promise<void> | null = null;
  /** Loads the yearly and study aggregates once (see `study`); the Details card is redrawn when they are in. */
  const loadStudy = () => (studyLoad ??= (async () => {
    study.state = "loading";
    const [annual, peat, burn, tmf] = await Promise.all([manifest.files.annual ? getJSON<Annual>(manifest.files.annual).catch(() => null) : null, ...["peat", "burned-area", "tmf"].map((f) => getJSON<StudyAgg>(f + ".json").catch(() => null))]);
    Object.assign(study, { annual, peat, burn, tmf, state: "done" }); Object.assign(window, { __studyLoaded: true });
    drawDetails();
  })());

  if (!map) map = makeMap(hasView ? { center: [hv![0], hv![1]], zoom: hv![2] } : { bounds: (boundsFor(regionSel.value) ?? (multi ? unionBounds(multi.countries) : DEFAULT_BOUNDS)) as Bounds });
  else if (!hasView && first.root.fellBack) { const b = boundsFor(regionSel.value) ?? (multi ? unionBounds(multi.countries) : DEFAULT_BOUNDS); map.fitBounds(b as Bounds, { padding: fitPadding(), animate: false }); } // the map started from the manifest of the folder that then failed
  let fire: FireLayers | null = null; // fire detections as map layers (manifest.fire_layers): real per-month PMTiles; rows live in the layer list below
  const ff = manifest.fire_layers;
  if (ff) {
    fire = new FireLayers(map, ff.layers, dataBase, ff.ptsMinZoom);
    const real = ff.layers.filter((d) => !d.placeholder), dflt = real.filter((d) => !d.clearing); // clearing layers start off
    const want = H.f === undefined ? dflt.map((d) => d.id) : H.f.split(",");
    for (const d of real) if (want.includes(d.id)) fire.enabled.add(d.id);
    fire.onStatus = (id, t) => setStatus("fire-" + id, t);
    fire.onChange = () => paintMap();
    fire.onAdded = () => layers?.applyOrder();
    $("fire-legend").innerHTML = `<div class="legend"><span>0</span><i class="fl-m"></i><span>400+ fires / 100 km&sup2;</span></div><div class="legend"><span>0</span><i class="fl-v"></i><span>square-root scale, same every month; zoom 9+ shows single detections</span></div>`;
  } else $("fire-legend").hidden = true;
  let layers: ContextLayers | null = null;
  // layer panel state: which rows are on, their draw order, opacity and open catalogue groups; the link keys s o p g come from encodeState (src/layerpanel/state.ts)
  let panelSt: PanelState | null = null, panelDefs: Defaults | null = null;
  {
    layers = new ContextLayers(map, lf.layers, dataBase, lf.version); if (fire && lf.version) fire.version = lf.version;
    const NAME: Record<string, string> = { regions: "Provinces" }, COLOR: Record<string, string> = { regions: "var(--accent)" };
    const ROW_TEXT: Record<string, { name: string; hint?: string }> = { peat: { name: "Peatland", hint: "Swamp soil made of plant remains; burns underground when drained." }, palm: { name: "Oil palm (Descals)" } }; // row names (and one-line hint) only: layer ids, data and link keys stay; palm renamed in  because MapBiomas adds its own oil-palm row // visible name and one-line hint only; layer id, data and URL key stay "peat"
    const FIRE_LABEL: Record<string, string> = { modis: "MODIS", viirs: "VIIRS" }; // row names only: the group is already called "Fire detections"; ids, link keys and texts stay
    const ctys: Cty[] = multi?.countries ?? [], regName = (id: string) => names[id] ?? id;
    infos.set("regions", { name: NAME.regions, desc: "Colored by the selected month; click one to select it", real: true });
    const addInfo = (rid: string, name: string, desc: string, d: InfoDef & { note?: string }, extraDesc = "") => infos.set(rid, { name, desc, extraDesc, def: d, range: rangeText(d), real: !d.placeholder, cov: [...coverageNotes(d, ctys), ...regionGapNotes(d, regName)] });
    const store = $("lyr-store"), extras = new Map<string, HTMLElement>(); // per row: status line, gap note, class boxes (and for the colour overlay: the metric picker). The element lives in the row while the row is on, in the hidden store otherwise
    const clsHtml = (d: { id: string; classes?: { id: number; label: string; color: string }[] }) => (d.classes ? `<div class="cls-row">${d.classes.map((c) => `<label class="cls"><input type="checkbox" data-cls="${c.id}" data-row="${d.id}" checked><i style="background:${c.color}"></i>${c.label}</label>`).join("")}</div>` : "");
    /** layers with a variant picker (mode "variant"): a select under the row name and a colour legend that follows the choice */
    const varHtml = (d: { id: string; variants?: { id: string; label: string }[]; default_variant?: string }) => d.variants ? `<div class="var-row"><label for="var-${d.id}">Show</label><select id="var-${d.id}" data-var="${d.id}">${d.variants.map((v) => `<option value="${v.id}"${v.id === (d.default_variant ?? d.variants![0].id) ? " selected" : ""}>${v.label}</option>`).join("")}</select></div>` : "";
    const varDef = (id: string) => { const d = lf.layers.find((x) => x.id === id); return d?.variants?.find((v) => v.id === layers!.getVariant(id)); };
    const mkExtra = (rid: string, inner: string) => { const e = document.createElement("div"); e.className = "lyr on lp-extra"; e.id = "lyr-" + rid; e.innerHTML = `<span class="ls" id="ls-${rid}" aria-live="polite"></span><span class="gap" id="gap-${rid}" hidden></span>${inner}`; store.append(e); extras.set(rid, e); return e; };
    const fireClsHtml = (rid: string, d: FireDef) => !d.classes?.length ? "" : `<div class="cls-row">${d.classes.map((c) => `<label class="cls${c.disabled ? " dis" : ""}"${c.hint ? ` title="${esc(c.hint)}"` : ""}><input type="checkbox" data-cls="${c.id}" data-row="${rid}"${c.disabled ? ` disabled aria-disabled="true" aria-describedby="clsh-${rid}-${c.id}"` : " checked"}><i style="background:${d.color[2]}"></i>${esc(c.label)}</label>${c.hint ? `<span class="cls-hint" hidden id="clsh-${rid}-${c.id}">${esc(c.hint)}</span>` : ""}`).join("")}</div>`; // fire layer sub-selection: a disabled class is greyed, not tickable, with its hint beside it
    const catLayers: { id: string; name: string; color?: string; tag?: string; keywords?: string; disabled?: boolean }[] = [];
    mkExtra("regions", "");
    catLayers.push({ id: "regions", name: NAME.regions, color: COLOR.regions, keywords: "colour color metric province fire count overlay" });
    if (multi) { NAME.countries = "Countries"; COLOR.countries = "var(--accent)"; infos.set("countries", { name: "Countries", desc: "Each country coloured by its national total of the selected month, with its own metric picker. Click a country to select it. Provinces and Countries are shown one at a time.", real: true }); mkExtra("countries", ""); catLayers.push({ id: "countries", name: "Countries", color: COLOR.countries, keywords: "colour color metric country national fire count overlay" }); }
    for (const d of lf.layers) {
      if (HIDDEN_ROWS.includes(d.id) || REMOVED_ROWS.includes(d.id)) continue; // placeholder and removed rows are not listed (data files untouched)
      const [n0, ...r0] = d.legend.split(" — "); const name = ROW_TEXT[d.id]?.name ?? d.title ?? n0, rest = d.title ? [d.legend] : r0; NAME[d.id] = name; COLOR[d.id] = d.color;
      const desc = rest.join(" — "); addInfo(d.id, name, desc, d, d.variants ? d.long ?? "" : "");
      mkExtra(d.id, clsHtml(d) + varHtml(d)); catLayers.push({ id: d.id, name, color: d.color, keywords: `${d.title ?? ""} ${d.legend}` });
    }
    layers.registerGroup("countries", (id) => id === "regions-country");
    layers.registerGroup("regions", (id) => id === "regions" || (id.startsWith("regions-") && id !== "regions-country"));
    layers.registerGroup("borders", (id) => id.startsWith("borders-")); // not in the list: stays above every row (fire, regions, context layers), below the basemap labels, so a thin border is never hidden by the colored cells
    const fireIds: string[] = [];
    for (const d of ff?.layers ?? []) { // fire rows (row id "fire-<id>")
      const rid = "fire-" + d.id, lab = FIRE_LABEL[d.id] ?? d.label; fireIds.push(rid); NAME[rid] = lab; COLOR[rid] = d.color[2]; addInfo(rid, lab, d.legend, d, d.note ?? "");
      layers.registerGroup(rid, (id) => id.startsWith(`fire-${d.id}-`) || id.startsWith(`fire-${d.id}_`)); // the layer and its classes (day / night: "fire-modis_1-…")
      mkExtra(rid, fireClsHtml(rid, d)); catLayers.push({ id: rid, name: lab, color: d.color[2], keywords: d.legend, ...(d.placeholder ? { disabled: true } : {}) });
      if (d.placeholder) setStatus(rid, "Slot for the model's gridded output; nothing drawn");
    }
    const rowIds = [...fireIds, ...layers.defaultOrder(["regions"])].flatMap((i) => (i === "regions" && multi ? ["regions", "countries"] : [i])).filter((i) => !HIDDEN_ROWS.includes(i) && !REMOVED_ROWS.includes(i)); // top first: fire, then other new layers, regions, context layers
    const fireDefault = (ff?.layers ?? []).filter((d) => !d.placeholder && !d.clearing).map((d) => "fire-" + d.id); // clearing layers start off
    panelDefs = { order: rowIds, active: [...fireDefault, "regions"], open: DEFAULT_OPEN, keepInLegacy: ["regions"] };
    let st = decodeState(H, panelDefs).state;
    if (H.rg === "0" && H.s === undefined) st = setActive(st, "regions", false); // a part-1 link (rg=0) has no s key
    const oneLevel = (x: PanelState, id: string, on: boolean): PanelState => (on && (id === "regions" || id === "countries") ? setActive(x, id === "regions" ? "countries" : "regions", false) : x); // Provinces and Countries are shown one at a time (the upper one would hide the other)
    if (st.active.has("regions") && st.active.has("countries")) st = setActive(st, "countries", false);
    panelSt = st;
    // the metric picker (the existing <select id="metric">, moved, not re-created) and its colour ramp live in the colour overlay's extra
    const rx = extras.get("regions")!; rx.insertAdjacentHTML("beforeend", `<div class="metric-box" id="metric-box"></div>`);
    const mbox = $("metric-box"); mbox.append($("metric-holder").firstElementChild!);
    if (extras.has("countries")) { extras.get("countries")!.insertAdjacentHTML("beforeend", `<div class="metric-box" id="metric-box-c"><label class="field"><span>Metric</span></label></div>`); $("metric-box-c").firstElementChild!.append(countrySel); }

    // ---- panel components
    const pop = new InfoPopover(), on = new OnTheMapList($("onmap"), { emptyText: "No layer is on. Tick one in the list below." });
    const cat = new LayerCatalogue($("layers"), { groups: GROUPS, layers: catLayers, open: st.open, search: true });
    const hasExtra = (id: string) => id === "regions" || id === "countries" || !!extras.get(id)!.querySelector(".cls-row, .var-row"); // a row shows controls only; every sentence is in its (i) panel
    refreshExtra = (id) => extras.get(id)?.classList.toggle("empty", !hasExtra(id));
    const renderOn = () => {
      on.setItems(activeOrder(st).map((id) => ({ id, name: NAME[id], color: COLOR[id], picker: extras.get(id)! })));
      for (const [id, e] of extras) { if (!st.active.has(id)) store.append(e); refreshExtra(id); }
      cat.setActive(st.active); naSet.forEach(applyNa); for (const id of rowIds) applyImp(id);
      $("reset-order").hidden = st.order.join() === rowIds.join();
    };
    const applyOpacity = (id: string, v: number) => { if (id === "regions") { regionsOp = v; paintMap(); } else if (id === "countries") { countryOp = v; paintMap(); } else if (id.startsWith("fire-")) fire!.setOpacity(id.slice(5), v); else layers!.setOpacity(id, v); };
    /** Pushes the panel state to the map: layers on/off, draw order, opacity. */
    const apply = () => {
      for (const id of rowIds) {
        const want = st.active.has(id);
        if (id === "regions") { if (regionsOn !== want) setRegionsOn(want); }
        else if (id === "countries") { if (countryOn !== want) setCountryOn(want); }
        else if (id.startsWith("fire-")) { if (fire!.enabled.has(id.slice(5)) !== want) fire!.toggle(id.slice(5), want); }
        else if (layers!.enabled.has(id) !== want) layers!.toggle(id, want);
        applyOpacity(id, opacityOf(st, id));
      }
      layers!.setOrder([...st.order]);
    };
    const commit = () => { renderOn(); apply(); writeHash(); };
    const monthText = (id: string) => { const n = now.get(id), t = [n?.status, n?.gap].filter(Boolean).join(" \u00b7 "); return st.active.has(id) ? t || "Drawn normally." : "Not on the map right now."; };
    const infoFor = (id: string): InfoContent => {
      const i = infos.get(id)!, d = i.def, vd = d && "variants" in d ? varDef(id) : undefined; // a row with a picker: the legend shows the swatches of the chosen variant
      const fd = id.startsWith("fire-") ? ff?.layers.find((x) => "fire-" + x.id === id) : undefined, hints = (fd?.classes ?? []).filter((c) => c.hint).map((c) => `${c.label}: ${c.hint}.`).join(" ");
      const cov = [i.range ? `Dates: ${i.range}.` : "", ...(i.cov ?? []), vd ? "" : i.extraDesc].filter(Boolean).join(" ");
      const src = [d?.source ? `Source: ${d.source}.` : "", d?.licence ? `Licence: ${d.licence}.` : ""].filter(Boolean).join(" ");
      const how = vd ? i.extraDesc : d?.long ?? "";
      const sections = [{ title: "What it shows", text: [ROW_TEXT[id]?.hint, i.desc, vd ? `Showing: ${vd.text}.` : ""].filter(Boolean).join(" ") }, { title: "Click", text: id === "regions" || id === "countries" ? "A click on the map selects what the ticked row shows: a province with Provinces, a country with Countries. With both rows off a click selects the country on a wide view and the province from zoom 5 on (a view of one large region such as Central Kalimantan). The outline under the pointer shows what the click will select." : "" }, { title: "Coverage", text: cov }, { key: "month", title: "This month", text: i.real ? monthText(id) : "" },
        { title: "Options", text: hints }, { title: "How to read it", text: id === "countries" ? "Darkest = the highest national monthly count of any country in the data for the chosen metric (square-root scale). This scale is separate from the Provinces scale, because a country adds up all its provinces." : how }, { title: "Source and licence", text: src } ].filter((x): x is { key?: string; title: string; text: string } => !!x.text);
      const ramp = id === "regions" || id === "countries" ? Object.assign(document.createElement("div"), { className: "legend", innerHTML: "<span>fewer</span><i></i><span>more detections</span>" }) : undefined; // colour ramp of the overlay
      return { id, title: i.name, important: importantOf(id), legend: vd?.legend, sections, node: ramp, opacity: i.real ? opacityOf(st, id) : false };
    };
    /** must-know sentences of a layer: its `important` key (layers.json / manifest), the coverage chip (Indonesia only, no data here), a placeholder note, and a problem status for the selected month */
    const importantOf = (id: string): string[] => {
      const d = infos.get(id)?.def, n = now.get(id), out: string[] = [...[d?.important ?? []].flat()];
      const c = impChip.get(id); if (c) out.push(c);
      if (infos.get(id) && !infos.get(id)!.real) out.push("Placeholder: synthetic stand-in, not real data.");
      if (n && st.active.has(id) && isProblem(n.status)) out.push(/[.!?]$/.test(n.status) ? n.status : n.status + ".");
      return [...new Set(out)];
    };
    const applyImp = (id: string) => { const imp = importantOf(id).length > 0, nm = NAME[id] ?? id; document.querySelectorAll(`#onmap .lp-row[data-id="${id}"], #layers .lp-crow[data-id="${id}"]`).forEach((e) => { e.classList.toggle("lp-imp", imp); e.querySelector(".lp-info")?.setAttribute("aria-label", imp ? `About ${nm}: important information` : `About ${nm}`); }); };
    impRefresh = (id) => { if (!infos.has(id) || !NAME[id]) return; applyImp(id); pop.setImportant(id, importantOf(id)); };
    popRefresh = (rid) => pop.updateSection(rid, "month", monthText(rid));
    // a layer with nothing for this month: its name and swatch are dimmed and its (i) button carries a dot; the reason is in the (i) panel under "This month"
    const naSet = new Set<string>(), applyNa = (id: string) => document.querySelectorAll(`#onmap .lp-row[data-id="${id}"], #layers .lp-crow[data-id="${id}"]`).forEach((e) => e.classList.toggle("lp-na", naSet.has(id)));
    markNa = (id, na) => { if (na) naSet.add(id); else naSet.delete(id); applyNa(id); };
    const secInfo = (): InfoContent => ({ id: "section", title: "About these layers", opacity: false,
      description: "Every layer here is real data unless its row carries a chip (for example placeholder, a stand-in with synthetic tiles). The first layer under On the map draws on top: drag its handle to reorder, or focus the handle, press Space, move with the Up and Down arrows, and press Space again to drop. Reset order appears once you change it.",
      note: manifest.sources ? `Sources. ${manifest.sources}` : undefined });
    pop.on("opacity-change", ({ id, value }) => { st = setOpacity(st, id, value); panelSt = st; applyOpacity(id, value); writeHash(); });
    on.on("info", ({ id, trigger }) => pop.toggle(trigger, infoFor(id))); cat.on("info", ({ id, trigger }) => pop.toggle(trigger, infoFor(id)));
    $("sec-info").addEventListener("click", (e) => pop.toggle(e.currentTarget as HTMLElement, secInfo()));
    on.on("order-change", ({ order }) => { st = applyActiveOrder(st, order); panelSt = st; commit(); });
    on.on("off", ({ id }) => { if (pop.openId === id) pop.close(false); st = setActive(st, id, false); panelSt = st; commit(); });
    cat.on("toggle", ({ id, on: v }) => {
      st = oneLevel(setActive(st, id, v), id, v); if (v) st = applyActiveOrder(st, [id, ...activeOrder(st).filter((i) => i !== id)]); // a layer you switch on goes to the top of the list (and draws on top)
      if (!v && pop.openId === id) pop.close(false);
      panelSt = st; commit();
    });
    cat.on("open-change", ({ open }) => { st = setOpenGroups(st, open); panelSt = st; writeHash(); });
    $("reset-order").addEventListener("click", () => { st = { ...st, order: [...rowIds] }; panelSt = st; commit(); });
    // class switches (x=) per layer: boxes live in the layer's extra
    const setCls = (row: string, cls: number, on: boolean) => { if (row.startsWith("fire-")) fire!.setClass(row.slice(5), cls, on); else layers!.setClass(row, cls, on); }; // class boxes of a context layer or of a fire layer (day / night)
    document.querySelectorAll<HTMLInputElement>("input[type=checkbox][data-cls]").forEach((el) => el.addEventListener("change", () => { setCls(el.dataset.row!, Number(el.dataset.cls), el.checked); writeHash(); }));
    syncBoxes = () => { // a fire layer with per-class tiles (MODIS / VIIRS day and night): the boxes work in the months that have the tiles; in any other month they are greyed and ticked (everything is drawn), so the row never changes shape while the slider plays. Your choice is kept and comes back.
      for (const d of ff?.layers ?? []) { const split = splitMonth(d, month), rid = "fire-" + d.id;
        for (const c of tiledClasses(d)) { const el = document.querySelector<HTMLInputElement>(`input[data-cls="${c.id}"][data-row="${rid}"]`); if (!el) continue; el.disabled = !split; el.toggleAttribute("aria-disabled", !split); if (split) el.removeAttribute("aria-disabled"); el.checked = split ? fire!.classOn(d.id, c.id) : true; el.closest("label")?.classList.toggle("dis", !split); } }
    };
    const classOk = (row: string, cls: number) => !!lf.layers.find((d) => d.id === row)?.classes?.some((c) => c.id === cls) || !!ff?.layers.find((d) => "fire-" + d.id === row && classEditable(d, cls)); // a disabled fire class can never be switched through the link
    for (const [row, cs] of Object.entries(parseOff(H.x, classOk))) for (const c of cs) { const el = document.querySelector<HTMLInputElement>(`#lyr-store input[data-cls="${c}"][data-row="${row}"]`); if (el) { el.checked = false; setCls(row, c, false); } }
    // variant pickers: the select swaps the file shown; the legend in the (i) panel follows; the choice is in the link (vr=)
    const varOk = (row: string, v: string) => !!lf.layers.find((d) => d.id === row)?.variants?.some((x) => x.id === v);
    for (const [row, v] of Object.entries(parseVariants(H.vr, varOk))) layers.setVariant(row, v);
    document.querySelectorAll<HTMLSelectElement>("select[data-var]").forEach((sel) => {
      const id = sel.dataset.var!; sel.value = layers!.getVariant(id);
      sel.addEventListener("change", () => { layers!.setVariant(id, sel.value); writeHash(); });
    });
    layers.onStatus = (id, t) => setStatus(id, t);
    layers.onChange = () => paintMap();
    regionsOn = st.active.has("regions"); regionsOp = opacityOf(st, "regions"); countryOn = st.active.has("countries"); countryOp = opacityOf(st, "countries");
    renderOn(); apply();
    Object.assign(window, { __panel: () => panelSt }); // read by scripts/check_share39.py (like __map)
  }
  // "no data for this layer in <country>": only layers whose def lists `coverage` can show it (none do while the data is Indonesia-only)
  const gapDefs: [string, { coverage?: string[]; gap_note?: string; region_gaps?: Record<string, string> }][] = [...(lf?.layers ?? []).map((d) => [d.id, d] as [string, typeof d]), ...(ff?.layers ?? []).map((d) => ["fire-" + d.id, d] as [string, typeof d])];
  const countryByRegion = new Map(regions.features.map((f) => [f.properties.id, countryOf(f.properties)]));
  function refreshGaps() {
    const rid = regionSel.value, cc = multi ? (rid === multi.all?.id ? undefined : cOfId(rid)) : countryByRegion.get(rid) ?? countryOf(); // "all countries" has no single country: no country-level note
    const ccs: Cty[] = multi?.countries ?? [];
    for (const [id, d] of gapDefs) {
      const e = document.getElementById("gap-" + id); if (!e) continue;
      const rg = regionGap(d, rid), t = (cc ? gapNote(d, cc) : "") || rg; e.textContent = t; e.hidden = !t;
      const ch = chipFor(d as InfoDef, ccs, cc, rg); // coverage chip: no longer drawn on the row; its sentence is a must-know line in the (i) panel
      impChip.set(id, ch && ch.kind !== "ph" ? (ch.kind === "gap" && t ? t : ch.text.charAt(0).toUpperCase() + ch.text.slice(1) + ".") : "");
      now.set(id, { status: now.get(id)?.status ?? "", gap: t }); popRefresh(id); refreshExtra(id); impRefresh(id);
    }
  }
  let curStyle = isDark() ? "dark" : "light";
  /** outline of the selection: one region by id; a national total = all regions of that country; the all-countries total = none */
  function selFilter(): maplibregl.FilterSpecification {
    const rid = regionSel.value, cc = multi && multi.countries.find((c) => c.total === rid)?.code;
    if (cc) return ["==", ["get", "country"], cc];
    return ["==", ["get", "id"], multi?.all?.id === rid ? "" : rid];
  }

  // map type: satellite imagery from NASA GIBS under our layers; plain map is the default and is not in the link
  const bm = new Basemap(map), baseSel = $<HTMLSelectElement>("basemap"), baseNote = $("base-note");
  bm.mode = parseBase(H.b); baseSel.value = bm.mode; baseNote.textContent = NOTE[bm.mode];
  const lineCol = () => (bm.mode === "sat" ? SAT_LINE : isDark() ? "#c3c8d0" : "#4b5260");
  const selCol = () => (bm.mode === "sat" ? SAT_LINE : getComputedStyle(document.documentElement).getPropertyValue("--fg").trim() || "#000");
  function recolor() { // borders and selection outlines: light on imagery, the original colours on the plain map
    for (const l of ["borders-minor", "borders-major", "borders-sel-interior"]) if (map.getLayer(l)) map.setPaintProperty(l, "line-color", lineCol());
    for (const l of ["regions-sel", "borders-sel-outline"]) if (map.getLayer(l)) map.setPaintProperty(l, "line-color", selCol());
  }
  const ctyMaxCache = new Map<string, number>();
  const ctyMax = (k: string) => { if (!ctyMaxCache.has(k)) { let m = 1; for (const c of multi?.countries ?? []) for (const v of monthly.series[c.total]?.[k] ?? []) if (v != null && v > m) m = v; ctyMaxCache.set(k, m); } return ctyMaxCache.get(k)!; };
  function paintMap() {
    if (!map.getLayer("regions")) return;
    const mx = maxAll();
    const expr: unknown[] = ["match", ["get", "id"]];
    for (const rid of ids) { const t = norm(val(rid, month), mx); expr.push(rid, t < 0 ? "#888" : heat(t)); }
    expr.push("#888");
    map.setPaintProperty("regions", "fill-color", expr as maplibregl.ExpressionSpecification);
    // row off (rg=0): no colour is drawn, but the fill stays in the style at opacity 0 so a click still selects a province; selection outline and borders stay (they are not the overlay)
    map.setPaintProperty("regions", "fill-opacity", !regionsOn ? 0 : regionsOp * (layers?.anyOn || fire?.anyOn ? 0.3 : bm.mode === "sat" ? 0.45 : 0.7));
    if (map.getLayer("regions-country")) { // Countries overlay: each province polygon takes the colour of its country's national series; scale per level (the highest national monthly count of the data = darkest)
      const k = countrySel.value, cx = ctyMax(k), ce: unknown[] = ["match", ["get", "country"]];
      for (const c of multi?.countries ?? []) { const t = norm(val(c.total, month, k), cx); ce.push(c.code, t < 0 ? "#888" : heat(t)); }
      ce.push("#888");
      map.setPaintProperty("regions-country", "fill-color", ce as maplibregl.ExpressionSpecification);
      map.setPaintProperty("regions-country", "fill-opacity", !countryOn ? 0 : countryOp * (layers?.anyOn || fire?.anyOn ? 0.3 : bm.mode === "sat" ? 0.45 : 0.7));
    }
    for (const l of ["regions-sel", "borders-sel-outline"]) if (map.getLayer(l)) map.setPaintProperty(l, "line-dasharray", est(ids[0], month) ? [2, 2] : [1, 0]); // dashed outline of the selection = estimated month (the borders themselves are always solid)
  }
  /** The metric colour overlay row: the layer panel switches it. */
  function setRegionsOn(on: boolean) {
    regionsOn = on; paintMap(); drawDetails(); resetHover();
  }
  function setCountryOn(on: boolean) { countryOn = on; paintMap(); drawDetails(); resetHover(); }
  /** Two border levels, solid and neutral grey, drawn from borders.geojson (edges shared by two regions only: no coast line). major = international,
   *  minor = province. Quiet at the whole-region view, stronger as you zoom in. Loaded after the map is up; a missing file just means no border lines. The polygon layers keep hit-testing, fill and selection. */
  let bordersData: unknown = null;
  function addBorders() {
    if (!bordersData || map.getSource("borders") || !map.getSource("regions")) return;
    const col = lineCol();
    map.addSource("borders", { type: "geojson", data: bordersData as string });
    const z = (...a: number[]) => ["interpolate", ["linear"], ["zoom"], ...a] as unknown as maplibregl.ExpressionSpecification;
    map.addLayer({ id: "borders-minor", type: "line", source: "borders", filter: ["==", ["get", "l"], "minor"], layout: { "line-join": "round" },
      paint: { "line-color": col, "line-width": z(3, 0.3, 6, 0.6, 9, 1), "line-opacity": z(3, 0.04, 5, 0.2, 7, 0.45, 9, 0.6) } }, map.getLayer("regions-sel") ? "regions-sel" : undefined);
    map.addLayer({ id: "borders-major", type: "line", source: "borders", filter: ["==", ["get", "l"], "major"], layout: { "line-join": "round" },
      paint: { "line-color": col, "line-width": z(3, 0.9, 6, 1.3, 9, 1.9), "line-opacity": z(3, 0.65, 6, 0.8, 9, 0.9) } }, map.getLayer("regions-sel") ? "regions-sel" : undefined);
    map.addLayer({ id: "borders-sel-interior", type: "line", source: "borders", filter: NONE_C, layout: { "line-join": "round" }, // province lines of the selected country: a little stronger than the rest
      paint: { "line-color": col, "line-width": z(3, 0.5, 6, 0.9, 9, 1.3), "line-opacity": z(3, 0.3, 6, 0.6, 9, 0.8) } }, map.getLayer("regions-sel") ? "regions-sel" : undefined);
    addOutlines();
    layers?.applyOrder(); applySel();
  }
  const NONE_C: maplibregl.FilterSpecification = ["==", ["get", "c"], ""], NONE_ID: maplibregl.FilterSpecification = ["==", ["get", "id"], ""];
  const hoverCol = () => (bm.mode === "sat" ? "#ffd54f" : getComputedStyle(document.documentElement).getPropertyValue("--accent").trim() || "#b8400a");
  /** Selecting a whole country outlines only its outer edge (coast + international border, from country-outlines.geojson, fetched the first time a country is selected);
   *  until that file is here, or if it fails, the old outline (every province in heavy black) is used so the selection is always visible. */
  let outlinesData: unknown = null, outlinesAsked = false;
  const selCountry = (): string | undefined => { const rid = regionSel.value; return multi?.countries.find((c) => c.total === rid)?.code; };
  function addOutlines() {
    if (!outlinesData || map.getSource("country-outlines") || !map.getSource("regions")) return;
    map.addSource("country-outlines", { type: "geojson", data: outlinesData as string });
    map.addLayer({ id: "borders-sel-outline", type: "line", source: "country-outlines", filter: NONE_C, layout: { "line-join": "round", "line-cap": "round" },
      paint: { "line-color": selCol(), "line-width": 3 } });
    map.addLayer({ id: "borders-hover-c", type: "line", source: "country-outlines", filter: NONE_C, layout: { "line-join": "round", "line-cap": "round" }, paint: { "line-color": hoverCol(), "line-width": 2.5, "line-opacity": 0.95 } }); // click preview: the country a click would select
  }
  function applySel() {
    const cc = selCountry(), outline = !!map.getLayer("borders-sel-outline");
    if (map.getLayer("regions-sel")) map.setFilter("regions-sel", cc && outline ? ["==", ["get", "id"], ""] : selFilter());
    if (outline) map.setFilter("borders-sel-outline", cc ? ["==", ["get", "c"], cc] : NONE_C);
    if (map.getLayer("borders-sel-interior")) map.setFilter("borders-sel-interior", cc ? ["all", ["==", ["get", "l"], "minor"], ["==", ["get", "c"], cc]] : NONE_C);
    if (cc) askOutlines();
  }
  function askOutlines() { // country outlines (coast + international border): fetched the first time a country is selected or hovered
    if (outlinesData || outlinesAsked || !manifest.files.outlines) return;
    outlinesAsked = true;
    fetchT(dataBase + manifest.files.outlines, { cache: "no-cache" }).then(async (r) => { if (!r.ok) return; outlinesData = await r.json(); addOutlines(); layers?.applyOrder(); applySel(); paintMap(); }).catch(() => { outlinesAsked = false; });
  }
  async function loadBorders() {
    const f = manifest.files.borders; if (!f) return;
    try { const r = await fetchT(dataBase + f, { cache: "no-cache" }); if (!r.ok) return; bordersData = await r.json(); addBorders(); } catch { /* no border lines, the rest of the map is unaffected */ }
  }
  const onStyle = () => { // runs on first load and after every setStyle (theme switch)
    if (map.getSource("regions")) return;
    bm.snapshot();
    map.addSource("regions", { type: "geojson", data: regions });
    map.addLayer({ id: "regions", type: "fill", source: "regions", paint: { "fill-color": "#888", "fill-opacity": 0.7 } });
    if (multi) map.addLayer({ id: "regions-country", type: "fill", source: "regions", paint: { "fill-color": "#888", "fill-opacity": 0, "fill-antialias": false } }); // Countries overlay: the province polygons, coloured by country
    addBorders();
    map.addLayer({ id: "regions-sel", type: "line", source: "regions", filter: selFilter(), paint: { "line-color": selCol(), "line-width": 3 } });
    map.addLayer({ id: "borders-hover-r", type: "line", source: "regions", filter: NONE_ID, paint: { "line-color": hoverCol(), "line-width": 2.5, "line-opacity": 0.95 } }); // click preview: the province (or, before the country outlines are in, the provinces of the country) a click would select
    paintMap(); applySel();
    layers?.reset(); fire?.reset();
    bm.apply(); recolor();
  };
  map.on("style.load", onStyle);
  if (map.getStyle()) onStyle(); // style may have finished while layers.json was loading; isStyleLoaded() is false while basemap tiles still load, which left regions and layers unattached (race)
  const minesHit = attachMinePopup(map, "ctx-mines-s", (cc) => multi?.countries.find((c) => c.code === cc)?.name ?? cc);
  // What a click on an area selects: the Countries row on = the country, the Provinces row on = the province; both rows off = by zoom, the country on a wide view and the province from zoom 5 on
  // (first 6, moved one level out on Joshua's order: the large Kalimantan provinces fill the screen at zoom 5 to 6 and must already select as provinces; the whole of Indonesia is zoom ~4 and still selects the country). Hysteresis of 0.3 so the target does not flip while a pinch passes the boundary.
  const Z_PROVINCE = 5, Z_HYST = 0.3;
  let zoomLevel: "country" | "region" = map.getZoom() >= Z_PROVINCE ? "region" : "country";
  const clickLevel = (): "country" | "region" => (!multi ? "region" : countryOn ? "country" : regionsOn ? "region" : zoomLevel);
  let hoverKey = "";
  const setHover = (f?: { id?: string; country?: string }) => { // outline of what a click would select; the same outline style on every level, no text
    const lvl = clickLevel(), key = f ? (lvl === "country" ? "c:" + f.country : "r:" + f.id) : "", hasOut = !!map.getLayer("borders-hover-c");
    if (key === hoverKey) return; hoverKey = key;
    if (map.getLayer("borders-hover-r")) map.setFilter("borders-hover-r", !f ? NONE_ID : lvl === "country" ? (hasOut ? NONE_ID : ["==", ["get", "country"], f.country ?? ""]) : ["==", ["get", "id"], f.id ?? ""]);
    if (hasOut) map.setFilter("borders-hover-c", f && lvl === "country" ? ["==", ["get", "c"], f.country ?? ""] : NONE_C);
    if (f && lvl === "country") askOutlines();
  };
  resetHover = () => { hoverKey = ""; setHover(); };
  map.on("zoom", () => { const z = map.getZoom(), was = zoomLevel; if (zoomLevel === "country" && z >= Z_PROVINCE + Z_HYST) zoomLevel = "region"; else if (zoomLevel === "region" && z < Z_PROVINCE - Z_HYST) zoomLevel = "country"; if (was !== zoomLevel) resetHover(); });
  Object.assign(window, { __clickLevel: clickLevel });
  map.on("mousemove", "regions", (e) => setHover(e.features?.[0]?.properties as { id?: string; country?: string } | undefined));
  map.on("mouseleave", "regions", resetHover);
  map.on("click", "regions", (e) => {
    if (minesHit(e.point)) return; // a click on a mine outline opens the mine pop-up, it does not select the area under it
    const f = e.features?.[0]?.properties; const id = f?.id as string | undefined; if (!id) return;
    if (clickLevel() === "country") { // like the Country picker: selects the country (and moves the map to it)
      const cc = f?.country as string | undefined; if (!cc || !cSel || !cDef(cc)) return;
      cSel.value = cc; cSel.dispatchEvent(new Event("change")); setTab("details", true); resetHover(); return;
    }
    const cc = multi ? cOfId(id) : undefined;
    if (multi && cc && cc !== country && country !== "all") { country = cc; fillRegions(); if (cSel) cSel.value = country; } // clicked a region of another country: follow it (no fly)
    regionSel.value = id; refresh(); setTab("details", true); resetHover();
  });
  map.on("mouseenter", "regions", () => (map.getCanvas().style.cursor = "pointer"));
  map.on("mouseleave", "regions", () => (map.getCanvas().style.cursor = ""));

  function refresh() {
    const want = isDark() ? "dark" : "light";
    if (want !== curStyle) { curStyle = want; map.setStyle(STYLES[want]); } // style.load repaints
    drawCalendar(); drawDetails(); refreshGaps(); paintMap(); syncSel();
    applySel();
    slider.value = String(monthly.months.indexOf(month)); $("slv").textContent = label(month); slider.setAttribute("aria-valuetext", label(month)); const hidE = metricSel.value === "viirs_eq" && hiddenEstimate(monthly.series[regionSel.value], "viirs_eq", monthly.months.indexOf(month));
    $("tl-est").hidden = !est(ids[0], month); $("tl-est").textContent = hidE ? "estimate not reliable here" : "estimated";
    layers?.setMonth(month); fire?.setMonth(month); syncBoxes(); writeHash();
  }
  // phone: the three selectors fold into one summary line ("Indonesia (national) · VIIRS-equivalent"); wider screens keep them open
  const sel = $<HTMLDetailsElement>("sel"), selTxt = $("sel-txt");
  const syncSel = () => { selTxt.textContent = optText(regionSel); };
  const openSel = () => { sel.open = !isDockLayout(); };
  openSel(); matchMedia(DOCK_QUERY).addEventListener("change", openSel);
  // Details sections: phone = Fires and Forest-loss fires open, Land and Data notes folded; wider screens: all open
  const openSecs = () => { for (const id of ["ds-land", "ds-notes"]) $<HTMLDetailsElement>(id).open = !isDockLayout(); };
  openSecs(); matchMedia(DOCK_QUERY).addEventListener("change", openSecs);
  for (const e of [metricSel, regionSel]) e.addEventListener("change", syncSel);
  syncSel();
  const slider = $<HTMLInputElement>("slider");
  slider.max = String(monthly.months.length - 1);
  $("ticks").innerHTML = years.filter((y) => Number(y) % 5 === 0).map((y) => `<span style="left:${(monthly.months.indexOf(y + "-01") / (monthly.months.length - 1)) * 100}%">${y}</span>`).join("");
  slider.addEventListener("input", () => { month = monthly.months[Number(slider.value)]; refresh(); });
  metricSel.addEventListener("change", refresh);
  countrySel.addEventListener("change", () => { paintMap(); drawDetails(); writeHash(); });
  regionSel.addEventListener("change", () => { // choosing a region moves the map to it; clicking one on the map does not
    const b = boundsFor(regionSel.value);
    if (b) map.fitBounds(b, { padding: fitPadding(), maxZoom: 10, duration: reduce.matches ? 0 : 1200 });
    refresh();
  });
  const cSel = document.getElementById("country") as HTMLSelectElement | null;
  if (multi && cSel) { // country selector: fly to the country, list only its regions, show its national series
    $("country-field").hidden = false;
    cSel.innerHTML = (multi.all ? `<option value="all">${multi.all.name}</option>` : "") + multi.countries.map((c) => `<option value="${c.code}">${c.name}</option>`).join("");
    cSel.value = country;
    cSel.addEventListener("change", () => {
      country = cSel.value; fillRegions(); regionSel.value = country === "all" ? multi.all!.id : cDef(country)!.total;
      const b = country === "all" ? unionBounds(multi.countries) : boundsOf(cDef(country)!);
      map.fitBounds(b, { padding: fitPadding(), maxZoom: 9, duration: reduce.matches ? 0 : 1200 });
      refresh();
    });
  }

  // play / pause: one month per 500 ms, loops at the end. Started by the user, so it also works under prefers-reduced-motion (WCAG 2.2.2); the map has no easing between months
  const play = $<HTMLButtonElement>("play"), reduce = matchMedia("(prefers-reduced-motion: reduce)");
  let timer = 0;
  const setPlaying = (on: boolean) => {
    clearInterval(timer); timer = 0;
    if (on) timer = window.setInterval(() => {
      const i = monthly.months.indexOf(month) + 1;
      month = monthly.months[i >= monthly.months.length ? 0 : i]; refresh();
    }, 500);
    play.setAttribute("aria-pressed", String(!!timer)); play.setAttribute("aria-label", timer ? "Pause" : "Play months");
    play.innerHTML = `<span aria-hidden="true">${timer ? "&#10074;&#10074;" : "&#9654;"}</span>`;
  };
  play.addEventListener("click", () => setPlaying(!timer));
  document.addEventListener("keydown", (e) => {
    const t = e.target as HTMLElement;
    if (e.altKey || e.ctrlKey || e.metaKey || t.closest("select,button,a,textarea") || (t instanceof HTMLInputElement && t.type !== "range")) return;
    if (e.key === " " && !play.disabled) { e.preventDefault(); setPlaying(!timer); }
    else if ((e.key === "ArrowLeft" || e.key === "ArrowRight") && t !== slider && !t.classList.contains("maplibregl-canvas")) {
      const i = monthly.months.indexOf(month) + (e.key === "ArrowRight" ? 1 : -1);
      if (i >= 0 && i < monthly.months.length) { e.preventDefault(); month = monthly.months[i]; refresh(); }
    }
  });

  // panels: collapse on desktop, bottom sheet with tabs on phones
  const dock = $("dock"), phone = matchMedia(DOCK_QUERY);
  document.querySelectorAll<HTMLButtonElement>(".collapse").forEach((b) => b.addEventListener("click", () => {
    const p = $(b.dataset.for!), c = p.toggleAttribute("data-collapsed");
    b.setAttribute("aria-expanded", String(!c)); b.textContent = c ? "Show" : "Hide"; measure();
  }));
  const drawer = $("drawer"), calbtn = $("calbtn");
  const setDrawer = (open: boolean) => { drawer.dataset.open = open ? "1" : "0"; calbtn.setAttribute("aria-expanded", String(open)); };
  setDrawer(!phone.matches && innerHeight >= 820);
  calbtn.addEventListener("click", () => setDrawer(drawer.dataset.open !== "1"));
  const setTab = (tab: string, open: boolean) => {
    dock.dataset.tab = tab; dock.dataset.open = open ? "1" : "0"; if (tab === "details" && open) void loadStudy(); writeHash();
    dock.querySelectorAll<HTMLElement>("[role=tab]").forEach((t) => t.setAttribute("aria-selected", String(t.dataset.tab === tab && open)));
  };
  setTab(parseTab(H.t) ?? "timeline", true); // t= from the link
  dock.querySelectorAll<HTMLElement>("[role=tab]").forEach((t) => t.addEventListener("click", () => setTab(t.dataset.tab!, !(dock.dataset.tab === t.dataset.tab && dock.dataset.open === "1"))));
  const grab = $("grab");
  let y0 = 0, dy = 0, drag = false;
  grab.addEventListener("pointerdown", (e) => { drag = true; y0 = e.clientY; dy = 0; grab.setPointerCapture(e.pointerId); });
  grab.addEventListener("pointermove", (e) => { if (drag) dy = e.clientY - y0; });
  grab.addEventListener("pointerup", () => {
    if (!drag) return; drag = false;
    setTab(dock.dataset.tab!, Math.abs(dy) < 8 ? dock.dataset.open !== "1" : dy < 0);
  });
  grab.addEventListener("keydown", (e) => { if (e.key === "ArrowUp") setTab(dock.dataset.tab!, true); if (e.key === "ArrowDown") setTab(dock.dataset.tab!, false); });
  document.querySelector<HTMLAnchorElement>("a.skip")?.addEventListener("click", (e) => { e.preventDefault(); [...dock.querySelectorAll<HTMLElement>("button, select, input")].find((x) => x.offsetParent !== null)?.focus(); }); // focus the first visible control (on desktop #dock has no box of its own) without touching the #m=...&r=... link state
  const menu = $("menu"), nav = $("nav");
  menu.addEventListener("click", () => { const o = nav.toggleAttribute("data-open"); menu.setAttribute("aria-expanded", String(o)); });

  // keep map controls + attribution above whatever sits at the bottom
  const measure = () => {
    const root = document.documentElement.style;
    if (isSideLayout()) { root.setProperty("--bottom-h", "0px"); root.setProperty("--side-w", Math.ceil(dock.getBoundingClientRect().right) + "px"); return; } // side sheet: the map controls move right of it
    root.setProperty("--side-w", "0px");
    const el = phone.matches ? dock : $("p-timeline");
    root.setProperty("--bottom-h", Math.ceil(innerHeight - el.getBoundingClientRect().top) + "px");
  };
  // when the bottom dock grows or shrinks (tab change, drag), move the map by half the change so the subject stays in the free part of the map
  const inset = () => (isDockLayout() && !isSideLayout() ? innerHeight - dock.getBoundingClientRect().top : 0);
  let lastInset = inset();
  new ResizeObserver(() => { const n = inset(); if (Math.abs(n - lastInset) > 4) { map.panBy([0, (n - lastInset) / 2], { duration: reduce.matches ? 0 : 300 }); } lastInset = n; }).observe(dock);
  // scroll cue: a panel body that has more below its visible part fades out at the bottom
  const bodies = [...document.querySelectorAll<HTMLElement>(".pbody")];
  const updateMore = () => bodies.forEach((e) => e.toggleAttribute("data-more", e.scrollHeight - e.clientHeight - e.scrollTop > 4));
  bodies.forEach((e) => { e.addEventListener("scroll", updateMore, { passive: true }); new ResizeObserver(updateMore).observe(e); const c = e.firstElementChild; if (c) new ResizeObserver(updateMore).observe(c); });
  updateMore();
  new ResizeObserver(measure).observe(dock); new ResizeObserver(measure).observe($("p-timeline"));
  addEventListener("resize", measure); phone.addEventListener("change", measure); measure();

  // deep link
  function writeHash() {
    clearTimeout(hashT);
    hashT = window.setTimeout(() => {
      const c = map.getCenter();
      const q = new URLSearchParams({ m: month, r: regionSel.value, ...(multi ? { c: country } : {}), k: metricSel.value, v: `${c.lng.toFixed(3)},${c.lat.toFixed(3)},${map.getZoom().toFixed(2)}` });
      if (panelSt && panelDefs) new URLSearchParams(encodeState(panelSt, panelDefs)).forEach((v, k) => q.set(k, v)); // panel keys: s (layers on) o (order) p (opacity) g (open groups)
      const off: Record<string, number[]> = {}; // class switches, open tab
      document.querySelectorAll<HTMLInputElement>("input[data-cls]:not(:checked):not(:disabled)").forEach((el) => { if (!el.dataset.row!.startsWith("fire-")) (off[el.dataset.row!] ??= []).push(Number(el.dataset.cls)); });
      for (const [id, cs] of Object.entries(fire?.offClasses() ?? {})) off["fire-" + id] = cs; // fire layers: from the layer state, so a choice made in a split month survives the months without tiles
      const ox = encodeOff(off); if (ox) q.set("x", ox);
      const vr: Record<string, string> = {}; // variant pickers that are not on their default
      document.querySelectorAll<HTMLSelectElement>("select[data-var]").forEach((el) => { const d = lf?.layers.find((x) => x.id === el.dataset.var); if (d && el.value !== (d.default_variant ?? d.variants?.[0]?.id)) vr[d.id] = el.value; });
      const ovr = encodeVariants(vr); if (ovr) q.set("vr", ovr);
      if (bm.mode === "sat") q.set("b", "sat");
      if (countrySel.value !== countrySel.options[0].value) q.set("kc", countrySel.value); // Countries overlay metric; the default is left out
      if (dock.dataset.tab !== "timeline" && dock.dataset.open === "1") q.set("t", dock.dataset.tab!);
      try { history.replaceState(null, "", "#" + q.toString().replace(/%2C/g, ",").replace(/%3A/g, ":").replace(/%7E/g, "~")); } catch {}
    }, 150);
  }
  map.on("moveend", writeHash);
  const setBase = (m: "plain" | "sat") => { bm.mode = m; baseSel.value = m; baseNote.textContent = NOTE[m]; bm.apply(); recolor(); paintMap(); writeHash(); };
  baseSel.addEventListener("change", () => setBase(parseBase(baseSel.value)));
  bm.onFail = () => { setBase("plain"); baseNote.textContent = FAIL_NOTE; }; // imagery host unreachable: back to the plain map, with a notice
  initTheme(refresh);
  refresh();
  document.body.dataset.ready = "1"; document.getElementById("loading")?.remove();
  map.once("idle", () => void loadStudy()); setTimeout(() => void loadStudy(), 20000); // the aggregates are not needed for the opening view: after the basemap is drawn (or 20 s), or at once when Details opens
  Object.assign(window, { __appReady: true, __map: map }); // __map: for scripts/perf_layers.py
  let bordersStarted = false; const startBorders = () => { if (!bordersStarted) { bordersStarted = true; void loadBorders(); } };
  map.once("idle", startBorders); setTimeout(startBorders, 20000); // after the basemap and fire cells are drawn (or 20 s): the opening view and the cold-load numbers never wait for it
}
/** Load failure: the opaque "Loading" overlay (z-index 30) used to hide the error banner (z-index 25), so a failed load looked like a load that never ends.
 *  Now the overlay itself turns into the error message with a retry button. */
function showLoadError(message: string) {
  const l = document.getElementById("loading"); document.body.dataset.failed = "1";
  if (l) {
    l.setAttribute("role", "alert"); l.classList.add("failed"); l.style.pointerEvents = "auto";
    l.innerHTML = `<div class="lf"><b>The map data could not be loaded.</b><span></span><button type="button" class="btn" id="retry">Try again</button></div>`;
    l.querySelector("span")!.textContent = message; l.querySelector("#retry")!.addEventListener("click", () => location.reload());
  }
  const b = document.getElementById("banner"); if (b) { b.hidden = false; b.textContent = "Could not load data: " + message; }
}
main().catch((e) => showLoadError(String(e?.message ?? e)));
