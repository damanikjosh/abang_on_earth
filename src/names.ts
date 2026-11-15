/** Display names for regions. regions.geojson keeps geoBoundaries' shapeName as delivered (ids and series do not change); this tidies what people read:
 *  Thai/Cambodian " Province" suffix dropped, ALL-CAPS names (Singapore's planning regions) in capitals-and-lowercase, one known misspelling fixed.
 *  Acronyms of 4 letters or fewer (ARMM, CAR, NCR) are left as the source has them: expanding them would be a guess. */
const FIX: Record<string, string> = { Saigang: "Sagaing" }; // Myanmar's Sagaing Region; geoBoundaries spells it "Saigang"
export function displayName(raw: string): string {
  let n = raw.replace(/\s+/g, " ").trim();
  n = n.replace(/ Province$/, "");
  if (n.length > 4 && n === n.toUpperCase() && /[A-Z]/.test(n)) n = n.toLowerCase().replace(/(^|[\s-])(\p{L})/gu, (_, a: string, b: string) => a + b.toUpperCase());
  return FIX[n] ?? n;
}
