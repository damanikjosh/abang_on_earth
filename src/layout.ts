/** One definition of the two layouts. Keep in step with the media queries in app.css (same numbers).
 *  FLOATING (wide screens with a mouse): three floating panels around the map; needs >= 1200 px width AND >= 601 px height AND a fine pointer (at 1024 px the map between the panels was 370 px wide).
 *  DOCK (everything else: phones, tablets in both orientations, short windows): one bottom sheet with tabs; on a short landscape screen (<= 480 px high) it becomes a left side sheet. */
export const DOCK_QUERY = "(max-width: 1199px), (max-height: 600px), (pointer: coarse)"; // touch devices always get the dock and its 44 px targets, whatever their size
export const SIDE_QUERY = "(max-height: 480px) and (min-width: 600px)";
/** Narrow screens only: the top bar collapses into a Menu button (old phone rule, unchanged: 480 px wide or 560 px high). */
export const NARROW_QUERY = "(max-width: 480px), (max-height: 560px)";
export const isDockLayout = (): boolean => matchMedia(DOCK_QUERY).matches;
export const isSideLayout = (): boolean => matchMedia(DOCK_QUERY).matches && matchMedia(SIDE_QUERY).matches;
