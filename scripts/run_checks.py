#!/usr/bin/env python3
"""Run the browser and data checks against a served build.
  npm run build && npm run preview &            # serves dist/ at http://127.0.0.1:4173/
  python3 scripts/run_checks.py [BASE_URL=http://127.0.0.1:4173/] [--only NAME[,NAME...]]
Needs `uv` (https://docs.astral.sh/uv/); each script runs as `uv run --with <packages> python scripts/<script> BASE_URL`, so Playwright's browser must be
installed once: `uvx playwright install chromium`. Prints one PASS/FAIL line per check and exits 1 if any failed."""
import subprocess, sys, time

CHECKS = [  # (script, extra packages, extra arguments after BASE_URL)
    ("check_smoke.py", "playwright,pillow,numpy", []), ("check_home.py", "playwright", []), ("check_keyboard.py", "playwright", []), ("check_touch.py", "playwright", []),
    ("check_ui_details.py", "playwright,pillow,numpy", []), ("check_details.py", "playwright", []), ("check_misc.py", "playwright", []),
    ("check_phone_frame.py", "playwright", []), ("check_links.py", "playwright", []), ("check_share.py", "playwright", []),
    ("check_load_failure.py", "playwright", []), ("check_load_order.py", "playwright", []), ("check_play.py", "playwright", []),
    ("check_scrub.py", "playwright", []), ("check_fireorder.py", "playwright", []), ("check_layer_panel.py", "playwright", []),
    ("check_autoscroll.py", "playwright", []), ("check_clickrule.py", "playwright", []), ("check_countries.py", "playwright", []),
    ("check_basemap.py", "playwright,pillow,numpy", []), ("check_mapbiomas.py", "playwright,pillow", []), ("check_harmonized.py", "playwright", []),
    ("check_daynight.py", "playwright,pillow,numpy", []), ("check_fire_daynight_site.py", "playwright,pillow,numpy", []), ("check_tiles.py", "pmtiles", []),
    ("check_paper_row.py", "", ["public/paper/technical-report.pdf"]),
]
args = [a for a in sys.argv[1:] if not a.startswith("--")]
base = args[0] if args else "http://127.0.0.1:4173/"
only = set(sys.argv[sys.argv.index("--only") + 1].split(",")) if "--only" in sys.argv else None
bad = []
for script, pkgs, extra in CHECKS:
    if only and script not in only and script[:-3] not in only: continue
    cmd = (["uv", "run"] + sum((["--with", p] for p in pkgs.split(",") if p), []) + ["python"] if pkgs else ["python3"]) + ["scripts/" + script, base] + extra
    t = time.time(); r = subprocess.run(cmd, capture_output=True, text=True)
    ok = r.returncode == 0
    print(("PASS " if ok else "FAIL ") + f"{script} ({time.time() - t:.0f} s)", flush=True)
    if not ok:
        bad.append(script); print("\n".join(("    " + l) for l in (r.stdout + r.stderr).strip().split("\n")[-12:]))
print(f"{len(CHECKS) - len(bad) if not only else 'selected'} checks run; failed: {bad or 'none'}")
sys.exit(1 if bad else 0)
