#!/usr/bin/env python3
"""build the homepage "Facts" row (six tested facts, each with an inline SVG diagram drawn from real data).
  python3 scripts/build_facts_data.py            # writes scripts/facts_data.json and rewrites the block between <!-- facts:begin --> and <!-- facts:end --> in index.html
  python3 scripts/build_facts_data.py --check    # recompute and fail if index.html or facts_data.json differ (used by tests/facts.test.ts)
Inputs (all in the repo; the file hashes are recorded in facts_data.json):
  public/data-v4/monthly.json     yearly Indonesia counts (MODIS raw, VIIRS raw, VIIRS-equivalent) and the monthly profiles of Myanmar, Laos, Vietnam, Indonesia
  scripts/facts_links.json        the "Open on the map" hashes (each one read back from the app's own link writer and loaded in a browser by scripts/check_facts.py)
Numbers that are not in the data files above come from the project's fact book and are in FACTBOOK below, each with its source.
The El Nino year list is not in any data file; it was recovered from the fact book's three group means (the script asserts that it reproduces 95,205 / 44,110 / 24,278 exactly).
Standard library only."""
import json, hashlib, pathlib, sys, html

ROOT = pathlib.Path(__file__).resolve().parent.parent
MON = ROOT / "public/data-v4/monthly.json"
MAN = ROOT / "public/data-v4/manifest.json"
LINKS = ROOT / "scripts/facts_links.json"
OUT = ROOT / "scripts/facts_data.json"
INDEX = ROOT / "index.html"
BEGIN, END = "<!-- facts:begin -->", "<!-- facts:end -->"

EL_NINO = [2002, 2004, 2006, 2009, 2015, 2018, 2023]
LA_NINA = [2007, 2010, 2011, 2020, 2021, 2022]
# fact book (version) values, one place
FACTBOOK = {
    "elnino_means": {"el_nino": 95205, "neutral": 44110, "la_nina": 24278, "ratio_neutral": 2.16, "ratio_others": 2.5, "rank_corr": 0.73, "rank_corr_wo_2015": 0.70, "y2015": 149770},
    "payoff": {"jump_glued": 5.04, "step_scaled": 1.04, "heldout_mean_pct": 5.7, "heldout_worst_pct": 15, "y2012_high_pct": 11},
    "seasons": {"months_apart": 5.9, "mainland_febapr_pct": 75, "indonesia_augoct_pct": 65, "peak_years_of_25": 25, "malaysia_top3_pct": 43},
    # land-use study of this project (re-derived independently on 15 Nov 2026): Sumatra + Kalimantan, forest lost 2002-2011, 275 m forest points;
    # "burned" = a MODIS fire in the loss year or the year before; palm = Descals planting year in the loss year or up to ten years after; other classes = Sims et al. 1 km drivers map.
    # ratio = share among burned-then-cleared / share among cleared-without-fire, all classes kept; [low, high] = 95% range
    "palm_fire": {"palm_burned_pct": 36.1, "palm_unburned_pct": 28.1,
                  "ratios": [["Oil palm", 1.28, 1.19, 1.38], ["Other farming", 0.95, 0.91, 1.00], ["Shifting cultivation", 0.66, 0.57, 0.75], ["Mines and energy", 0.54, 0.44, 0.64], ["Logging", 0.52, 0.44, 0.63]],
                  "ratio_palm_wo_wildfire_class": 1.35},
    "unseen": {"clusters_unseen_pct": 86, "range_pct": [82, 88], "single_share_pct": 57, "single_unseen_pct": 95, "detections_in_seen_clusters_pct": 55, "same_sensor_50min_match_pct": [53, 70]},
}

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def load():
    m = json.loads(MON.read_text())
    months = m["months"]
    def yearly(key, ser):
        out = {}
        for i, mo in enumerate(months):
            v = m["series"][ser][key][i]
            if v is not None: out[int(mo[:4])] = out.get(int(mo[:4]), 0) + v
        return out
    idn = {k: yearly(k, "indonesia") for k in ("modis_raw", "viirs_raw", "viirs_eq")}
    def profile(ser):  # mean over years of each year's share of detections in each calendar month (MODIS, 2001-2025, every year weighted equally)
        by = {}
        for i, mo in enumerate(months):
            y, mm = int(mo[:4]), int(mo[5:]) - 1
            by.setdefault(y, [0] * 12)[mm] += m["series"][ser]["modis_raw"][i] or 0
        ys = [y for y in by if 2001 <= y <= 2025 and sum(by[y]) > 0]
        return [round(100 * sum(by[y][k] / sum(by[y]) for y in ys) / len(ys), 2) for k in range(12)], len(ys)
    prof = {s: profile(s) for s in ("myanmar", "laos", "vietnam", "indonesia")}
    return m, idn, prof

