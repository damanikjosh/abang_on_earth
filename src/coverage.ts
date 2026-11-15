/** Per-country "no data for this layer here" labels. A layer def (layers.json layers[] or manifest fire_layers.layers[]) may carry
 *  `coverage: ["IDN","MYS"]` (ISO-3 codes where it has data) and `gap_note` (text to show elsewhere). No `coverage` = covers everywhere, so
 *  today's Indonesia-only manifests show nothing. A region's country is regions.geojson properties.country (default IDN). */
export interface Covered { coverage?: string[]; gap_note?: string; region_gaps?: Record<string, string> }
export const DEFAULT_COUNTRY = "IDN";
export const DEFAULT_GAP = "No data for this layer in this country";
export const countryOf = (props?: { country?: string } | null): string => props?.country || DEFAULT_COUNTRY;
export const covered = (d: Covered, cc: string): boolean => !d.coverage || d.coverage.includes(cc);
/** "" when the layer has data for `cc`, otherwise the note to show in the layer row. */
export const gapNote = (d: Covered, cc: string): string => (covered(d, cc) ? "" : d.gap_note || DEFAULT_GAP);
