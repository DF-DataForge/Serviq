/** @odoo-module **/
/*
 * Leaflet (shipped with the module, no CDN) and the tile configuration of
 * the settings, loaded once for every map of the installations.
 */
import { loadCSS, loadJS } from "@web/core/assets";

const LEAFLET = "/serviq_installation_map/static/lib/leaflet/leaflet";
let tilesPromise = null;

export async function loadLeaflet(orm) {
    if (!tilesPromise) {
        tilesPromise = orm.call("serviq.installation", "get_map_tile_config", []);
    }
    const [tiles] = await Promise.all([
        tilesPromise,
        loadCSS(`${LEAFLET}.css`),
        loadJS(`${LEAFLET}.js`),
    ]);
    return { L: window.L, tiles };
}

export function addTileLayer(L, map, tiles) {
    L.tileLayer(tiles.url, {
        attribution: tiles.attribution,
        maxZoom: tiles.maxZoom || 19,
    }).addTo(map);
}

/** Round marker in the colour of the status of the installation. */
export function statusIcon(L, state) {
    return L.divIcon({
        className: "sq-map-marker",
        html: `<div class="sq-map-marker-inner sq-map-state-${state || "none"}"></div>`,
        iconSize: [22, 22],
        iconAnchor: [11, 11],
    });
}

export function escapeHtml(value) {
    return String(value === undefined || value === null ? "" : value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

// Fallback view when nothing is on the map yet (Belgium / the Netherlands).
export const DEFAULT_BOUNDS = [[49.45, 2.5], [53.6, 7.3]];