def facts_data():
    m, idn, prof = load()
    years = list(range(2003, 2026))
    glued = [idn["modis_raw"][y] if y <= 2011 else idn["viirs_raw"][y] for y in years]
    scaled = [idn["viirs_eq"][y] for y in years]
    jump = idn["viirs_raw"][2012] / idn["modis_raw"][2011]
    step = idn["viirs_eq"][2012] / idn["viirs_eq"][2011]
    assert round(jump, 2) == FACTBOOK["payoff"]["jump_glued"], jump   # 5.04 (numbers-consistency: 5.039)
    assert round(step, 2) == FACTBOOK["payoff"]["step_scaled"], step   # 1.04 (numbers-consistency: 1.039)
    mod = idn["modis_raw"]; yrs = sorted(mod)
    neutral = [y for y in yrs if y not in EL_NINO and y not in LA_NINA]
    mean = lambda ys: sum(mod[y] for y in ys) / len(ys)
    fb = FACTBOOK["elnino_means"]
    assert (round(mean(EL_NINO)), round(mean(neutral)), round(mean(LA_NINA))) == (fb["el_nino"], fb["neutral"], fb["la_nina"]), (mean(EL_NINO), mean(neutral), mean(LA_NINA))
    assert round(mean(EL_NINO) / mean(neutral), 2) == fb["ratio_neutral"] and round(mean(EL_NINO) / (sum(mod[y] for y in yrs if y not in EL_NINO) / 18), 1) == fb["ratio_others"]
    assert mod[2015] == fb["y2015"] and len(EL_NINO) + len(LA_NINA) + len(neutral) == 25
    man = json.loads(MAN.read_text()); fl = {l["id"]: l for l in man["fire_layers"]["layers"]}; hm = fl["harm"]["harm_meta"]
    months = hm["months_by_region"]["indonesia"]; assert len(months) == 115 and months[0] == "2002-07" and months[-1] == "2012-01" and hm["n_points"] == 608298
    harm = {"n_points": hm["n_points"], "months": len(months), "first": months[0], "last": months[-1], "modis": [fl["modis"]["min"], fl["modis"]["max"]], "viirs": [fl["viirs"]["min"], fl["viirs"]["max"]],
            "note": "manifest.json fire_layers: harm_meta (n_points, months_by_region) and the min/max of the modis and viirs layers; the site data has no per-month point count, so the diagram shows the periods, not monthly counts"}
    return {
        "inputs": {str(MON.relative_to(ROOT)): sha(MON), str(MAN.relative_to(ROOT)): sha(MAN), str(LINKS.relative_to(ROOT)): sha(LINKS)},
        "factbook": FACTBOOK,
        "f1": {"years": years, "glued": glued, "scaled": scaled, "jump_computed": round(jump, 3), "step_computed": round(step, 3), "note": "Indonesia series 'indonesia' of monthly.json, summed per year; glued = MODIS (modis_raw) to 2011 then VIIRS (viirs_raw); scaled = viirs_eq"},
        "f2": {"years": yrs, "modis": [mod[y] for y in yrs], "el_nino": EL_NINO, "la_nina": LA_NINA, "neutral": neutral, "means": {"el_nino": round(mean(EL_NINO)), "neutral": round(mean(neutral)), "la_nina": round(mean(LA_NINA))}},
        "harm": harm,
        "f3": {"share_pct_by_month": {k: v[0] for k, v in prof.items()}, "years_used": {k: v[1] for k, v in prof.items()},
               "febapr_share_pct": {k: round(sum(v[0][1:4]), 1) for k, v in prof.items()}, "augoct_share_pct_indonesia": round(sum(prof["indonesia"][0][7:10]), 1),
               "note": "mean over years of each year's share of MODIS detections in each calendar month (2001-2025, every year equal weight); the fact book's 93 / 92 / 65 % are medians or country-averaged shares, so the card quotes the book, the diagram draws these profiles"},
    }

