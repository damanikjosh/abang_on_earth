import "./common";
import "./home.css";
import { initTheme } from "./theme";
import { loadPointer, dataUrl } from "./dataroot";
import { parseCountries, coveragePhrase } from "./countries";
import { isPaperInfo, statusLine } from "./paperrow";
initTheme();

// Coverage wording follows the data: the countries listed in the active data folder's manifest ("Indonesia" stays if anything fails or the data is Indonesia-only).
(async () => {
  try {
    const BASE = import.meta.env.BASE_URL, ptr = await loadPointer(BASE, (u, i) => fetch(u, i));
    const r = await fetch(dataUrl(BASE, ptr.base, "manifest.json"), { cache: "no-cache" }); if (!r.ok) return;
    const m = parseCountries(await r.json()); if (!m) return;
    const { phrase, full, prep } = coveragePhrase(m.countries);
    const was = "across Southeast Asia", now = `${prep} ${phrase}`; // static head text says the 11-country default; follow the data if it differs
    if (now !== was) {
      document.title = document.title.replace(was, now);
      document.querySelectorAll<HTMLMetaElement>('meta[name=description],meta[property="og:title"],meta[property="og:description"]').forEach((e) => (e.content = e.content.replace(was, now)));
    }
    document.querySelectorAll("[data-coverage]").forEach((e) => (e.textContent = phrase));
    document.querySelectorAll("[data-coverage-prep]").forEach((e) => (e.textContent = prep));
    const l = document.getElementById("coverage-list"); if (l && phrase !== full) { l.textContent = `${m.countries.length} countries: ${full}.`; l.hidden = false; } // the full list stays reachable
  } catch { /* keep the static text */ }
})();

// Technical report row: text from paper/paper.json (written by scripts/sync_paper.py); no valid paper.json = the row stays hidden
(async () => {
  try {
    const r = await fetch(import.meta.env.BASE_URL + "paper/paper.json", { cache: "no-cache" }); if (!r.ok) return;
    const j: unknown = await r.json(); if (!isPaperInfo(j)) return;
    const q = (s: string) => document.querySelector<HTMLElement>(s)!;
    q("#paper-h").textContent = j.title; q(".paper-by").textContent = j.author; q(".paper-status").textContent = statusLine(j);
    q("#paper-link").hidden = !j.pdf_public; q("#paper-soon").hidden = j.pdf_public;
    if (j.pdf_public) q("#paper-link").setAttribute("aria-label", `Read the PDF: ${j.title}`);
    q("#paper").hidden = false;
  } catch { /* keep the row hidden */ }
})();
