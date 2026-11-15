import { Emitter, el, uid } from "./emitter.ts";
/** "On the map": only the layers that are on, in draw order (top of the list = drawn on top). .
 *  Row = drag handle, swatch + name, optional picker slot (an element the host supplies: metric picker, sensor picker ...), (i) button, off button. No up/down buttons.
 *  Reorder: pointer events (mouse, touch, pen) on the handle, or with the keyboard on the handle: Space/Enter grab, Arrow Up/Down (Home/End) move, Space/Enter drop, Esc cancel, with aria-live announcements.
 *  Events (list.on(name, fn) or addEventListener): "order-change" {order} new order of the ids, top first, sent when a drop commits · "info" {id, trigger} (i) pressed · "off" {id} off button pressed. */
export interface OnItem { id: string; name: string; color?: string; tag?: string; /** host-owned element shown under the name (e.g. a <select>) */ picker?: HTMLElement | null }
export interface OnEvents { "order-change": { order: string[] }; info: { id: string; trigger: HTMLButtonElement }; off: { id: string } }
export interface OnOptions { label?: string; emptyText?: string }
const GRIP = '<svg width="14" height="18" viewBox="0 0 14 18" aria-hidden="true" focusable="false"><g fill="currentColor"><circle cx="4" cy="4" r="1.6"/><circle cx="10" cy="4" r="1.6"/><circle cx="4" cy="9" r="1.6"/><circle cx="10" cy="9" r="1.6"/><circle cx="4" cy="14" r="1.6"/><circle cx="10" cy="14" r="1.6"/></g></svg>';
const X = '<svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true" focusable="false"><path d="M2 2l10 10M12 2L2 12" stroke="currentColor" stroke-width="1.8" fill="none" stroke-linecap="round"/></svg>';
const INFO = '<svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><circle cx="8" cy="8" r="7" fill="none" stroke="currentColor" stroke-width="1.4"/><circle cx="8" cy="4.6" r="1" fill="currentColor"/><path d="M8 7.2v4.6" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>';

interface Session { id: string; start: string[]; kind: "key" | "pointer"; pointerId?: number; y?: number; raf?: number; t?: number }
const EDGE = 48, MAXSPEED = 18; // auto-scroll while dragging: pixels from the edge of the scrolling panel where it starts, and px per 16.7 ms (one frame at 60 Hz) at the very edge; scaled by the real time between frames so a slow device scrolls as fast

export class OnTheMapList extends Emitter<OnEvents> {
  readonly root: HTMLElement; readonly list: HTMLUListElement;
  private rows = new Map<string, HTMLLIElement>(); private names = new Map<string, string>();
  private empty: HTMLElement; private live: HTMLElement; private session: Session | null = null; private moving = false; private focusAfter: string | null = null;
  constructor(host: HTMLElement, opts: OnOptions = {}) {
    super();
    const u = uid("lp-on"); this.helpId = u + "-help";
    this.root = el("div", "lp-onmap"); this.root.id = u;
    this.list = el("ul", "lp-stack", { "aria-label": opts.label ?? "Layers on the map. The first one is drawn on top." });
    this.empty = el("p", "lp-empty", { tabindex: "-1" }, opts.emptyText ?? "No layer is on. Tick one in the list below.");
    const help = el("p", "lp-sr", { id: u + "-help" }, "Press Space or Enter to pick this layer up, then Arrow Up or Arrow Down to move it, Space or Enter to drop it, Escape to cancel. Or drag it with the mouse or your finger.");
    this.live = el("div", "lp-sr", { role: "status", "aria-live": "polite" });
    this.root.append(this.list, this.empty, help, this.live); host.append(this.root);
    this.list.addEventListener("keydown", (e) => this.onKey(e));
    this.list.addEventListener("click", (e) => this.onClick(e));
    this.list.addEventListener("pointerdown", (e) => this.onPointerDown(e));
    this.list.addEventListener("pointermove", (e) => this.onPointerMove(e));
    this.list.addEventListener("pointerup", (e) => this.onPointerUp(e, true));
    this.list.addEventListener("pointercancel", (e) => this.onPointerUp(e, false));
    this.list.addEventListener("focusout", (e) => { const t = e.target as HTMLElement; if (!this.moving && this.session?.kind === "key" && t.classList.contains("lp-handle") && !this.list.contains(e.relatedTarget as Node)) this.cancel("Cancelled, moved back"); });
  }
  private helpId = "";
  /** Ids in the order they are shown now. */
  get order(): string[] { return [...this.list.children].map((r) => (r as HTMLElement).dataset.id!); }
  /** Shows exactly these rows, in this order. Rows that stay keep their DOM (focus and an open (i) popover survive). */
  setItems(items: readonly OnItem[]): void {
    if (this.session) this.cancel();
    const keep = new Set(items.map((i) => i.id));
    for (const [id, li] of this.rows) if (!keep.has(id)) { li.remove(); this.rows.delete(id); this.names.delete(id); }
    items.forEach((it, idx) => {
      let li = this.rows.get(it.id);
      if (!li) { li = this.build(it); this.rows.set(it.id, li); }
      this.fill(li, it);
      if (this.list.children[idx] !== li) this.list.insertBefore(li, this.list.children[idx] ?? null);
    });
    this.empty.hidden = items.length > 0;
    if (this.focusAfter !== null) { const t = this.rows.get(this.focusAfter)?.querySelector<HTMLElement>(".lp-handle") ?? (items.length ? null : this.empty); this.focusAfter = null; t?.focus(); }
  }
  private build(it: OnItem): HTMLLIElement {
    const li = el("li", "lp-row", { "data-id": it.id });
    const handle = el("button", "lp-handle", { type: "button", "aria-pressed": "false", "aria-describedby": this.helpId }); handle.innerHTML = GRIP;
    const sw = el("span", "lp-sw", { "aria-hidden": "true" }), name = el("span", "lp-name"), tag = el("span", "lp-tag"); tag.hidden = true;
    const info = el("button", "lp-info", { type: "button", "aria-haspopup": "dialog", "aria-expanded": "false" }); info.innerHTML = INFO;
    const off = el("button", "lp-off", { type: "button" }); off.innerHTML = X;
    const picker = el("div", "lp-picker"); picker.hidden = true;
    li.append(handle, sw, name, tag, info, off, picker);
    return li;
  }
  private fill(li: HTMLLIElement, it: OnItem): void {
    this.names.set(it.id, it.name);
    li.querySelector<HTMLElement>(".lp-handle")!.setAttribute("aria-label", `Reorder ${it.name}`);
    li.querySelector<HTMLElement>(".lp-handle")!.setAttribute("aria-roledescription", "drag handle");
    const sw = li.querySelector<HTMLElement>(".lp-sw")!; sw.style.background = it.color ?? "transparent"; sw.hidden = !it.color;
    li.querySelector<HTMLElement>(".lp-name")!.textContent = it.name;
    const tag = li.querySelector<HTMLElement>(".lp-tag")!; tag.textContent = it.tag ?? ""; tag.hidden = !it.tag;
    li.querySelector<HTMLElement>(".lp-info")!.setAttribute("aria-label", `About ${it.name}`);
    li.querySelector<HTMLElement>(".lp-off")!.setAttribute("aria-label", `Turn off ${it.name}`);
    const slot = li.querySelector<HTMLElement>(".lp-picker")!;
    if ((it.picker ?? null) !== (slot.firstElementChild ?? null)) { slot.replaceChildren(...(it.picker ? [it.picker] : [])); }
    slot.hidden = !it.picker;
  }
  private say(t: string): void { this.live.textContent = ""; setTimeout(() => (this.live.textContent = t), 20); }
  private nameOf = (id: string): string => this.names.get(id) ?? id;

