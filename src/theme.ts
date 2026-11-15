// light/dark: follows the OS unless the user toggled; choice kept in localStorage (no cookies, no tracking)
const KEY = "aa-theme";
/** The saved choice (if any) goes on <html data-theme>. Safe to call more than once. */
export function applyStoredTheme() { try { const t = localStorage.getItem(KEY); if (t) document.documentElement.dataset.theme = t; } catch {} }
export function initTheme(onChange?: () => void) {
  applyStoredTheme();
  document.getElementById("theme")?.addEventListener("click", () => {
    const dark = isDark();
    const next = dark ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem(KEY, next); } catch {}
    onChange?.();
  });
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => onChange?.());
}
export function isDark(): boolean {
  const t = document.documentElement.dataset.theme;
  return t ? t === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
}
