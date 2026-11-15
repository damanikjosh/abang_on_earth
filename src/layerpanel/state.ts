/** Pure state of the layer panel: which layers are on, in which order, with which opacity, which catalogue groups are open, and a compact URL-hash encoding of it.
 *  No DOM. Reads today's share-link format too (src/sharelink.ts keys l f o p), so every old link still opens.
 *  Row ids are the app's row ids: context layers as in layers.json ("loss", "peat" ...), fire layers with the "fire-" prefix ("fire-viirs"), and whatever id the host gives the colour overlay ("metric").
 *  Order is "top of the list = drawn on top". Every function returns a new state; the old one is never changed. */
export interface PanelState {
  /** Every known row id, top = drawn on top. Inactive rows keep a slot so a layer switched on later appears where it was. */
  order: readonly string[];
  active: ReadonlySet<string>;
  /** Only values other than 1 are stored (0 to 1, steps of 0.05). */
  opacity: ReadonlyMap<string, number>;
  /** Ids of the catalogue groups that are open. */
  open: readonly string[];
}
/** What a link without panel keys means. Keep it: encode leaves out whatever equals it, decode falls back to it. */
export interface Defaults {
  order: readonly string[]; active: readonly string[]; open: readonly string[];
  /** Rows that an OLD link (keys l f) does not mention but that are always on, e.g. ["metric"], the colour overlay. */
  keepInLegacy?: readonly string[];
}

export const clampOpacity = (x: number): number => (Number.isFinite(x) ? Math.min(1, Math.max(0, Math.round(x * 20) / 20)) : 1);
const uniq = (ids: Iterable<string>, known?: ReadonlySet<string>): string[] => { const seen = new Set<string>(), out: string[] = []; for (const i of ids) if (i && !seen.has(i) && (!known || known.has(i))) { seen.add(i); out.push(i); } return out; };

export function initialState(d: Defaults): PanelState {
  const order = uniq(d.order), known = new Set(order);
  return { order, active: new Set(uniq(d.active, known)), opacity: new Map(), open: uniq(d.open) };
}
/** Active ids in draw order, top first: what the "On the map" list shows. */
export const activeOrder = (s: PanelState): string[] => s.order.filter((i) => s.active.has(i));

export function setActive(s: PanelState, id: string, on: boolean): PanelState {
  if (!s.order.includes(id) || s.active.has(id) === on) return s;
  const a = new Set(s.active); if (on) a.add(id); else a.delete(id);
  return { ...s, active: a };
}
/** The list was reordered: `ids` is the new order of the ACTIVE rows (top first). They take over the slots the active rows had; inactive rows stay where they are.
 *  Ids that are not active, or unknown, are ignored; active rows missing from `ids` keep their relative order after the listed ones. */
export function applyActiveOrder(s: PanelState, ids: readonly string[]): PanelState {
  const act = activeOrder(s), want = uniq(ids, new Set(act)), seq = [...want, ...act.filter((i) => !want.includes(i))];
  let k = 0;
  return { ...s, order: s.order.map((i) => (s.active.has(i) ? seq[k++] : i)) };
}
export function setOpacity(s: PanelState, id: string, v: number): PanelState {
  if (!s.order.includes(id)) return s;
  const m = new Map(s.opacity), c = clampOpacity(v);
  if (c === 1) m.delete(id); else m.set(id, c);
  return { ...s, opacity: m };
}
export const opacityOf = (s: PanelState, id: string): number => s.opacity.get(id) ?? 1;
export function setGroupOpen(s: PanelState, group: string, open: boolean): PanelState {
  const has = s.open.includes(group);
  return has === open ? s : { ...s, open: open ? [...s.open, group] : s.open.filter((g) => g !== group) };
}
export const setOpenGroups = (s: PanelState, groups: readonly string[]): PanelState => ({ ...s, open: uniq(groups) });

