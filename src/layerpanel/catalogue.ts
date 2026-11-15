import { Emitter, el, uid } from "./emitter.ts";
/** "Add layers": grouped, collapsible catalogue with a checkbox per layer, a count of layers that are on per group, an optional search box across all groups, and remembered open/closed groups. .
 *  Groups come in as data. A layer that is in no group lands in an automatic "Other" group, so nothing is unreachable. Unknown ids in a group are ignored.
 *  Events (catalogue.on(name, fn)): "toggle" {id, on} checkbox changed · "open-change" {open} the set of open groups changed by the user · "info" {id, trigger} (i) pressed. */
export interface CatGroup { id: string; label: string; description?: string; layers: readonly string[] }
export interface CatLayer { id: string; name: string; color?: string; tag?: string; keywords?: string; /** shown but cannot be switched on (placeholder data) */ disabled?: boolean }
export interface CatEvents { toggle: { id: string; on: boolean }; "open-change": { open: string[] }; info: { id: string; trigger: HTMLButtonElement } }
export interface CatOptions { groups: readonly CatGroup[]; layers: readonly CatLayer[]; open?: readonly string[]; search?: boolean; searchLabel?: string }
const CARET = '<svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true" focusable="false"><path d="M4 2l4 4-4 4" stroke="currentColor" stroke-width="1.8" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const INFO = '<svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><circle cx="8" cy="8" r="7" fill="none" stroke="currentColor" stroke-width="1.4"/><circle cx="8" cy="4.6" r="1" fill="currentColor"/><path d="M8 7.2v4.6" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>';
interface G { def: CatGroup; sec: HTMLElement; btn: HTMLButtonElement; count: HTMLElement; body: HTMLElement; ids: string[] }