# ---------------------------------------------------------------- SVG helpers (viewBox 360 wide: text 13 units = about 12.4 px on a 342 px phone card)
W, H = 360, 250
def esc(s): return html.escape(str(s), quote=True)
def txt(x, y, s, cls="", anchor="start"): return f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}"{(" class=" + chr(34) + cls + chr(34)) if cls else ""}>{esc(s)}</text>'
def svg(label, body, desc):
    return (f'<svg class="fx" viewBox="0 0 {W} {H}" role="img" aria-label="{esc(label)}" focusable="false"><title>{esc(label)}</title><desc>{esc(desc)}</desc>{body}</svg>')
def kfmt(v): return "0" if v == 0 else (f"{v/1000:g}k")

def chart1(d):
    L, R, T, B = 44, 10, 34, 26
    ys, g, s = d["years"], d["glued"], d["scaled"]; top = 900000
    X = lambda y: L + (y - ys[0]) * (W - L - R) / (ys[-1] - ys[0]); Y = lambda v: T + (H - T - B) * (1 - v / top)
    o = []
    for t in (0, 300000, 600000, 900000): o.append(f'<line class="gl" x1="{L}" x2="{W-R}" y1="{Y(t):.1f}" y2="{Y(t):.1f}"/>' + txt(L - 5, Y(t) + 4, kfmt(t), "ax", "end"))
    for y in (2003, 2008, 2012, 2017, 2021, 2025): o.append(txt(X(y) + (6 if y == 2025 else 0), H - 8, y, "ax", "end" if y == 2025 else "middle"))
    o.append(f'<line class="brk" x1="{X(2011.5):.1f}" x2="{X(2011.5):.1f}" y1="{T-6}" y2="{H-B}"/>' + txt(X(2011.5) - 5, T + 22, "joined: jumps 5.04×", "ax-fg", "end"))
    pts = lambda vs: " ".join(f"{X(y):.1f},{Y(v):.1f}" for y, v in zip(ys, vs))
    o.append(f'<polyline class="ln-fg" points="{pts(g)}"/>')
    o.append(f'<polyline class="ln-ac" points="{pts(s)}"/>')
    # legend
    o.append(f'<line class="ln-fg" x1="{L}" x2="{L+22}" y1="11" y2="11"/>' + txt(L + 27, 15, "Joined as recorded", "ax") + f'<line class="ln-ac" x1="{L+160}" x2="{L+182}" y1="11" y2="11"/>' + txt(L + 187, 15, "Scaled to VIIRS level", "ax"))
    return svg("Indonesia, detections per year 2003 to 2025: the joined record jumps about 5 times in 2012, the scaled record does not",
               "".join(o), "Two lines. Joined as recorded: low until 2011 (57,427 detections), 289,381 in 2012. Scaled to the VIIRS level: 281,805 in 2011 and 292,852 in 2012. After 2012 both lines are the same VIIRS counts.")

def chart2(d):
    L, R, T, B = 44, 8, 30, 26
    ys, v = d["years"], d["modis"]; top = 150000; n = len(ys)
    bw = (W - L - R) / n
    Y = lambda t: T + (H - T - B) * (1 - t / top)
    o = []
    for t in (0, 50000, 100000, 150000): o.append(f'<line class="gl" x1="{L}" x2="{W-R}" y1="{Y(t):.1f}" y2="{Y(t):.1f}"/>' + txt(L - 5, Y(t) + 4, kfmt(t), "ax", "end"))
    for i, (y, c) in enumerate(zip(ys, v)):
        cls = "bar-ac" if y in d["el_nino"] else "bar-mu"
        o.append(f'<rect class="{cls}" x="{L + i*bw + 1:.1f}" y="{Y(c):.1f}" width="{bw-2:.1f}" height="{Y(0)-Y(c):.1f}"/>')
    for y in (2001, 2005, 2010, 2015, 2020, 2025): o.append(txt(L + (y - ys[0] + .5) * bw + (4 if y == 2025 else 0), H - 8, y, "ax", "end" if y == 2025 else "middle"))
    o.append(txt(L + (2015 - ys[0] + .5) * bw - 4, Y(149770) + 4, "2015: 149,770", "ax", "end"))
    o.append(f'<rect class="bar-ac" x="{L}" y="5" width="10" height="10"/>' + txt(L + 15, 14, "El Niño year", "ax") + f'<rect class="bar-mu" x="{L+100}" y="5" width="10" height="10"/>' + txt(L + 115, 14, "other year", "ax"))
    return svg("Indonesia, MODIS detections per year 2001 to 2025, El Niño years marked",
               "".join(o), "25 bars. The seven El Niño years 2002, 2004, 2006, 2009, 2015, 2018 and 2023 are orange; they average 95,205 detections. The 12 neutral years average 44,110 and the 6 La Niña years 24,278.")

