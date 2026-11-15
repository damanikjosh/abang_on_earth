import { Emitter, el, uid } from "./emitter.ts";
/** The (i) popover: description, legend, source and licence, coverage note and the opacity slider. One instance serves every (i) button.
 *  All text is set with textContent, never as HTML: layer text is data, not markup.
 *  role=dialog. Closes on Esc, outside click, the close button, or when its (i) button leaves the page. Focus moves in on open, is trapped while open (Tab cycles) and returns to the (i) button on close.
 *  Wide screens: floats beside the (i) button. Narrow screens (default max-width 640 px): bottom sheet with a backdrop and aria-modal.
 *  Events (pop.on(name, fn)): "opacity-change" {id, value 0..1, percent 0..100} while the slider moves · "close" {id}. */
export interface LegendItem { color?: string; label: string }
export interface InfoContent {
  id: string; title: string; description?: string; legend?: string | readonly LegendItem[]; source?: string; licence?: string; coverage?: string; note?: string;
  /** Current opacity 0..1; shown as the slider value. Pass `false` to hide the slider for a layer that has no opacity. */
  opacity?: number | false;
  /** Must-know sentences, shown first in a highlighted block. */
  important?: string[];
  /** Titled paragraphs: every sentence a layer row used to show lives here instead, under small headings. `key` lets the host replace the text later (updateSection). */
  sections?: { key?: string; title: string; text: string }[];
  /** An element shown under the sections (e.g. a colour ramp), host-owned markup, no user text. */
  node?: HTMLElement;
}
export interface InfoEvents { "opacity-change": { id: string; value: number; percent: number }; close: { id: string } }
export interface InfoOptions { narrowQuery?: string; /** slider step in percent, default 5 */ step?: number }
const FOCUSABLE = 'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),[tabindex]:not([tabindex="-1"])';

