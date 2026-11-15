"""Paletted PNG encoder shared by the raster tilers (tiler_sea.py, tiler_mapbiomas_years.py)."""
import io
import numpy as np
from PIL import Image


def png_encode(a, rgb, alpha):
    """a: uint8 palette indices; rgb: list of (r, g, b); alpha: list. The palette is cut to the entries in use."""
    n = max(2, int(a.max()) + 1)
    im = Image.fromarray(a.astype(np.uint8), "P")
    pal = []
    for i in range(n):
        pal += list(rgb[i])
    im.putpalette(pal)
    b = io.BytesIO()
    im.save(b, "PNG", transparency=bytes(alpha[:n]), optimize=True)
    return b.getvalue()
