/** Tiny typed event emitter on top of EventTarget. `on` hands the listener the event detail and returns an unsubscribe function; plain addEventListener also works (CustomEvent, detail = payload). */
export class Emitter<M extends object> extends EventTarget {
  on<K extends keyof M & string>(type: K, fn: (detail: M[K]) => void): () => void {
    const h = (e: Event) => fn((e as CustomEvent<M[K]>).detail);
    this.addEventListener(type, h);
    return () => this.removeEventListener(type, h);
  }
  protected emit<K extends keyof M & string>(type: K, detail: M[K]): void { this.dispatchEvent(new CustomEvent(type, { detail })); }
}
let n = 0;
/** Unique DOM id prefix for aria-controls / aria-describedby. */
export const uid = (p: string): string => `${p}-${++n}`;
export function el<K extends keyof HTMLElementTagNameMap>(tag: K, cls = "", attrs: Record<string, string> = {}, text?: string): HTMLElementTagNameMap[K] {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (text !== undefined) e.textContent = text;
  return e;
}
