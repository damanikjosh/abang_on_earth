#!/usr/bin/env python3
"""Refreshes the homepage "Technical report" row from the current paper PDF. Deterministic: same PDF in, same files out.
  uv run --with pypdfium2 --with pillow python scripts/sync_paper.py PDF [--repo PAPER_REPO_DIR] [--final] [--pdf-private] [--out public/paper]
Writes (all under public/paper/, nothing else in the app changes):
  technical-report.pdf          copy of the PDF (NOT written when --pdf-private: paper.json then says pdf_public=false and the row shows no link)
  technical-report-p1.webp/.png page 1 rendered at 2x for a card about 360 px wide (webp target < 120 KB, png is the fallback)
  paper.json                    {title, author, pages, build_time, paper_commit, repo_head, sha256, draft, pdf_public, thumb: {w,h}}
--pdf-private also whitens every e-mail address on page 1 in the thumbnail (paper.json thumb_masked = number of words masked); public mode renders the page as is.
PDF reading and rendering use pypdfium2 (Apache-2.0 OR BSD-3-Clause, PDFium BSD-3-Clause); PyMuPDF (AGPL) was removed for the public release.
Refuses (exit 1, writes nothing) if the PDF has zero pages.
title: the lines of page 1 above "TECHNICAL REPORT" (the PDF metadata title is a shorter variant), set in sentence case (acronyms taken from the abstract); author: PDF metadata;
build_time: the footer "build [src <sha>, base <sha>,] <Day D Mon YYYY HH:MM> KST"; paper_commit: the footer's src sha, or the paper repo's git HEAD when the footer has none (the 16-page build); draft: true while the text still has a boxed RESULT PENDING (override: --final).
"""
import sys, re, json, hashlib, shutil, pathlib, subprocess, io, datetime
def die(msg):
    print("sync_paper: REFUSED:", msg, file=sys.stderr); sys.exit(1)
def text_of(page):
    tp = page.get_textpage(); t = tp.get_text_range(); tp.close(); return t.replace("\r\n", "\n").replace("\r", "\n")
def email_boxes(page):
    """bounding boxes (PDF points, l b r t) of every whitespace-delimited word that contains an e-mail address"""
    tp = page.get_textpage(); n = tp.count_chars(); txt = tp.get_text_range(0, n); boxes = []; i = 0
    while i < n:
        if txt[i].isspace(): i += 1; continue
        j = i
        while j < n and not txt[j].isspace(): j += 1
        if re.search(r"[^\s@]+@[^\s@]+", txt[i:j]):
            cb = [tp.get_charbox(k) for k in range(i, j)]
            boxes.append((min(b[0] for b in cb), min(b[1] for b in cb), max(b[2] for b in cb), max(b[3] for b in cb)))
        i = j
    tp.close(); return boxes
def title_block(page):
    """the lines of page 1 above the 'TECHNICAL REPORT' line (the title is set in small capitals, so font sizes cannot be used)"""
    lines = [l.strip() for l in text_of(page).split("\n") if l.strip()]
    for i, l in enumerate(lines):
        if l.upper().startswith("TECHNICAL REPORT") and i: return " ".join(lines[:i])
    return " ".join(lines[:1])
def sentence_case(t, forms_from):
    forms = {}
    for w in re.findall(r"[A-Za-z][A-Za-z0-9\-]*", forms_from):
        if len(w) >= 2 and w == w.upper() and w.isalpha(): forms.setdefault(w.lower(), w)  # acronyms (VIIRS, MODIS) as written in the running text
    words = re.sub(r"\s+", " ", t).strip().split(" ")
    out = [forms.get(re.sub(r"[^a-z0-9\-]", "", w.lower()), w.lower()) if re.sub(r"[^A-Za-z0-9\-]", "", w) else w for w in words]
    s = " ".join(out); return s[:1].upper() + s[1:]
def main(argv):
    a = [x for x in argv if not x.startswith("--")]; opt = lambda n, d=None: argv[argv.index(n) + 1] if n in argv else d
    if not a: die("usage: sync_paper.py PDF [--repo DIR] [--final] [--pdf-private] [--out DIR]")
    pdf = pathlib.Path(a[0]).resolve(); out = pathlib.Path(opt("--out", "public/paper"))
    repo = pathlib.Path(opt("--repo", pdf.parent))
    import pypdfium2 as pdfium
    from PIL import Image, ImageDraw
    try: doc = pdfium.PdfDocument(pdf)
    except Exception as e: die(f"the PDF cannot be opened ({e})")
    npages = len(doc)
    if npages == 0: die("the PDF has no pages")
    pages = [doc[i] for i in range(npages)]
    text = "\n".join(text_of(p) for p in pages)
    m = re.search(r"build (?:src ([0-9a-f]{6,40}), base [0-9a-f]{6,40}, )?\w{3} (\d{1,2} \w{3} \d{4}) (\d{2}):(\d{2}) KST", text_of(pages[-1])) or re.search(r"build (?:src ([0-9a-f]{6,40}), base [0-9a-f]{6,40}, )?\w{3} (\d{1,2} \w{3} \d{4}) (\d{2}):(\d{2}) KST", text)
    if not m: die("no 'build [src <sha>, base <sha>,] <date time> KST' footer found")
    t = datetime.datetime.strptime(f"{m.group(2)} {m.group(3)}:{m.group(4)}", "%d %b %Y %H:%M")
    abstract = text[text.find("ABSTRACT"):][:3000] if "ABSTRACT" in text else text[:3000]
    title = sentence_case(title_block(pages[0]), abstract)
    try: head = subprocess.run(["git", "-C", str(repo), "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    except Exception: head = None
    pub = "--pdf-private" not in argv
    masked = 0
    k = 720 / pages[0].get_width()  # 2x of a 360 px card
    im = pages[0].render(scale=k, rev_byteorder=False).to_pil().convert("RGB")
    if not pub:  # private mode: the thumbnail must not show any e-mail address either; the words are whitened in the rendered image (the PDF itself is not copied in this mode)
        dr = ImageDraw.Draw(im)
        for bl, bb, br, bt in email_boxes(pages[0]):
            dr.rectangle([(bl - 3) * k, im.height - (bt + 2) * k, (br + 3) * k, im.height - (bb - 2) * k], fill=(255, 255, 255)); masked += 1
    out.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO(); q = 82
    while True:
        buf = io.BytesIO(); im.save(buf, "WEBP", quality=q, method=6)
        if buf.tell() < 120_000 or q <= 40: break
        q -= 6
    (out / "technical-report-p1.webp").write_bytes(buf.getvalue()); im.save(out / "technical-report-p1.png", optimize=True)
    pdfout = out / "technical-report.pdf"
    if pub: shutil.copyfile(pdf, pdfout)
    elif pdfout.exists(): pdfout.unlink()
    info = {"title": title, "author": (doc.get_metadata_dict().get("Author") or ""), "pages": npages, "build_time": t.strftime("%Y-%m-%dT%H:%M+09:00"), "paper_commit": m.group(1) or head,
            "repo_head": head, "sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(), "draft": "--final" not in argv and bool(re.search(r"RESULT PENDING", text)),
            "pdf_public": pub, "thumb_masked": masked, "thumb": {"w": im.width, "h": im.height}}
    (out / "paper.json").write_text(json.dumps(info, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps(info, ensure_ascii=False)); print("webp bytes", len(buf.getvalue()), "q", q)
if __name__ == "__main__": main(sys.argv[1:])
