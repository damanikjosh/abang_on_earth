#!/usr/bin/env python3
"""Unit test for scripts/sync_paper.py with tiny generated PDFs. uv run --with reportlab --with pypdfium2 --with pillow python scripts/test_sync_paper.py"""
import subprocess, sys, json, tempfile, pathlib, hashlib
from reportlab.pdfgen import canvas
HERE = pathlib.Path(__file__).resolve().parent; T = pathlib.Path(tempfile.mkdtemp())
FOOT = "2 · build src abc1234f, base 0123456, Sun 15 Nov 2026 10:37 KST"
def make(name, body_extra="", pending=False, pages=2, email=None, foot=None):
    f = T / name; c = canvas.Canvas(str(f), pagesize=(612, 792)); c.setAuthor("Test Author"); c.setTitle("short")
    def put(x, y_top, t, size):  # y measured from the top of the page, as in the old PyMuPDF fixtures
        c.setFont("Helvetica", size); c.drawString(x, 792 - y_top, t)
    put(72, 80, "A TINY MODEL OF VIIRS AND MODIS", 16); put(72, 110, "TECHNICAL REPORT", 10); put(72, 130, "Test Author", 10)
    if email: put(72, 145, email, 10)
    put(72, 160, "ABSTRACT VIIRS and MODIS are sensors. " + body_extra + (" RESULT PENDING" if pending else ""), 9)
    for _ in range(pages - 1):
        c.showPage(); put(72, 760, foot or FOOT, 8)
    c.save(); return f
def run(pdf, out, *extra): return subprocess.run([sys.executable, str(HERE / "sync_paper.py"), str(pdf), "--out", str(out), *extra], capture_output=True, text=True)
def check(c, m):
    print(("ok   " if c else "FAIL ") + m)
    if not c: sys.exit(1)
a = make("a.pdf", pending=True); o = T / "oa"; r = run(a, o); j = json.loads((o / "paper.json").read_text())
check(r.returncode == 0, "valid PDF accepted")
check(j["title"] == "A tiny model of VIIRS and MODIS" and j["author"] == "Test Author" and j["pages"] == 2, f"title sentence-cased with acronyms kept, author, pages: {j['title']!r}")
check(j["build_time"] == "2026-11-15T10:37+09:00" and j["paper_commit"] == "abc1234f", "build time and commit read from the footer")
check(j["draft"] is True and j["pdf_public"] is True and j["sha256"] == hashlib.sha256(a.read_bytes()).hexdigest(), "draft flag (RESULT PENDING), pdf_public, sha256 of the PDF")
check(all((o / n).stat().st_size > 0 for n in ["technical-report.pdf", "technical-report-p1.webp", "technical-report-p1.png"]), "pdf, webp and png written")
check((o / "technical-report-p1.webp").stat().st_size < 120_000, "webp under 120 KB")
b1 = (o / "technical-report-p1.webp").read_bytes(); run(a, o); check((o / "technical-report-p1.webp").read_bytes() == b1, "deterministic (same PDF, same image)")
o2 = T / "ob"; r = run(a, o2, "--pdf-private", "--final"); j2 = json.loads((o2 / "paper.json").read_text())
check(j2["pdf_public"] is False and j2["draft"] is False and not (o2 / "technical-report.pdf").exists(), "--pdf-private: no PDF copied; --final: draft false")
z = T / "z.pdf"; z.write_bytes(b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[]/Count 0>>endobj\ntrailer<</Root 1 0 R/Size 3>>\n%%EOF\n")
o4 = T / "oz"; r = run(z, o4); check(r.returncode == 1 and not o4.exists(), f"refuses a PDF with zero pages: {r.stderr.strip()[:80]}")
n = make("n.pdf", foot="2 · build Sun 15 Nov 2026 12:09 KST"); on = T / "on"; r = run(n, on, "--repo", str(T)); jn = json.loads((on / "paper.json").read_text())
check(r.returncode == 0 and jn["build_time"] == "2026-11-15T12:09+09:00" and jn["paper_commit"] is None, "footer without a src hash accepted (16-page build), commit falls back to the repo HEAD (None outside a repo)")
# e-mail masking (private mode only): ink in the e-mail line's box in the thumbnail
from PIL import Image
em = make("e.pdf", pending=True, email="someone@example.org")
def ink(out):  # dark pixels in the band of the e-mail line (y 137..150 pt at 720/612 scale)
    im = Image.open(out / "technical-report-p1.png").convert("L"); k = 720 / 612
    return sum(1 for x in range(int(72 * k), int(190 * k)) for y in range(int(136 * k), int(150 * k)) if im.getpixel((x, y)) < 128)
oe1, oe2 = T / "oe1", T / "oe2"; run(em, oe1); run(em, oe2, "--pdf-private")
j3 = json.loads((oe2 / "paper.json").read_text())
check(ink(oe1) > 50, f"public mode renders the e-mail line as is ({ink(oe1)} dark pixels)")
check(ink(oe2) == 0 and j3["thumb_masked"] == 1, "private mode: the e-mail line is blank in the png thumbnail, paper.json thumb_masked 1")
check(json.loads((oe1 / "paper.json").read_text())["thumb_masked"] == 0, "public mode: thumb_masked 0")
check(ink(oe2) == 0 and not (oe2 / "technical-report.pdf").exists(), "private mode copies no PDF")
print("ALL OK")