export class LayerCatalogue extends Emitter<CatEvents> {
  readonly root: HTMLElement; readonly searchInput: HTMLInputElement | null = null;
  private groups: G[] = []; private rows = new Map<string, { li: HTMLLIElement; cb: HTMLInputElement; l: CatLayer }>();
  private openSet: Set<string>; private active = new Set<string>(); private q = ""; private empty: HTMLElement; private live: HTMLElement;
  constructor(host: HTMLElement, opts: CatOptions) {
    super();
    this.root = el("div", "lp-cat"); this.openSet = new Set(opts.open ?? []);
    const byId = new Map(opts.layers.map((l) => [l.id, l])), placed = new Set<string>();
    const defs: CatGroup[] = opts.groups.map((g) => ({ ...g, layers: g.layers.filter((i) => byId.has(i) && !placed.has(i) && (placed.add(i), true)) }));
    const rest = opts.layers.filter((l) => !placed.has(l.id)).map((l) => l.id);
    if (rest.length) defs.push({ id: "other", label: "Other", layers: rest });
    if (opts.search !== false) {
      const label = opts.searchLabel ?? "Search layers";
      const wrap = el("div", "lp-searchwrap"), inp = el("input", "lp-search", { type: "search", "aria-label": label, placeholder: `Search ${opts.layers.length} layers`, autocomplete: "off", spellcheck: "false" });
      inp.addEventListener("input", () => { this.q = inp.value; this.applyFilter(true); });
      inp.addEventListener("keydown", (e) => { if (e.key === "Escape" && inp.value) { e.stopPropagation(); inp.value = ""; this.q = ""; this.applyFilter(true); } });
      wrap.append(inp); this.root.append(wrap); (this as { searchInput: HTMLInputElement | null }).searchInput = inp;
    }
    for (const def of defs) {
      const u = uid("lp-g"), sec = el("section", "lp-group", { "data-group": def.id });
      const h = el("h3", "lp-gh"), btn = el("button", "lp-gbtn", { type: "button", "aria-controls": u });
      const caret = el("span", "lp-caret"); caret.innerHTML = CARET; caret.setAttribute("aria-hidden", "true");
      const lab = el("span", "lp-glabel", {}, def.label), count = el("span", "lp-count");
      btn.append(caret, lab, count); h.append(btn);
      const body = el("ul", "lp-gbody", { id: u, "aria-label": def.label });
      if (def.description) btn.title = def.description;
      for (const id of def.layers) { const r = this.row(byId.get(id)!); this.rows.set(id, r); body.append(r.li); }
      btn.addEventListener("click", () => this.toggleGroup(def.id));
      sec.append(h, body); this.root.append(sec);
      this.groups.push({ def, sec, btn, count, body, ids: [...def.layers] });
    }
    this.empty = el("p", "lp-nomatch", {}, ""); this.empty.hidden = true;
    this.live = el("div", "lp-sr", { role: "status", "aria-live": "polite" });
    this.root.append(this.empty, this.live); host.append(this.root);
    this.refresh();
  }
  private row(l: CatLayer) {
    const li = el("li", "lp-crow", { "data-id": l.id }), label = el("label", "lp-clabel");
    const cb = el("input", "lp-cb", { type: "checkbox" }); cb.disabled = !!l.disabled;
    const sw = el("span", "lp-sw", { "aria-hidden": "true" }); if (l.color) sw.style.background = l.color; else sw.hidden = true;
    const nm = el("span", "lp-name", {}, l.name); label.append(cb, sw, nm);
    const tag = el("span", "lp-tag", {}, l.tag ?? ""); tag.hidden = !l.tag;
    const info = el("button", "lp-info", { type: "button", "aria-label": `About ${l.name}`, "aria-haspopup": "dialog", "aria-expanded": "false" }); info.innerHTML = INFO;
    cb.addEventListener("change", () => { this.emit("toggle", { id: l.id, on: cb.checked }); });
    info.addEventListener("click", () => this.emit("info", { id: l.id, trigger: info }));
    li.append(label, tag, info); return { li, cb, l };
  }
  /** Sets which layers are on (checkbox state and the counts); does not emit. */
  setActive(ids: Iterable<string>): void { this.active = new Set(ids); this.refresh(); }
  getOpen(): string[] { return this.groups.filter((g) => this.openSet.has(g.def.id)).map((g) => g.def.id); }
  /** Sets which groups are open (unknown ids ignored); does not emit. */
  setOpen(ids: Iterable<string>): void { const known = new Set(this.groups.map((g) => g.def.id)); this.openSet = new Set([...ids].filter((i) => known.has(i))); this.refresh(); }
  private toggleGroup(id: string): void {
    if (this.q.trim()) return; // while a search is shown the matching groups are all open
    if (this.openSet.has(id)) this.openSet.delete(id); else this.openSet.add(id);
    this.refresh(); this.emit("open-change", { open: this.getOpen() });
  }
  private match(l: CatLayer): boolean { const q = this.q.trim().toLowerCase(); return !q || `${l.name} ${l.keywords ?? ""}`.toLowerCase().includes(q); }
  private applyFilter(announce: boolean): void {
    this.refresh();
    if (announce && this.q.trim()) { const n = [...this.rows.values()].filter((r) => this.match(r.l)).length; this.live.textContent = ""; setTimeout(() => (this.live.textContent = n ? `${n} layer${n === 1 ? "" : "s"} found` : "No layer found"), 20); }
  }
  private refresh(): void {
    const searching = !!this.q.trim(); let shown = 0;
    for (const [id, r] of this.rows) { r.cb.checked = this.active.has(id); const m = this.match(r.l); r.li.hidden = !m; if (m) shown++; }
    for (const g of this.groups) {
      const on = g.ids.filter((i) => this.active.has(i)).length, matches = g.ids.filter((i) => this.match(this.rows.get(i)!.l)).length;
      const open = searching ? matches > 0 : this.openSet.has(g.def.id);
      g.sec.hidden = searching && matches === 0;
      g.btn.setAttribute("aria-expanded", String(open)); g.btn.toggleAttribute("aria-disabled", searching); if (!searching) g.btn.removeAttribute("aria-disabled");
      g.body.hidden = !open; g.sec.classList.toggle("lp-open", open);
      g.count.textContent = on ? `${on} on · ${g.ids.length}` : String(g.ids.length); g.count.classList.toggle("lp-has", on > 0);
      g.count.setAttribute("aria-label", `${on} of ${g.ids.length} on`);
    }
    this.empty.hidden = !(searching && shown === 0); this.empty.textContent = searching && shown === 0 ? `No layer matches “${this.q.trim()}”.` : "";
  }
}
