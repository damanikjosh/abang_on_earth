"""Colours and legends of the MapBiomas conversion-year layers. One source for the tile script and for layers.json.
Three hue families, each a sequential
ramp in lightness (dark = early / small share, light = late / large share) interpolated in CIELAB, so the order is readable
without hue (colour-blind safe, also in grey scale). No red or orange: those belong to the fire layers."""
import numpy as np

# Hue (CIELAB hue angle, degrees) per class, chosen by a search for the largest colour distance between the three classes under normal,
# protan, deutan and tritan vision AND from the 20 colours of the five fire layers: olive-green (oil palm), teal (pulpwood), purple-magenta (mining).
HUES = {"palm": 100, "pulp": 190, "mine": 320}
LSTOPS = (34, 56, 82)      # lightness of the dark / middle / light end
CSTOPS = (36, 46, 30)      # chroma of the dark / middle / light end
YEARS = list(range(2001, 2025))                  # code = year - 2000, 1..24
SHARE_EDGES = [5, 20, 50, 80, 100]              # upper edges (%) of the 5 bins of share variants: (0.5,5] (5,20] (20,50] (50,80] (80,100]
FOREST_EDGES = [20, 40, 60, 80, 100]            # 5 bins of "forest before": 0-19 20-39 40-59 60-79 80-100 %
VARIANTS = ["year", "share", "forest", "in2024"]  # file suffixes and the picker's option ids, in picker order


def _lab(rgb):
    c = np.asarray(rgb, float) / 255; c = np.where(c <= .04045, c / 12.92, ((c + .055) / 1.055) ** 2.4)
    xyz = np.array([[.4124564, .3575761, .1804375], [.2126729, .7151522, .072175], [.0193339, .119192, .9503041]]) @ c / np.array([.95047, 1, 1.08883])
    f = np.where(xyz > .008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.array([116 * f[1] - 16, 500 * (f[0] - f[1]), 200 * (f[1] - f[2])])


def _rgb(lab):
    fy = (lab[0] + 16) / 116; fx = fy + lab[1] / 500; fz = fy - lab[2] / 200
    f = np.array([fx, fy, fz]); xyz = np.where(f ** 3 > .008856, f ** 3, (f - 16 / 116) / 7.787) * np.array([.95047, 1, 1.08883])
    c = np.linalg.inv(np.array([[.4124564, .3575761, .1804375], [.2126729, .7151522, .072175], [.0193339, .119192, .9503041]])) @ xyz
    c = np.clip(c, 0, 1); c = np.where(c <= .0031308, 12.92 * c, 1.055 * c ** (1 / 2.4) - .055)
    return tuple(int(round(v * 255)) for v in c)


def hex2rgb(h): return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))
def rgb2hex(c): return "#%02x%02x%02x" % tuple(c)


def ramp(cls, n):
    """n colours from dark to light (Lab-interpolated through the middle anchor)."""
    h = np.radians(HUES[cls]); a = [np.array([L, C * np.cos(h), C * np.sin(h)]) for L, C in zip(LSTOPS, CSTOPS)]
    out = []
    for i in range(n):
        t = i / (n - 1) if n > 1 else 0.5
        lab = a[0] + (a[1] - a[0]) * (t / .5) if t <= .5 else a[1] + (a[2] - a[1]) * ((t - .5) / .5)
        out.append(_rgb(lab))
    return out


def legend(cls, variant):
    """Legend entries [(hex, label)] of a variant; for the year variant 24 colours are in the tiles, the legend lists 5 key years."""
    if variant == "year":
        r = ramp(cls, len(YEARS)); return [(rgb2hex(r[YEARS.index(y)]), str(y)) for y in (2001, 2006, 2012, 2018, 2024)]
    r = ramp(cls, 5)
    if variant == "forest":
        lab = ["0-19 %", "20-39 %", "40-59 %", "60-79 %", "80-100 %"]
    else:
        lab = ["1-5 %", "6-20 %", "21-50 %", "51-80 %", "81-100 %"]
    return [(rgb2hex(c), l) for c, l in zip(r, lab)]


def palette(cls, variant):
    """(rgb list, alpha list) of the PNG palette: index 0 transparent."""
    r = ramp(cls, len(YEARS) if variant == "year" else 5)
    return [(0, 0, 0)] + r, [0] + [255] * len(r)


def encode_index(variant, a, w):
    """a, w float32 arrays (value, presence weight) -> uint8 palette index (0 = nothing)."""
    idx = np.zeros(a.shape, np.uint8)
    if variant == "year":
        idx[w > 0] = np.clip(np.rint(a[w > 0]), 1, len(YEARS)).astype(np.uint8)
    elif variant == "forest":
        m = w > 0; idx[m] = 1 + np.minimum(4, np.floor(a[m] / 20)).astype(np.uint8)
    else:  # share, in2024
        m = a >= 0.5
        idx[m] = 1 + np.searchsorted(np.array(SHARE_EDGES[:-1], float), a[m], side="left").astype(np.uint8)
    return idx
