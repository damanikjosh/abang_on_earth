# Abang on Earth

A map of MODIS and VIIRS fire detections across Southeast Asia, 2001 to today, with the forest loss, oil palm, peat, burned area and plantation layers underneath, month by month. Static site: Vite, TypeScript, MapLibre GL JS, PMTiles. No server, no trackers, no cookies.

- `/` homepage, `/app/` the map and month calendar, `/credits/` sources and licences.
- `public/data-v4/` is the complete data the site loads: JSON for the regional counts and the layer catalogue, and one PMTiles file per layer and month or year. Nothing else is loaded; `scripts/check_data_used.py` proves it (below).

## Requirements
Node 22 (LTS) and npm. For the checks: Python 3.12 and [uv](https://docs.astral.sh/uv/).

## Commands
```
npm ci
npm test                  # unit tests (node --test)
npm run build             # type-check + build to dist/
npm run preview           # serve dist/ at http://127.0.0.1:4173/ (HTTP Range supported, as tile files need)
npm run dev               # dev server
```
The site is built for the domain root (`base` `/`). For a project Pages URL build with `BASE=/abang_on_earth/ npm run build`; all links are relative and data is fetched through `import.meta.env.BASE_URL`.

## Verification
Against a served build (`npm run build && npm run preview`):
```
python3 scripts/check_data_used.py                   # every file under public/ is used by the site, and every referenced file exists
uvx playwright install chromium                      # once
python3 scripts/run_checks.py http://127.0.0.1:4173/ # the browser checks, one PASS/FAIL line each
uv run --with playwright python scripts/crawl_requests.py http://127.0.0.1:4173/ /tmp/requests.log
python3 scripts/check_data_used.py --crawl /tmp/requests.log   # the crawl requested nothing outside the used set
```
- `check_data_used.py` is the static proof: a file counts as used when a page links it, the data manifest or `layers.json` names it, or it is a tile file of a layer row that the app lists (rows in `HIDDEN_ROWS` and `REMOVED_ROWS` of `src/layergroups.ts`, and placeholder rows, are not counted). Files the homepage links, such as `public/paper/*` and later `public/deck/*`, count as used automatically.
- `crawl_requests.py` is a sample that confirms it in a browser: every listed layer row with all its classes and variants, the slider at a spread of years and months, every fire layer, the Details tab. `--all-months` steps through every month.
- `check_smoke.py` is the quick test (about two minutes): the pages load, every layer row is on for three months without a failed request, Harmonized VIIRS, MapBiomas and the overlays draw, no console errors, the report row works. It also runs against the live site: `uv run --with playwright --with pillow --with numpy python scripts/check_smoke.py https://abang.earth/`.
- `run_checks.py` runs the smoke test and then the scripts `scripts/check_*.py` (layer panel, share links, keyboard path, phone layout, load failures, tiles answer HTTP Range, harmonized layer, day and night boxes, MapBiomas rows, basemap, homepage, paper row).

## Data
`public/data-version.json` points the app at the data folder (`data-v4/`). `DATA_LICENSES.md` lists every file group with its source and licence. What the groups are derived from:

| Files | Derived from |
|---|---|
| `fire/modis*`, `fire/viirs*`, `monthly.json`, `annual.json`, `manifest.json` | NASA FIRMS active-fire detections, counted per region and month |
| `fire/harm/` | model output: VIIRS-like night points predicted from MODIS night passes, 2002 to 2012 (experimental) |
| `regions.geojson`, `borders.geojson`, `country-outlines.geojson` | geoBoundaries first-level administrative boundaries, simplified |
| `forest-loss/`, `oilpalm/`, `burned-area/`, `tmf/`, `peat/`, `drivers/`, `mapbiomas/`, `mines/` | Hansen forest loss, Descals oil palm, MCD64A1, JRC TMF, CIFOR peat, forest-loss drivers, MapBiomas Indonesia, mining polygons |

The processing that turns the raw FIRMS archive, the Hansen and Descals rasters and the model output into these files needs hundreds of gigabytes and is not included. The scripts that turn public inputs into tiles are:

| Script | Input | Output |
|---|---|---|
| `tools/layers/tiler_sea.py LAYER OUTDIR NPROC BBOX SRC_GLOB` | GeoTIFFs: burned mask, Hansen lossyear, Descals planting year, peat, drivers classes | yearly or static PMTiles (`forest-loss/`, `oilpalm/`, `burned-area/`, `peat/`, `drivers/`) |
| `scripts/make_drivers_class.py` | Sims et al. drivers GeoTIFF + Hansen lossyear tiles | the class raster for `drivers/` |
| `tools/layers/tiler_mapbiomas_years.py` | 0.001 degree MapBiomas conversion-year rasters | `mapbiomas/<class>_<year>.pmtiles` (palette: `tools/layers/mb_palette.py`) |
| `scripts/build_mines.py` | Maus et al. mining polygons (GeoPackage) + commodity CSV | `mines/mines.geojson` |
| `scripts/build_borders.py` | `regions.geojson` | `borders.geojson`, `country-outlines.geojson` |
These are not run by the checks; they are provided so the layer files can be rebuilt from the public sources.

## Technical report and demo deck
The homepage has a row for the technical report. Its source lives in another repository; only the built PDF, a page-1 thumbnail and a small JSON are shipped, in `public/paper/`, written by
```
uv run --with pypdfium2 --with pillow python scripts/sync_paper.py PATH/TO/report.pdf
uv run --with reportlab --with pypdfium2 --with pillow python scripts/test_sync_paper.py   # tests the script
```
The demo deck will follow the same pattern in `public/deck/` (`deck.pdf`, `deck.pptx`, a thumbnail), linked from the homepage. Any file a page links counts as used for `check_data_used.py`, so no change to the proof is needed.

## Deployment
`.github/workflows/pages.yml` runs the unit tests and the used-files proof, builds and publishes `dist/` with GitHub Pages on every push to `main` (and manually, with an optional `base` input for a project URL). The workflow does not set a custom domain: that is a repository setting, and a `CNAME` file is added only when the domain is attached. The published site must stay under 1 GB; data is plain git, no Git LFS.

## Licences
- Code licence: TODO(owner): choose a licence before this repository is made public. No LICENSE file is present on purpose.
- Data: see `DATA_LICENSES.md`. Several groups are share-alike (ODbL 1.0, CC BY-SA), so those files must stay under those terms.
- Fonts (Inter, Space Grotesk, SIL OFL 1.1) and libraries come from `package-lock.json`; none is GPL or AGPL.
