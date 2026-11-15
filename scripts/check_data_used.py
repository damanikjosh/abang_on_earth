#!/usr/bin/env python3
"""Static proof that every file under public/ is used by the site, and list of those that are not.

A file is USED when one of these holds:
  1. it is a fixed file of the page set (favicon, 404 page, data-version.json, ...), listed in FIXED;
  2. a source page (index.html, app/index.html, credits/index.html) links it (href/src), or home.ts fetches it (paper/paper.json);
  3. it is a core data file named by the data manifest (manifest.json "files") or layers.json / manifest.json themselves;
  4. it is a tile file that the app requests for a layer row that is reachable in the layer list: every entry of layers.json
     (except rows in HIDDEN_ROWS of src/layergroups.ts and rows marked placeholder) and every fire layer of manifest.json
     (except placeholder rows), with {month}/{year}/{class}/{variant} expanded over the entry's "available" list or its min/max.
Usage: python3 scripts/check_data_used.py [REPO_ROOT=.] [--list-unused] [--crawl LOG]   (exit 1 when public/ holds an unused file,
or when --crawl LOG names a requested URL that is not in the used set).
"""
import json, re, sys
from pathlib import Path

ROOT = Path(next((a for a in sys.argv[1:] if Path(a).is_dir()), "."))
PUB = ROOT / "public"
FIXED = {"CNAME", "404.html", "favicon.svg", "data-version.json"}

def hidden_rows():
    """Row ids the app never lists: HIDDEN_ROWS (placeholders) and REMOVED_ROWS (taken out of the app) of src/layergroups.ts."""
    t = (ROOT / "src/layergroups.ts").read_text(); out = set()
    for name in ("HIDDEN_ROWS", "REMOVED_ROWS"):
        m = re.search(name + r"[^=]*=\s*\[([^\]]*)\]", t)
        if m: out |= set(re.findall(r'"([^"]+)"', m.group(1)))
    return out

def expand(path, avail, lo=None, hi=None):
    """All concrete paths of a template."""
    if "{" not in path:
        return [path]
    vals = [str(a) for a in (avail or [])]
    out = []
    for ph in ("month", "year", "class", "variant"):
        if "{" + ph + "}" in path:
            if ph == "class":
                vals = [v[1:] if v.startswith("c") else v for v in vals]
            out = [path.replace("{" + ph + "}", v) for v in vals]
    return out

def used_set():
    used, why = set(), {}
    def add(p, reason):
        used.add(p); why.setdefault(p, reason)
    for f in FIXED:
        add(f, "fixed page file")
    # page links
    for page in ("index.html", "app/index.html", "credits/index.html", "public/404.html"):
        t = (ROOT / page).read_text()
        for u in re.findall(r'(?:href|src)="([^"#?:]+)"', t):
            u = u.lstrip("./").lstrip("/")
            if u.startswith("assets/") or u.endswith("/") or not u or u.startswith("src/"):
                continue
            q = PUB / u
            if q.is_file():
                add(u, f"linked from {page}")
        for u in re.findall(r'srcset="([^"\s]+)"', t):
            if (PUB / u).is_file():
                add(u, f"srcset in {page}")
        for u in re.findall(r'(?:href|src)="\.\./([^"#?]+)"', t):
            if (PUB / u).is_file():
                add(u, f"linked from {page}")
    for u in re.findall(r'"(paper/[A-Za-z0-9_.-]+)"', (ROOT / "src/home.ts").read_text()):
        add(u, "fetched by src/home.ts")
    # the homepage may link the deck/paper through paper.json: its files are read as used
    pj = PUB / "paper/paper.json"
    if pj.is_file():
        for v in json.loads(pj.read_text()).values():
            if isinstance(v, str) and (PUB / v).is_file():
                add(v, "named in paper/paper.json")
    ptr = json.loads((PUB / "data-version.json").read_text())
    bases = {ptr["base"], ptr["fallback"]}
    hid = hidden_rows()
    for base in bases:
        D = PUB / base
        for core in ("manifest.json", "layers.json"):
            add(base + core, "core data file (loadCore)")
        man = json.loads((D / "manifest.json").read_text())
        for k, v in man["files"].items():
            add(base + v, f"manifest.files.{k}")
        app = (ROOT / "src/app.ts").read_text()
        m = re.search(r'\.\.\.\[((?:"[^"]+",?\s*)+)\]\.map\(\(f\) => getJSON', app)
        for f in re.findall(r'"([^"]+)"', m.group(1) if m else ""):
            add(base + f + ".json", "per-study aggregate loaded by src/app.ts (loadStudy)")
        lay = json.loads((D / "layers.json").read_text())
        for d in lay["layers"]:
            if d["id"] in hid or d.get("placeholder"):
                continue
            paths = [(d["path"], d.get("available"))]
            for c in d.get("classes", []) or []:
                if c.get("path"): paths.append((c["path"], c.get("available")))
            for p, av in paths:
                for q in expand(p, av): add(base + q, f"layers.json row {d['id']}")
        for d in man.get("fire_layers", {}).get("layers", []):
            if ("fire-" + d["id"]) in hid or d.get("placeholder"):
                continue
            paths = [(d["path"], d.get("available"))]
            for c in d.get("classes", []) or []:
                if c.get("path"): paths.append((c["path"], c.get("available")))
            for p, av in paths:
                for q in expand(p, av): add(base + q, f"manifest fire layer {d['id']}")
    return used, why

if __name__ == "__main__":
    used, why = used_set()
    on_disk = {str(p.relative_to(PUB)): p.stat().st_size for p in PUB.rglob("*") if p.is_file() and p.name != ".DS_Store"}
    missing = sorted(u for u in used if u not in on_disk and u != "CNAME")  # CNAME exists only once a custom domain is attached
    unused = sorted(f for f in on_disk if f not in used)
    print(f"public/: {len(on_disk)} files, {sum(on_disk.values())/1e6:.1f} MB; used {len(used & set(on_disk))}; unused {len(unused)} ({sum(on_disk[f] for f in unused)/1e6:.1f} MB); referenced but missing {len(missing)}")
    for m in missing[:20]: print("  MISSING", m, "<-", why[m])
    if "--list-unused" in sys.argv or unused:
        grp = {}
        for f in unused:
            g = "/".join(f.split("/")[:2]) if f.count("/") >= 2 else f
            a = grp.setdefault(g, [0, 0]); a[0] += 1; a[1] += on_disk[f]
        for g, (n, b) in sorted(grp.items()): print(f"  UNUSED {g}: {n} files, {b/1e6:.2f} MB")
    bad = 0
    if "--crawl" in sys.argv:
        log = Path(sys.argv[sys.argv.index("--crawl") + 1]).read_text().split()
        req = {u.split("?")[0].lstrip("/") for u in log}
        base_req = {r for r in req if (PUB / r).is_file() or r in used}
        outside = sorted(r for r in base_req if r not in used)
        never = sorted(f for f in used if f in on_disk and f not in req and f not in FIXED)
        print(f"crawl: {len(req)} distinct URLs; requested but not in used set: {len(outside)}; in used set but never requested by the crawl: {len(never)}")
        for o in outside[:20]: print("  OUTSIDE", o)
        bad = len(outside)
    sys.exit(1 if (unused or missing or bad) else 0)