  private onClick(e: MouseEvent): void {
    const b = (e.target as HTMLElement).closest("button"); const li = b?.closest<HTMLLIElement>(".lp-row"); if (!b || !li) return;
    const id = li.dataset.id!;
    if (b.classList.contains("lp-info")) this.emit("info", { id, trigger: b as HTMLButtonElement });
    else if (b.classList.contains("lp-off")) {
      const o = this.order, k = o.indexOf(id); this.focusAfter = o[k + 1] ?? o[k - 1] ?? "";
      this.say(`${this.nameOf(id)} turned off`); this.emit("off", { id });
    }
  }
  // ---- keyboard (WAI-ARIA rearrangeable list pattern: grab, move, drop, cancel)
  private onKey(e: KeyboardEvent): void {
    const h = (e.target as HTMLElement).closest<HTMLButtonElement>(".lp-handle"); if (!h) return;
    const li = h.closest<HTMLLIElement>(".lp-row")!, id = li.dataset.id!;
    const s = this.session;
    if (!s) { if (e.key === " " || e.key === "Enter") { e.preventDefault(); this.grab(id, li, h, "key"); } return; }
    if (s.kind !== "key" || s.id !== id) return;
    if (e.key === " " || e.key === "Enter") { e.preventDefault(); this.drop(); }
    else if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); this.cancel("Cancelled, moved back"); }
    else if (e.key === "ArrowUp" || e.key === "ArrowDown" || e.key === "Home" || e.key === "End") {
      e.preventDefault();
      const n = this.list.children.length, k = this.indexOf(li);
      const to = e.key === "ArrowUp" ? k - 1 : e.key === "ArrowDown" ? k + 1 : e.key === "Home" ? 0 : n - 1;
      if (to < 0 || to >= n) { this.say(`${this.nameOf(id)} is already ${to < 0 ? "first" : "last"}`); return; }
      if (to === k) return;
      this.place(li, to); h.focus(); this.say(`${this.nameOf(id)}, position ${to + 1} of ${n}`);
    }
  }
  private indexOf(li: Element): number { return [...this.list.children].indexOf(li); }
  private place(li: HTMLLIElement, to: number): void { // move without losing focus
    this.moving = true; const ref = [...this.list.children].filter((c) => c !== li)[to] ?? null; this.list.insertBefore(li, ref); this.moving = false;
  }
  private grab(id: string, li: HTMLLIElement, h: HTMLButtonElement, kind: "key" | "pointer", pointerId?: number): void {
    this.session = { id, start: this.order, kind, pointerId };
    li.classList.add("lp-grabbed"); h.setAttribute("aria-pressed", "true"); this.list.classList.add("lp-sorting");
    if (kind === "key") this.say(`${this.nameOf(id)} picked up, position ${this.indexOf(li) + 1} of ${this.list.children.length}. Arrow Up or Down to move, Space to drop, Escape to cancel.`);
  }
  private end(): HTMLLIElement | null {
    const s = this.session; if (s?.raf) cancelAnimationFrame(s.raf); this.session = null; this.list.classList.remove("lp-sorting");
    const li = s ? this.rows.get(s.id) ?? null : null;
    if (li) { li.classList.remove("lp-grabbed"); li.querySelector(".lp-handle")?.setAttribute("aria-pressed", "false"); }
    return li;
  }
  private drop(): void {
    const s = this.session!, from = s.start, li = this.end(), now = this.order;
    const moved = now.join("\u0000") !== from.join("\u0000");
    this.say(moved ? `${this.nameOf(s.id)} dropped, position ${now.indexOf(s.id) + 1} of ${now.length}` : `${this.nameOf(s.id)} dropped, position unchanged`);
    if (s.kind === "key") li?.querySelector<HTMLElement>(".lp-handle")?.focus();
    if (moved) this.emit("order-change", { order: now });
  }
  private cancel(msg?: string): void {
    const s = this.session; if (!s) return; const start = s.start, li = this.end();
    this.moving = true; for (const id of start) { const r = this.rows.get(id); if (r) this.list.append(r); } this.moving = false;
    if (s.kind === "key") li?.querySelector<HTMLElement>(".lp-handle")?.focus();
    if (msg) this.say(msg);
  }
  // ---- pointer (mouse, touch, pen): the row follows the pointer by swapping places with the rows it passes
  private onPointerDown(e: PointerEvent): void {
    const h = (e.target as HTMLElement).closest<HTMLButtonElement>(".lp-handle"); if (!h || this.session) return;
    if (e.pointerType === "mouse" && e.button !== 0) return;
    const li = h.closest<HTMLLIElement>(".lp-row")!;
    e.preventDefault(); h.focus({ preventScroll: true });
    try { this.list.setPointerCapture(e.pointerId); } catch { /* pointer already gone */ }
    this.grab(li.dataset.id!, li, h, "pointer", e.pointerId);
  }
  private onPointerMove(e: PointerEvent): void {
    const s = this.session; if (!s || s.kind !== "pointer" || e.pointerId !== s.pointerId) return;
    s.y = e.clientY; this.follow(); if (!s.raf) s.raf = requestAnimationFrame(() => this.autoScroll());
  }
  /** The dragged row takes the place under the pointer (rows it passes swap with it). */
  private follow(): void {
    const s = this.session; if (!s || s.kind !== "pointer" || s.y === undefined) return;
    const li = this.rows.get(s.id)!, others = [...this.list.children].filter((c) => c !== li) as HTMLElement[];
    let to = others.length;
    for (let i = 0; i < others.length; i++) { const r = others[i].getBoundingClientRect(); if (s.y < r.top + r.height / 2) { to = i; break; } }
    if (to !== this.indexOf(li)) this.place(li, to);
  }
  /** The panel that scrolls the list (nearest ancestor that can scroll vertically). */
  private scroller(): HTMLElement | null { for (let n = this.list.parentElement; n; n = n.parentElement) { const o = getComputedStyle(n).overflowY; if ((o === "auto" || o === "scroll") && n.scrollHeight > n.clientHeight + 1) return n; } return null; }
  /** While the pointer is near the top or bottom edge of the panel the panel scrolls (a long list on a phone no longer ends at the screen edge); the row keeps following the pointer. */
  private autoScroll(): void {
    const s = this.session; if (!s || s.kind !== "pointer") return; s.raf = 0;
    const now = performance.now(), dt = Math.min(100, s.t ? now - s.t : 16.7); s.t = now; // time-based: a slow frame rate does not slow the scroll down
    const sc = this.scroller(), y = s.y; if (!sc || y === undefined) return;
    const r = sc.getBoundingClientRect(), top = Math.max(r.top, 0), bottom = Math.min(r.bottom, innerHeight);
    const k = dt / 16.7, d = y < top + EDGE ? -Math.ceil(MAXSPEED * k * Math.min(1, (top + EDGE - y) / EDGE)) : y > bottom - EDGE ? Math.ceil(MAXSPEED * k * Math.min(1, (y - (bottom - EDGE)) / EDGE)) : 0;
    if (d) { const before = sc.scrollTop; sc.scrollTop += d; if (sc.scrollTop !== before) this.follow(); }
    s.raf = requestAnimationFrame(() => this.autoScroll());
  }
  private onPointerUp(e: PointerEvent, commit: boolean): void {
    const s = this.session; if (!s || s.kind !== "pointer" || e.pointerId !== s.pointerId) return;
    try { this.list.releasePointerCapture(e.pointerId); } catch { /* already released */ }
    if (commit) this.drop(); else this.cancel("Cancelled, moved back");
  }
}
