import { test } from "node:test";
import assert from "node:assert/strict";
import { isPaperInfo, kst, statusLine } from "../src/paperrow.ts";

const I = { title: "T", author: "A", pages: 36, build_time: "2026-11-15T10:39+09:00", draft: true, pdf_public: true };
test("status line is generated from paper.json, in Korea Standard Time", () => {
  assert.equal(kst("2026-11-15T10:39+09:00"), "15 Nov 2026 10:39 KST");
  assert.equal(kst("2026-11-15T01:39:00Z"), "15 Nov 2026 10:39 KST");
  assert.equal(statusLine(I), "Draft · updated 15 Nov 2026 10:39 KST · 36 pages");
  assert.equal(statusLine({ ...I, draft: false, pages: 1 }), "Updated 15 Nov 2026 10:39 KST · 1 page");
});
test("isPaperInfo rejects anything that is not a complete paper.json", () => {
  assert.ok(isPaperInfo(I));
  for (const x of [null, {}, "x", { ...I, pages: 0 }, { ...I, title: "" }, { ...I, build_time: "soon" }, { ...I, draft: "yes" }, { ...I, pdf_public: undefined }]) assert.ok(!isPaperInfo(x), JSON.stringify(x));
});
