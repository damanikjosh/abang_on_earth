#!/usr/bin/env python3
"""Live check of the homepage Technical report row. Fails (exit 1) if the served paper is not the current paper.
  python3 scripts/check_paper_row.py [BASE_URL=https://abang.earth/] [PAPER_PDF=public/paper/technical-report.pdf]
Checks: paper.json is valid and its sha256 equals the sha256 of PAPER_PDF; the served PDF (when pdf_public) has that same sha256, and when pdf_public is false it is NOT served;
the thumbnail (webp and png) is served as an image; the homepage HTML contains the row. Standard library only."""
import sys, json, hashlib, pathlib, urllib.request, urllib.error
BASE = (sys.argv[1] if len(sys.argv) > 1 else "https://abang.earth/").rstrip("/") + "/"
ROOT = pathlib.Path(__file__).resolve().parent.parent
PDF = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else pathlib.Path("public/paper/technical-report.pdf")
bad = []
def get(path):
    try:
        with urllib.request.urlopen(urllib.request.Request(BASE + path, headers={"Cache-Control": "no-cache", "User-Agent": "check_paper_row"}), timeout=60) as r: return r.status, r.headers.get("content-type", ""), r.read()
    except urllib.error.HTTPError as e: return e.code, "", b""
def ok(c, m):
    print(("ok   " if c else "FAIL ") + m)
    if not c: bad.append(m)
want = hashlib.sha256(PDF.read_bytes()).hexdigest() if PDF.exists() else None
ok(want is not None, f"current paper PDF found: {PDF}")
st, _, body = get("paper/paper.json"); ok(st == 200, "paper.json served")
info = json.loads(body) if st == 200 else {}
ok(all(k in info for k in ("title", "author", "pages", "build_time", "sha256", "draft", "pdf_public")), f"paper.json complete: {info.get('title', '')[:50]!r}, {info.get('pages')} pages, built {info.get('build_time')}, draft={info.get('draft')}")
ok(want is not None and info.get("sha256") == want, f"paper.json sha256 == current PDF ({str(info.get('sha256'))[:12]} vs {str(want)[:12]})")
st, ct, body = get("paper/technical-report.pdf")
if info.get("pdf_public"): ok(st == 200 and hashlib.sha256(body).hexdigest() == want, f"served PDF is the current PDF (HTTP {st}, {len(body)} bytes)")
else: ok(st == 404, f"pdf_public is false: the PDF is NOT served (HTTP {st})")
for f, t in (("technical-report-p1.webp", "image/webp"), ("technical-report-p1.png", "image/png")):
    st, ct, body = get("paper/" + f); ok(st == 200 and ct.startswith("image/") and len(body) > 5000, f"thumbnail {f} served ({ct}, {len(body)} bytes)")
st, _, body = get(""); html = body.decode("utf8", "ignore")
ok('id="paper"' in html and "First page of the technical report" in html, "homepage has the Technical report row and the thumbnail alt text")
print("ALL OK" if not bad else f"FAILED: {len(bad)}"); sys.exit(1 if bad else 0)