// ---- URL encoding ------------------------------------------------------------------------------------------------
// New keys (all optional; a missing key means the default):
//   s = layers that are on:          s=fire-viirs,metric,loss      (empty value = nothing on)
//   o = full stacking order, top first, only when it differs from the default
//   p = opacity per row, only when not 1:   p=loss:0.5~fire-viirs:0.35      (same syntax as the old p key)
//   g = open catalogue groups:       g=fires,land                  (empty value = all closed)
// Old keys, read when no s key is present: l = context layers on, f = fire layers on (ids without "fire-"; missing f = the default fire layers), o = order, p = opacity.
export type HashInput = string | URLSearchParams | Record<string, string | undefined>;
const MAX = 4096; // an untrusted link longer than this is cut before parsing
function toParams(h: HashInput): URLSearchParams {
  if (h instanceof URLSearchParams) return h;
  if (typeof h === "string") { try { return new URLSearchParams(h.replace(/^#/, "").slice(0, MAX)); } catch { return new URLSearchParams(); } }
  const p = new URLSearchParams(); for (const [k, v] of Object.entries(h)) if (v !== undefined) p.set(k, v); return p;
}
const list = (s: string | null): string[] => (s ?? "").split(",").map((x) => x.trim()).filter(Boolean);
const same = (a: readonly string[], b: readonly string[]): boolean => a.length === b.length && a.every((x, i) => x === b[i]);
const pairs = (s: string | null): [string, string][] => (s ?? "").split("~").map((p) => { const i = p.indexOf(":"); return i > 0 ? ([p.slice(0, i), p.slice(i + 1)] as [string, string]) : null; }).filter((x): x is [string, string] => x !== null);

/** The panel part of the link as "s=...&o=..." (no leading "#"); "" when everything equals the defaults. The app merges it with its own keys (m r c k v b t x ...). */
export function encodeState(s: PanelState, d: Defaults): string {
  const q = new URLSearchParams();
  const act = activeOrder(s), dflt = initialState(d);
  if (!same([...s.order].filter((i) => s.active.has(i)).sort(), [...dflt.active].sort())) q.set("s", act.join(","));
  if (!same(s.order, dflt.order)) q.set("o", s.order.join(","));
  const p = [...s.opacity].filter(([, v]) => Math.abs(v - 1) > 1e-9).map(([i, v]) => `${i}:${+v.toFixed(2)}`).join("~"); if (p) q.set("p", p);
  if (!same([...s.open].sort(), [...dflt.open].sort())) q.set("g", s.open.join(","));
  return q.toString().replace(/%2C/g, ",").replace(/%3A/g, ":").replace(/%7E/g, "~");
}
export interface Decoded { state: PanelState; /** true when the link used the old keys (l f o p) */ legacy: boolean }
/** Never throws. Ids that are not in `d.order` are dropped from every key; opacity is clamped; garbage falls back to the defaults. */
export function decodeState(h: HashInput, d: Defaults): Decoded {
  const q = toParams(h), base = initialState(d), known = new Set(base.order);
  const legacy = !q.has("s") && (q.has("l") || q.has("f"));
  let active: string[];
  if (q.has("s")) active = uniq(list(q.get("s")), known);
  else if (legacy) {
    const fireDefault = base.order.filter((i) => base.active.has(i) && i.startsWith("fire-"));
    const fire = q.has("f") ? list(q.get("f")).map((i) => "fire-" + i) : fireDefault;
    // old links had no row for the colour overlay (it was the k= select): the ids in keepInLegacy stay on
    active = uniq([...list(q.get("l")), ...fire, ...(d.keepInLegacy ?? [])], known);
  } else active = [...base.active];
  const given = uniq(list(q.get("o")), known);
  const order = given.length ? [...given, ...base.order.filter((i) => !given.includes(i))] : [...base.order];
  const opacity = new Map<string, number>();
  for (const [id, v] of pairs(q.get("p"))) { const n = Number(v); if (known.has(id) && v.trim() !== "" && Number.isFinite(n) && clampOpacity(n) !== 1) opacity.set(id, clampOpacity(n)); }
  const open = q.has("g") ? uniq(list(q.get("g"))) : base.open; // group ids are checked by the catalogue (it ignores unknown ones)
  return { state: { order, active: new Set(active), opacity, open }, legacy };
}