def chart3(d):
    L, R, T, B = 36, 8, 34, 26
    pr = d["share_pct_by_month"]; top = 60
    X = lambda k: L + (k + .5) * (W - L - R) / 12; Y = lambda t: T + (H - T - B) * (1 - t / top)
    cw = (W - L - R) / 12
    o = [f'<rect class="band" x="{L + cw*1:.1f}" y="{T}" width="{cw*3:.1f}" height="{H-T-B}"/><rect class="band" x="{L + cw*7:.1f}" y="{T}" width="{cw*3:.1f}" height="{H-T-B}"/>']
    for t in (0, 25, 50): o.append(f'<line class="gl" x1="{L}" x2="{W-R}" y1="{Y(t):.1f}" y2="{Y(t):.1f}"/>' + txt(L - 5, Y(t) + 4, f"{t}%", "ax", "end"))
    for k, nm in enumerate("JFMAMJJASOND"): o.append(txt(X(k), H - 8, nm, "ax", "middle"))
    pts = lambda vs: " ".join(f"{X(k):.1f},{Y(min(v, top)):.1f}" for k, v in enumerate(vs))
    for s in ("myanmar", "laos", "vietnam"): o.append(f'<polyline class="ln-mu" points="{pts(pr[s])}"/>')
    o.append(f'<polyline class="ln-ac" points="{pts(pr["indonesia"])}"/>')
    o.append(f'<line class="ln-mu" x1="{L}" x2="{L+22}" y1="10" y2="10"/>' + txt(L + 27, 14, "Myanmar, Laos, Vietnam", "ax") + f'<line class="ln-ac" x1="{L+228}" x2="{L+250}" y1="10" y2="10"/>' + txt(L + 255, 14, "Indonesia", "ax"))
    o.append(txt(L + cw * 2.5, T + 12, "Feb–Apr", "ax", "middle") + txt(L + cw * 8.5, T + 12, "Aug–Oct", "ax", "middle"))
    return svg("Share of a year's MODIS detections in each calendar month: Myanmar, Laos and Vietnam peak in Feb to Apr, Indonesia in Aug to Oct",
               "".join(o), "Four lines over twelve months. The three mainland countries rise in February to April and are near zero from June to October. Indonesia is low from January to May and highest in August to October.")

def chart4():
    u = FACTBOOK["unseen"]
    rows = [("All VIIRS fire clusters", u["clusters_unseen_pct"], "no MODIS detection within 2 km, same day"),
            (f"Clusters with one detection ({u['single_share_pct']}% of all)", u["single_unseen_pct"], None),
            ("VIIRS detections, by cluster", 100 - u["detections_in_seen_clusters_pct"], None)]
    L, R = 8, 8; w = W - L - R; o = []
    y0 = 30
    for i, (lab, un, _) in enumerate(rows):
        y = y0 + i * 62
        seen_lab = "MODIS sees it" if i < 2 else "in clusters MODIS sees"
        un_lab = "no MODIS" if i < 2 else "in unseen clusters"
        o.append(txt(L, y - 6, lab, "ax"))
        o.append(f'<rect class="bar-ac" x="{L}" y="{y}" width="{w*un/100:.1f}" height="26"/><rect class="bar-mu" x="{L + w*un/100:.1f}" y="{y}" width="{w*(100-un)/100:.1f}" height="26"/>')
        o.append(txt(L + 6, y + 18, f"{un}%", "on-ac"))
        if 100 - un >= 12: o.append(txt(W - R - 6, y + 18, f"{100-un}%", "on-mu", "end"))
        else: o.append(txt(W - R, y + 44, f"{100-un}% seen", "ax", "end"))
    o.append(f'<rect class="bar-ac" x="{L}" y="{H-24}" width="10" height="10"/>' + txt(L + 15, H - 14, "not seen by MODIS", "ax") + f'<rect class="bar-mu" x="{L+140}" y="{H-24}" width="10" height="10"/>' + txt(L + 155, H - 14, "MODIS detection nearby", "ax"))
    return svg("About 86 percent of VIIRS fire clusters have no MODIS detection within 2 km on the same day",
               "".join(o), "Three bars. All clusters: 86 percent not seen by MODIS, 14 percent seen. Single-detection clusters, which are 57 percent of all clusters: 95 percent not seen. VIIRS detections: 55 percent sit in clusters MODIS sees, 45 percent in clusters it does not.")

