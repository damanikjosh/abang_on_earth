/** Layer panel components. Include the stylesheet once:  import "./layerpanel/layerpanel.css";  Nothing here has side effects, so an unused import is dropped by the build. */
export { OnTheMapList, type OnItem, type OnEvents, type OnOptions } from "./onthemap.ts";
export { LayerCatalogue, type CatGroup, type CatLayer, type CatEvents, type CatOptions } from "./catalogue.ts";
export { InfoPopover, type InfoContent, type InfoEvents, type InfoOptions, type LegendItem } from "./infopopover.ts";
export { initialState, activeOrder, setActive, applyActiveOrder, setOpacity, opacityOf, setGroupOpen, setOpenGroups, encodeState, decodeState, clampOpacity, type PanelState, type Defaults, type Decoded, type HashInput } from "./state.ts";
