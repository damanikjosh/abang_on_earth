/** Catalogue groups of the layer list: which row belongs to which group, in what order, and which rows are not listed at all.
 *  Row ids are the app's row ids: context layers as in layers.json, fire layers "fire-<id>" (manifest fire_layers), the metric colour overlay "regions".
 *  A row that is in no group falls into the catalogue's automatic "Other" group, so a new layer never disappears. */
export interface GroupDef { id: string; label: string; description: string; layers: string[] }
export const GROUPS: GroupDef[] = [
  { id: "fires", label: "Fire detections", description: "MODIS and VIIRS fire detections, observed and harmonized", layers: ["fire-viirs", "fire-modis", "fire-harm"] },
  { id: "colour", label: "Fire counts by region", description: "Provinces and countries coloured by the fire count of the selected month", layers: ["countries", "regions"] },
  { id: "land", label: "Forest and land", description: "Forest loss, what cleared forest became, peatland", layers: ["loss", "drivers", "peat"] },
  { id: "plant", label: "Plantations and mines", description: "Oil palm, and the year land became oil palm, pulpwood or mining", layers: ["palm", "mb_palm", "mb_pulp", "mb_mine"] },
  { id: "more", label: "More data", description: "Forest history, converted plantation, burned area", layers: ["tmfdef", "tmfdeg", "plantation", "burned"] },
];
/** Placeholder rows (synthetic stand-ins, no real data): not shown in the list. Data files stay as they are; delete an id here to show the row again. */
export const HIDDEN_ROWS: string[] = ["alerts", "pulp"];
/** Rows taken out of the app (the forest-loss fires clrm and clrv, then loss_palm and mines). Their tiles and layers.json entries stay on disk; old links that name them are ignored. Delete the ids here and the filter in app.ts to bring them back. */
export const REMOVED_ROWS: string[] = ["fire-clrm", "fire-clrv", "loss_palm", "mines"]; // + "Forest loss then oil palm" and "Mines (about 2019)" (layers.json entries and tiles stay)
export const DEFAULT_OPEN: string[] = ["fires", "colour"];
export const groupOfRow = (id: string): string | undefined => GROUPS.find((g) => g.layers.includes(id))?.id;