def chart5(d):
    h = d; L, R = 8, 10; w = W - L - R
    mi = lambda m: (int(m[:4]) - 2001) * 12 + int(m[5:]) - 1
    X = lambda m, end=False: L + w * (mi(m) + (1 if end else 0)) / 300
    rows = [("MODIS fire detections (real)", h["modis"], "bar-mu", None), ("VIIRS fire detections (real)", h["viirs"], "bar-mu", None), ("Harmonized VIIRS (experimental)", [h["first"], h["last"]], "bar-ac", f"{h['n_points']:,} points, {h['months']} months, night only")]
    o = []
    for y in (2001, 2005, 2010, 2015, 2020, 2025):
        x = L + w * (y - 2001) / 25; o.append(f'<line class="gl" x1="{x:.1f}" x2="{x:.1f}" y1="26" y2="{H-30}"/>' + txt(x if y not in (2001, 2025) else (x if y == 2001 else x + 6), H - 12, y, "ax", "start" if y == 2001 else ("end" if y == 2025 else "middle")))
    for i, (lab, (a, b), cls, extra) in enumerate(rows):
        y = 34 + i * 62
        o.append(txt(L, y - 6, lab, "ax") + f'<rect class="{cls}" x="{X(a):.1f}" y="{y}" width="{X(b, True) - X(a):.1f}" height="24"/>')
        if extra: o.append(txt(L, y + 42, extra, "ax-fg"))
    return svg("Periods of the real MODIS and VIIRS records and of the experimental Harmonized VIIRS layer, 2001 to 2025",
               "".join(o), "Three bars on a 2001 to 2025 axis. MODIS: January 2001 to December 2025. VIIRS: January 2012 to December 2025. Harmonized VIIRS, the experimental model layer: July 2002 to January 2012, 115 months and 608,298 points, night passes only.")

def chart_palm():
    r = FACTBOOK["palm_fire"]["ratios"]; L, R, T = 150, 44, 40; w = W - L - R; top = 1.5
    X = lambda v: L + w * v / top
    o = [f'<line class="brk" x1="{X(1):.1f}" x2="{X(1):.1f}" y1="{T-12}" y2="{H-34}"/>' + txt(X(1), T - 18, "1.0 = same with or without fire", "ax", "middle")]
    for i, (lab, v, lo, hi) in enumerate(r):
        y = T + i * 36
        o.append(txt(L - 8, y + 16, lab, "ax-fg" if i == 0 else "ax", "end"))
        o.append(f'<rect class="{"bar-ac" if i == 0 else "bar-mu"}" x="{L}" y="{y}" width="{X(v) - L:.1f}" height="22"/>')
        o.append(txt((X(1) if 0.8 < v < 1 else X(v)) + 6, y + 16, f"{v:.2f}", "ax-fg" if i == 0 else "ax"))  # a value just under 1.0 is written past the dashed line, not on it
    o.append(txt(L, H - 10, "less often after fire", "ax") + txt(W - R + 40, H - 10, "more often", "ax", "end"))
    return svg("Oil palm is the only land use that is more common where the forest burned before it was cleared",
               "".join(o), "Five bars of a ratio: the share of a land use among forest that burned and was then cleared, divided by its share among forest cleared without fire. Oil palm 1.28, other farming 0.95, shifting cultivation 0.66, mines and energy 0.54, logging 0.52. A dashed line marks 1.0, the same with or without fire.")

# ---------------------------------------------------------------- HTML
def hint_html(link): return f'<p class="muted small fact-hint">{link["hint"]}</p>' if link.get("hint") else ""
def a(link, cls="pill"): return f'<a class="{cls}" href="app/{esc(link["hash"])}" data-fact-link="{esc(link["id"])}">{esc(link["label"])}</a>'

