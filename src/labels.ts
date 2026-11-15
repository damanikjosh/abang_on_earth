/** User-visible text for the forest-loss-fire layers (internal ids clrm/clrv, flag `clearing` and keys *_clearing are unchanged: saved links and data use them). */
export const FOREST_LOSS_FIRE_LEGEND = "Fire detections on forest that was lost in the same year or the next. This includes forest destroyed by the fire itself; it is not proof of land clearing.";
/** The data files still say "clearing fires"; show the correct wording whatever they contain. */
export function forestLossFire<T extends { label: string; legend: string; clearing?: boolean }>(d: T): T {
  return d.clearing ? { ...d, label: d.label.replace(/clearing fires/i, "forest-loss fires"), legend: FOREST_LOSS_FIRE_LEGEND } : d;
}
