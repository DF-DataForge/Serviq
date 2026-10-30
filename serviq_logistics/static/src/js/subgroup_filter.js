/** @odoo-module **/

// Shared segment filter (installation categories) for all logistic
// dashboards. The chosen value is stored in localStorage so the filter
// follows the user throughout the whole dashboard application. The
// segments come from the server (see filter_options.js); "all" shows
// every product.

import { filterOptions } from "./filter_options";

const STORAGE_KEY = "serviq_logistics.subgroup";

function validValues() {
    return ["all", ...filterOptions.segments.map((s) => s.value)];
}

/** Buttons of the segment filter: "all" first, then one per category. */
export function subgroupOptions() {
    return [
        { value: "all", label: "Alle producten", icon: "" },
        ...filterOptions.segments.map((s) => ({ value: s.value, label: s.label, icon: "fa-tag" })),
    ];
}

export function subgroupLabel(value) {
    const seg = filterOptions.segments.find((s) => s.value === value);
    return seg ? seg.label : "";
}

/** The stored segment, or "all" when unknown (call after loadFilterOptions). */
export function getStoredSubgroup() {
    try {
        const value = window.localStorage.getItem(STORAGE_KEY);
        return validValues().includes(value) ? value : "all";
    } catch {
        return "all";
    }
}

export function setStoredSubgroup(value) {
    try {
        window.localStorage.setItem(STORAGE_KEY, validValues().includes(value) ? value : "all");
    } catch {
        // localStorage unavailable (private mode) - filter just won't persist
    }
}

/** Methods for the SegmentFilter template, mixed into the dashboards with
 *  Object.assign(MyDashboard.prototype, segmentFilterMethods). The
 *  component implements onSubgroupClick(value). */
export const segmentFilterMethods = {
    segmentOptions() {
        return subgroupOptions();
    },
    hasSegments() {
        return filterOptions.segments.length > 0;
    },
    getSubgroupLabel(value) {
        return subgroupLabel(value);
    },
};
