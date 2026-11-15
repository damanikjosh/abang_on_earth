/** Homepage "Technical report" row: the text comes from public/paper/paper.json, written by scripts/sync_paper.py, never typed here. */
export interface PaperInfo { title: string; author: string; pages: number; build_time: string; draft: boolean; pdf_public: boolean; sha256?: string }
export const isPaperInfo = (x: unknown): x is PaperInfo => {
  const o = x as Record<string, unknown> | null;
  return !!o && typeof o === "object" && typeof o.title === "string" && !!o.title && typeof o.author === "string" && typeof o.pages === "number" && o.pages > 0
    && typeof o.build_time === "string" && !Number.isNaN(Date.parse(o.build_time)) && typeof o.draft === "boolean" && typeof o.pdf_public === "boolean";
};
/** "15 Nov 2026 10:39 KST" (always Korea Standard Time, whatever the visitor's zone) */
export function kst(iso: string): string {
  const p = Object.fromEntries(new Intl.DateTimeFormat("en-GB", { timeZone: "Asia/Seoul", day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", hourCycle: "h23" })
    .formatToParts(new Date(iso)).map((x) => [x.type, x.value]));
  return `${p.day} ${p.month} ${p.year} ${p.hour}:${p.minute} KST`;
}
/** "Draft · updated 15 Nov 2026 10:39 KST · 36 pages" ("Updated ..." when the paper is final) */
export const statusLine = (i: PaperInfo): string => `${i.draft ? "Draft · updated" : "Updated"} ${kst(i.build_time)} · ${i.pages} ${i.pages === 1 ? "page" : "pages"}`;