export class InfoPopover extends Emitter<InfoEvents> {
  readonly el: HTMLElement; private back: HTMLElement; private titleEl: HTMLElement; private bodyEl: HTMLElement;
  private trigger: HTMLElement | null = null; private id: string | null = null; private slider: HTMLInputElement | null = null; private out: HTMLOutputElement | null = null;
  private mq: MediaQueryList; private step: number;
  constructor(opts: InfoOptions = {}) {
    super();
    const u = uid("lp-pop"); this.step = opts.step ?? 5;
    this.mq = matchMedia(opts.narrowQuery ?? "(max-width: 640px)");
    this.back = el("div", "lp-back"); this.back.hidden = true;
    this.el = el("div", "lp-pop", { role: "dialog", "aria-labelledby": u + "-t", tabindex: "-1" }); this.el.hidden = true;
    const head = el("div", "lp-pop-head"); this.titleEl = el("h2", "", { id: u + "-t" });
    const x = el("button", "lp-pop-x", { type: "button", "aria-label": "Close" }); x.innerHTML = '<svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true" focusable="false"><path d="M2 2l10 10M12 2L2 12" stroke="currentColor" stroke-width="1.8" fill="none" stroke-linecap="round"/></svg>';
    head.append(this.titleEl, x); this.bodyEl = el("div", "lp-pop-body"); this.el.append(head, this.bodyEl);
    document.body.append(this.back, this.el);
    x.addEventListener("click", () => this.close());
    this.back.addEventListener("pointerdown", () => this.close());
    document.addEventListener("pointerdown", (e) => { if (this.isOpen && !this.el.contains(e.target as Node) && !this.trigger?.contains(e.target as Node)) this.close(false); }, true);
    document.addEventListener("keydown", (e) => this.onKey(e), true);
    addEventListener("resize", () => this.place());
    document.addEventListener("scroll", () => this.place(), true);
  }
  get isOpen(): boolean { return !this.el.hidden; }
  get openId(): string | null { return this.isOpen ? this.id : null; }
  toggle(trigger: HTMLElement, c: InfoContent): void { if (this.isOpen && this.trigger === trigger) this.close(); else this.open(trigger, c); }
  open(trigger: HTMLElement, c: InfoContent): void {
    if (this.isOpen) this.close(false);
    this.trigger = trigger; this.id = c.id; trigger.setAttribute("aria-expanded", "true");
    this.titleEl.textContent = c.title; this.bodyEl.replaceChildren(...this.content(c)); this.bodyEl.scrollTop = 0;
    const narrow = this.mq.matches; this.el.setAttribute("aria-modal", String(narrow)); this.el.classList.toggle("lp-sheet", narrow); this.back.hidden = !narrow;
    this.el.hidden = false; this.place(); this.el.focus({ preventScroll: true });
  }
  /** Closes; focus goes back to the (i) button unless the close came from clicking somewhere else (`restore` false). */
  close(restore = true): void {
    if (!this.isOpen) return;
    const t = this.trigger, id = this.id!; this.el.hidden = true; this.back.hidden = true; this.slider = this.out = null;
    t?.setAttribute("aria-expanded", "false"); this.trigger = null; this.id = null;
    if (restore && t?.isConnected) t.focus();
    this.emit("close", { id });
  }
  private impBlock(lines: readonly string[]): HTMLElement { const b = el("div", "lp-pop-imp", { role: "note", "data-imp": "1" }); b.append(el("strong", "", {}, "Important")); for (const l of lines) b.append(el("p", "", {}, l)); return b; }
  /** Replaces (or adds, or removes) the highlighted block of the open panel: a problem status that appeared or went away while the panel is open. */
  setImportant(id: string, lines: readonly string[]): void { if (!this.isOpen || this.id !== id) return; const old = this.bodyEl.querySelector("[data-imp]"); old?.remove(); if (lines.length) this.bodyEl.prepend(this.impBlock(lines)); }
  /** Replaces the text of the open panel's section with this key (a status that changed while the panel is open). */
  updateSection(id: string, key: string, text: string): void { if (!this.isOpen || this.id !== id) return; const p = this.bodyEl.querySelector(`[data-sec="${key}"] p`); if (p) p.textContent = text; }
  /** The host changed the opacity elsewhere: keep the open slider in step. */
  setOpacity(id: string, v: number): void { if (this.isOpen && this.id === id && this.slider) { this.slider.value = String(Math.round(v * 100)); this.sync(); } }
  private sync(): void { if (!this.slider || !this.out) return; const p = Number(this.slider.value); this.out.textContent = `${p}%`; this.slider.setAttribute("aria-valuetext", `${p} percent`); this.slider.style.setProperty("--lp-fill", `${p}%`); }
  private content(c: InfoContent): HTMLElement[] {
    const out: HTMLElement[] = [];
    if (c.important?.length) out.push(this.impBlock(c.important));
    if (c.description) out.push(el("p", "lp-pop-desc", {}, c.description));
    if (c.legend && (typeof c.legend === "string" || c.legend.length)) {
      const sec = el("div", "lp-pop-sec"); sec.append(el("h3", "", {}, "Legend"));
      if (typeof c.legend === "string") sec.append(el("p", "", {}, c.legend));
      else { const ul = el("ul", "lp-legend"); for (const it of c.legend) { const li = el("li"); const sw = el("span", "lp-sw", { "aria-hidden": "true" }); if (it.color) sw.style.background = it.color; else sw.hidden = true; li.append(sw, el("span", "", {}, it.label)); ul.append(li); } sec.append(ul); }
      out.push(sec);
    }
    for (const sc of c.sections ?? []) { const sec = el("div", "lp-pop-sec", sc.key ? { "data-sec": sc.key } : {}); sec.append(el("h3", "", {}, sc.title), el("p", "", {}, sc.text)); out.push(sec); }
    if (c.node) { const sec = el("div", "lp-pop-sec"); sec.append(c.node); out.push(sec); }
    const dl = el("dl", "lp-pop-dl"), add = (k: string, v?: string) => { if (v) { dl.append(el("dt", "", {}, k), el("dd", "", {}, v)); } };
    add("Source", c.source); add("Licence", c.licence); add("Coverage", c.coverage); add("Note", c.note);
    if (dl.children.length) out.push(dl);
    if (c.opacity !== false) {
      const id = uid("lp-op"), row = el("div", "lp-opacity"), lab = el("label", "", { for: id }, "Opacity");
      const inp = el("input", "", { id, type: "range", min: "0", max: "100", step: String(this.step), "aria-label": `${c.title} opacity` });
      inp.value = String(Math.round((c.opacity ?? 1) * 100)); const o = el("output", "lp-op-val", { for: id });
      this.slider = inp; this.out = o; this.sync();
      inp.addEventListener("input", () => { this.sync(); const p = Number(inp.value); this.emit("opacity-change", { id: this.id!, value: p / 100, percent: p }); });
      row.append(lab, inp, o); out.push(row);
    }
    return out;
  }
  private focusables(): HTMLElement[] { return [...this.el.querySelectorAll<HTMLElement>(FOCUSABLE)].filter((e) => !e.hidden && e.offsetParent !== null); }
  private onKey(e: KeyboardEvent): void {
    if (!this.isOpen) return;
    if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); this.close(); return; }
    if (e.key !== "Tab") return;
    const f = this.focusables(); if (!f.length) { e.preventDefault(); return; }
    const a = document.activeElement as HTMLElement | null, i = a ? f.indexOf(a) : -1;
    if (!this.el.contains(a)) { e.preventDefault(); (e.shiftKey ? f[f.length - 1] : f[0]).focus(); return; }
    if (e.shiftKey && (i <= 0)) { e.preventDefault(); f[f.length - 1].focus(); }
    else if (!e.shiftKey && i === f.length - 1) { e.preventDefault(); f[0].focus(); }
  }
  private place(): void {
    if (!this.isOpen) return;
    const t = this.trigger; if (!t || !t.isConnected) { this.close(false); return; }
    const narrow = this.mq.matches, p = this.el;
    this.el.setAttribute("aria-modal", String(narrow)); p.classList.toggle("lp-sheet", narrow); this.back.hidden = !narrow;
    if (narrow) { p.style.left = p.style.top = p.style.width = ""; return; }
    const r = t.getBoundingClientRect(), vw = innerWidth, vh = innerHeight, w = Math.min(360, vw - 16); p.style.width = w + "px";
    const h = p.offsetHeight, panel = t.closest(".lp-panel")?.getBoundingClientRect() ?? r;
    let left = panel.right + 12; if (left + w > vw - 8) left = panel.left - w - 12; if (left < 8) left = Math.min(Math.max(8, r.left), vw - w - 8);
    const top = Math.min(Math.max(8, r.top - 8), Math.max(8, vh - h - 8));
    p.style.left = left + "px"; p.style.top = top + "px";
  }
}
