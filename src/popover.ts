import { DOCK_QUERY } from "./layout.ts";
/** One shared info popover: opened by a row's "i" button. role=dialog; closes on Esc, outside click or its close button; focus goes in and returns to the button.
 *  Desktop: anchored beside the panel, next to the row. Phone (or no room beside the panel): bottom sheet with a backdrop, aria-modal. Focus is trapped while open. */
export interface PopContent { title: string; body: string }
const FOCUSABLE = 'a[href],button:not([disabled]),[tabindex]:not([tabindex="-1"])';
export class Popover {
  readonly el: HTMLElement; private back: HTMLElement; private titleEl: HTMLElement; readonly bodyEl: HTMLElement;
  private trigger: HTMLElement | null = null;
  constructor(readonly id = "info-pop") {
    this.back = document.createElement("div"); this.back.className = "pop-back"; this.back.hidden = true;
    this.el = document.createElement("div"); this.el.className = "pop"; this.el.id = id; this.el.hidden = true; this.el.tabIndex = -1;
    this.el.setAttribute("role", "dialog"); this.el.setAttribute("aria-labelledby", id + "-t");
    this.el.innerHTML = `<div class="pop-head"><h2 id="${id}-t"></h2><button type="button" class="pop-x" aria-label="Close"><svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true"><path d="M2 2l10 10M12 2L2 12" stroke="currentColor" stroke-width="1.8" fill="none" stroke-linecap="round"/></svg></button></div><div class="pop-body"></div>`;
    this.titleEl = this.el.querySelector("h2")!; this.bodyEl = this.el.querySelector(".pop-body")!;
    document.body.append(this.back, this.el);
    this.el.querySelector(".pop-x")!.addEventListener("click", () => this.close());
    this.back.addEventListener("pointerdown", () => this.close());
    document.addEventListener("pointerdown", (e) => { if (this.trigger && !this.el.contains(e.target as Node) && !this.trigger.contains(e.target as Node)) this.close(false); }, true);
    document.addEventListener("keydown", (e) => this.key(e));
    addEventListener("resize", () => this.place());
    document.addEventListener("scroll", () => this.place(), true);
  }
  get isOpen() { return !this.el.hidden; }
  get owner() { return this.trigger; }
  toggle(trigger: HTMLElement, c: PopContent) { if (this.isOpen && this.trigger === trigger) this.close(); else this.open(trigger, c); }
  open(trigger: HTMLElement, c: PopContent) {
    if (this.trigger && this.trigger !== trigger) this.trigger.setAttribute("aria-expanded", "false");
    this.trigger = trigger; trigger.setAttribute("aria-expanded", "true");
    this.titleEl.textContent = c.title; this.bodyEl.innerHTML = c.body; this.bodyEl.scrollTop = 0;
    this.el.hidden = false; this.place(); this.el.focus({ preventScroll: true });
  }
  /** returnFocus=false for an outside click: the click already moved focus where the user wants it */
  close(returnFocus = true) {
    if (!this.isOpen) return;
    const t = this.trigger; this.el.hidden = true; this.back.hidden = true; this.trigger = null;
    t?.setAttribute("aria-expanded", "false"); if (returnFocus) t?.focus();
  }
  private sheet() { return matchMedia(DOCK_QUERY).matches; }
  private place() {
    if (!this.isOpen || !this.trigger) return;
    const el = this.el, panel = this.trigger.closest<HTMLElement>(".panel"), pr = panel?.getBoundingClientRect(), left = pr ? pr.right + 8 : 12, room = innerWidth - left - 12;
    const sheet = this.sheet() || !pr || room < 260;
    el.classList.toggle("sheet", sheet); this.back.hidden = !sheet; el.setAttribute("aria-modal", sheet ? "true" : "false");
    if (sheet) { el.style.cssText = ""; return; }
    const w = Math.min(360, room), tr = this.trigger.closest<HTMLElement>(".lyr, .sec-head")?.getBoundingClientRect() ?? this.trigger.getBoundingClientRect();
    el.style.left = left + "px"; el.style.width = w + "px"; el.style.maxHeight = innerHeight - 24 + "px"; el.style.top = "0px"; el.style.bottom = "auto"; el.style.right = "auto";
    const h = el.getBoundingClientRect().height;
    el.style.top = Math.max(12, Math.min(tr.top, innerHeight - 12 - h)) + "px";
  }
  private key(e: KeyboardEvent) {
    if (!this.isOpen) return;
    if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); this.close(); return; }
    if (e.key !== "Tab") return;
    const f = [...this.el.querySelectorAll<HTMLElement>(FOCUSABLE)].filter((x) => x.offsetParent !== null);
    if (!f.length) { e.preventDefault(); return; }
    const first = f[0], last = f[f.length - 1], a = document.activeElement;
    if (e.shiftKey && (a === first || a === this.el)) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && a === last) { e.preventDefault(); first.focus(); }
    else if (!this.el.contains(a)) { e.preventDefault(); first.focus(); }
  }
}
