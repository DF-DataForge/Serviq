/** @odoo-module **/
/*
 * Standard installation filters - category, installer and distributor -
 * shared by the overview dashboard (with its map panel and planning
 * calendar), the hours overview and the kanban and list views of
 * installations. The choice is remembered per browser, so it carries over
 * from one screen to the next.
 */
import { Component, onWillStart, useState } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { useService } from "@web/core/utils/hooks";

const STORAGE_KEY = "serviq_installation_filters";

export const EMPTY_FILTERS = Object.freeze({ category: "", installer: "", distributor: "" });

export function loadSystemFilters() {
    try {
        const stored = JSON.parse(browser.localStorage.getItem(STORAGE_KEY) || "{}");
        const filters = { ...EMPTY_FILTERS };
        for (const key of Object.keys(EMPTY_FILTERS)) {
            if (stored[key]) {
                filters[key] = String(stored[key]);
            }
        }
        return filters;
    } catch {
        return { ...EMPTY_FILTERS };
    }
}

export function saveSystemFilters(filters) {
    try {
        browser.localStorage.setItem(STORAGE_KEY, JSON.stringify(filters));
    } catch {
        // Private mode or blocked storage: the choice is not remembered.
    }
}

export function hasSystemFilters(filters) {
    return Object.values(filters || {}).some((value) => value);
}

/** Installation domain of the filters (same as the server's
 *  serviq.installation._system_filter_domain). */
export function systemFiltersDomain(filters) {
    const { category, installer, distributor } = filters || {};
    const domain = [];
    if (category) {
        domain.push(["category_id", "=", parseInt(category)]);
    }
    if (installer === "none") {
        domain.push(["installer_id", "=", false]);
    } else if (installer) {
        domain.push(["installer_id", "=", parseInt(installer)]);
    }
    if (distributor) {
        domain.push(["distributor_id", "=", parseInt(distributor)]);
    }
    return domain;
}

export class SystemFilterBar extends Component {
    static template = "serviq_installation.SystemFilterBar";
    static props = {
        filters: Object,
        onChange: Function,
    };

    setup() {
        this.orm = useService("orm");
        this.options = useState({ categories: [], installers: [], distributors: [] });
        onWillStart(async () => {
            Object.assign(
                this.options,
                await this.orm.call("serviq.installation", "get_system_filter_options", [])
            );
        });
    }

    get active() {
        return hasSystemFilters(this.props.filters);
    }

    onFilterChange(key, ev) {
        const filters = { ...this.props.filters, [key]: ev.target.value };
        saveSystemFilters(filters);
        this.props.onChange(filters);
    }

    clear() {
        const filters = { ...EMPTY_FILTERS };
        saveSystemFilters(filters);
        this.props.onChange(filters);
    }
}
