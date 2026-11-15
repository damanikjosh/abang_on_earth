# Data licences

Every file under `public/` by group, with the source it is derived from and the licence that source gives. Each derived file keeps the attribution below; the credits page of the site (`credits/index.html`) shows the same sources to visitors. Several groups are share-alike: those files must stay under the stated terms wherever they are copied.

| Files | Source | Source licence | Terms for the files here |
|---|---|---|---|
| `data-v4/fire/modis*/`, `data-v4/fire/viirs*/`, `data-v4/monthly.json`, `data-v4/annual.json` (fire counts) | NASA FIRMS archive: MODIS Collection 6.1 active fires (MOD14, MYD14), VIIRS S-NPP 375 m active fires (VNP14IMG), filtered (types 1-3 dropped, MODIS confidence below 30 and VIIRS low confidence dropped) | NASA open data, CC0 | derived tiles and counts; NASA FIRMS acknowledgement kept on the credits page |
| `data-v4/fire/harm/` | Model output computed from MODIS Aqua (MYD021KM, MYD03, MYD14 mask classes, LAADS DAAC) | MODIS data: NASA open data. The model and its output are the owner's work | CC BY 4.0 (author's own work). Attribution: "Abang on Earth, Joshua Julian Damanik, 2026, CC BY 4.0"; acknowledge NASA LAADS DAAC as the source of the MODIS input (NASA open data) |
| `data-v4/regions.geojson`, `data-v4/borders.geojson`, `data-v4/country-outlines.geojson` | geoBoundaries gbOpen ADM1 (Runfola et al. 2020, PLoS ONE 15(4):e0231866), simplified; OpenStreetMap-based for Indonesia and Malaysia | per country as listed by geoBoundaries: ODbL 1.0 (Indonesia, Malaysia, Singapore, Thailand, Cambodia, Laos, Timor-Leste), CC BY 4.0 (Myanmar), CC BY 3.0 IGO (Philippines), public domain (Vietnam, Brunei) | share-alike: the region geometry is offered under ODbL 1.0, (c) OpenStreetMap contributors where the source is OpenStreetMap |
| `data-v4/manifest.json`, `data-v4/layers.json` catalogue and per-layer text; the site pages' written content | written for this project | n/a | CC BY 4.0 (author), attribution "Abang on Earth, Joshua Julian Damanik, 2026, CC BY 4.0"; text quoting a source keeps that source's terms |
| `data-v4/forest-loss/` | Hansen et al. 2013, Global Forest Change v1.13, Science 342:850 | CC BY 4.0 | derived tiles, attribution |
| `data-v4/oilpalm/` | Descals et al. 2024, ESSD 16:5111, Zenodo 10.5281/zenodo.13379129 | CC BY 4.0 | derived tiles, attribution |
| `data-v4/burned-area/`, `data-v4/burned-area.json` | MODIS/Terra+Aqua Burned Area MCD64A1 v6.1, doi:10.5067/MODIS/MCD64A1.061 | NASA, no use restrictions | derived tiles and aggregates |
| `data-v4/tmf/`, `data-v4/tmf.json` | JRC Tropical Moist Forests v1.2025, Vancutsem et al. 2021, Science Advances 7:eabe1603 | free use with attribution ("Source: EC JRC"); no endorsement by the European Commission | derived tiles and aggregates |
| `data-v4/peat/`, `data-v4/peat.json` | Gumbricht et al. 2017, Tropical and subtropical wetlands distribution v2.1, CIFOR, doi:10.17528/CIFOR/DATA.00058 | CC BY 4.0 | derived tiles and aggregates |
| `data-v4/drivers/` | Sims et al. 2025, Global drivers of forest loss at 1 km resolution, v1.3, Zenodo 10.5281/zenodo.19485190 | CC BY 4.0 | derived tiles, attribution |
| `data-v4/mines/mines.geojson` | Maus et al. 2024 mining polygons (with OpenStreetMap), Zenodo 10.5281/zenodo.7307210 | ODbL 1.0 | share-alike: offered under ODbL 1.0, (c) OpenStreetMap contributors |
| `data-v4/mapbiomas/` | MapBiomas Indonesia Collection 4 (version 2), via landy.mapbiomas.id | CC BY-SA (MapBiomas terms of use) | share-alike: the derived tiles are offered under CC BY-SA; see `data-v4/mapbiomas/ATTRIBUTION.txt` |
| `data-v4/annual.json`, `data-v4/monthly.json` region series for Hansen / Descals / peat / TMF statistics | aggregates of the sources above | as above | derived |
| `paper/` | the author's technical report (PDF, thumbnail, metadata) | n/a | CC BY 4.0, attribution as above; figures that reproduce third-party data stay under those licences |
| `team/joshua.jpg` | portrait of the site author | used with the permission of the pictured person | not covered by the CC BY 4.0 grant above; reuse needs the pictured person's permission |
| `home-app.jpg` | screenshot of this application | n/a | CC BY 4.0 (our own figure); the map data visible in it keeps the source licences above |

Not stored here, loaded at run time: the OpenFreeMap basemap (OpenMapTiles schema BSD / CC BY 4.0 design, map data (c) OpenStreetMap contributors, ODbL) and NASA GIBS Blue Marble imagery for the satellite view (NASA open data, CC0). Fonts (Inter, Space Grotesk, SIL OFL 1.1) are bundled into the build through Fontsource.