def card(n, title, num, numcap, body, keep, source, fig, figcap, links):
    assert len(links) == 1, "one map link per fact"
    link = links[0]
    act = a(link, "pill solid")
    return f'''<article class="fact two" id="fact-{n}" aria-labelledby="fact-{n}-h">
<div class="stack">
<p class="eyebrow">Fact {n} of 6</p>
<h3 class="disp fact-h" id="fact-{n}-h">{title}</h3>
<p class="fact-num disp" aria-label="{esc(numcap)}">{num}</p>
<p class="body">{body}</p>
<p class="body"><b>What to keep in mind.</b> {keep}</p>
<p class="muted small fact-src">Source: {source}</p>
<p class="ctas fact-act">{act}</p>
{hint_html(link)}
</div>
<figure class="fact-fig">{fig}<figcaption class="muted small">{figcap}</figcaption></figure>
</article>'''

def build_html(d, L):
    lk = {l["id"]: l for l in L["links"]}
    def ls(*ids): return [lk[i] for i in ids]
    c = []
    c.append(card(1, "Joining the MODIS record to the VIIRS record makes a jump of about 5 times", "5.04× → 1.04×", "5.04 times, then 1.04 times",
        "Indonesia's yearly detection count from 2011 to 2012. When the MODIS record is simply joined to the VIIRS record the count jumps 5.04 times in one year. After we scale MODIS to the VIIRS level it changes 1.04 times. On years we left out of the fit, the scaled yearly totals are within about 6% on average (5.7%).",
        "A small step after scaling is expected, because the ratio is fitted on VIIRS levels. Only the held-out years test it: the worst year is off by about 15%, and 2012 itself comes out about 11% too high.",
        "NASA FIRMS MODIS and VIIRS detections (CC0), Indonesia 2003–2025; scaling is our ratio baseline. Details on <a href=\"credits/\">Credits</a>.",
        chart1(d["f1"]), "Indonesia, detections per year. The line “joined as recorded” is MODIS to 2011 and VIIRS from 2012; after 2012 both lines are the same VIIRS counts.",
        ls("f1")))
    c.append(card(2, "Indonesia burns more in El Niño years", "2.16×", "2.16 times",
        "MODIS detections per year in Indonesia, 2001–2025. The 7 El Niño years (Aug–Oct Pacific warmth index of 0.5 or more) average 95,205 detections; the 12 neutral years average 44,110. That is 2.16 times. Against all other years together, which include 6 La Niña years (24,278), it is 2.5 times.",
        "There are only 25 years, and 2015 alone has 149,770 detections; the rank correlation between the index and the yearly count is 0.73 (0.70 without 2015). This is an association, not proof of cause.",
        "NASA FIRMS MODIS detections (CC0); El Niño years from a Pacific warmth index (Aug–Oct, 0.5 or more). Details on <a href=\"credits/\">Credits</a>.",
        chart2(d["f2"]), "Indonesia, MODIS detections per year. Orange bars are the seven El Niño years.",
        ls("f2")))
    c.append(card(3, "Two fire seasons, in opposite halves of the year", "5.9 months", "5.9 months apart",
        "MODIS 2001–2025, each year weighted equally. Myanmar, Laos and Vietnam have their peak month in February to April, in all 25 of 25 years. Indonesia peaks in August to October. On average 75% of the mainland's fire falls in Feb–Apr and 65% of Indonesia's in Aug–Oct. The two peaks are 5.9 months apart; 6 would be exactly opposite.",
        "Cambodia peaks in January–February, and Malaysia is flatter (43% of its fire in its three busiest months). Counts are detections, not burned area.",
        "NASA FIRMS MODIS detections (CC0), 10 countries. Details on <a href=\"credits/\">Credits</a>.",
        chart3(d["f3"]), "Share of a year's MODIS detections in each calendar month, mean over 25 years. Grey bands: Feb–Apr and Aug–Oct.",
        ls("f3")))
    c.append(card(4, "Where forest burned before it was cleared, oil palm followed more often", "36% vs 28%", "36 percent against 28 percent",
        "Sumatra and Kalimantan, forest lost from 2002 to 2011. Where MODIS saw a fire in the year of the loss or the year before, 36.1% of the lost forest was oil palm within ten years. Where it saw no fire, 28.1%. That is 1.28 times as often (range 1.19 to 1.38). Of everything the cleared forest became, oil palm is the only land use that is more common after fire: other farming is the same with or without fire (0.95), and mines (0.54) and logging (0.52) are less common. Across Indonesia, about 24% of the forest lost since 2001 was oil palm by 2021, mostly planted within three years of the loss.",
        "This is an association. It does not show that a fire was set to plant oil palm. “No fire” means no fire seen by MODIS; small or cloud-hidden fires are missed. Most of the difference comes from fire in the year of the loss itself.",
        "Forest loss: Hansen et al. 2013 (CC BY 4.0); oil palm planting year: Descals et al. 2024 (CC BY 4.0); other land uses: Sims et al. 2025 (CC BY 4.0); fires: NASA FIRMS MODIS (CC0). Details on <a href=\"credits/\">Credits</a>.",
        chart_palm(), "How much more or less often each land use follows forest that burned before it was cleared, compared with forest cleared without fire. Sumatra and Kalimantan, forest lost 2002–2011.",
        ls("fp")))
    c.append(card(5, "VIIRS sees small fires that MODIS misses", "86%", "86 percent",
        "of VIIRS fire clusters (2012–2025, 11 countries) have no MODIS detection within 2 km on the same day; the range is 82–88% depending on how clusters are drawn. 57% of clusters are a single detection, and 95% of those are not seen by MODIS.",
        "“Not seen” mixes small fires, a different overpass time and swath coverage; the same VIIRS sensor 50 minutes later matches only 53–70% in Indonesia.",
        "NASA FIRMS MODIS and VIIRS detections (CC0); Harmonized VIIRS is our own model output (CC BY 4.0). Details on <a href=\"credits/\">Credits</a>.",
        chart4(), "VIIRS fire clusters 2012–2025: share with and without a MODIS detection within 2 km on the same day.",
        ls("f4")))
    c.append(card(6, "Our experimental model draws the fires of 2002\u20132011 as VIIRS-style points", "608,298 points", "608,298 points",
        "<b>Harmonized VIIRS</b> is an experimental layer: our own model reads MODIS Aqua night scenes (46,125 of them) and draws where a VIIRS-style sensor would have seen heat. The layer holds 608,298 points over 115 months, from July 2002 to January 2012, night passes only. It is experimental model output, not VIIRS data.",
        "It exists for night passes only and covers Southeast Asia in two areas: Indonesia with its neighbours, and the mainland with the Philippines. Read the <a href=\"paper/technical-report.pdf\" target=\"_blank\" rel=\"noopener\">technical report</a> for how it was made and what we tested.",
        "NASA MODIS Aqua night scenes (LAADS DAAC, NASA open data) and NASA FIRMS MODIS (CC0); the points are our own model output (CC BY 4.0). Details on <a href=\"credits/\">Credits</a>.",
        chart5(d["harm"]), "Periods covered by the real MODIS and VIIRS records and by the experimental Harmonized VIIRS layer. The site data has no point count per month, so the diagram shows periods, not monthly counts.",
        ls("f5")))
    head = '''<section class="band" id="facts" aria-labelledby="facts-h">
<div class="stack">
<p class="eyebrow">Facts we tested</p>
<h2 class="disp" id="facts-h">Six facts about fire in Southeast Asia.</h2>
<p class="body">Each button opens the map at the place, month and layers that show the fact; press Play there to watch it happen. A detection is one hot pixel reported by a satellite; every count here is a count of detections, not of fires.</p>
</div>
'''
    return head + "\n".join(c) + "\n</section>"

def main():
    d = facts_data(); L = json.loads(LINKS.read_text())
    out = json.dumps(d, indent=1, ensure_ascii=False) + "\n"
    block = f"{BEGIN}\n{build_html(d, L)}\n{END}"
    src = INDEX.read_text()
    if BEGIN in src: new = src[:src.index(BEGIN)] + block + src[src.index(END) + len(END):]
    else: raise SystemExit(f"index.html has no {BEGIN} marker")
    if "--check" in sys.argv:
        bad = (OUT.read_text() != out) or (src != new)
        print("facts: up to date" if not bad else "facts: index.html or facts_data.json is out of date, run scripts/build_facts_data.py"); sys.exit(1 if bad else 0)
    OUT.write_text(out); INDEX.write_text(new); print("wrote", OUT.name, "and the facts block of index.html")

if __name__ == "__main__": main()
