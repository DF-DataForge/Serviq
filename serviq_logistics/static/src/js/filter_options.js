/** @odoo-module **/

// Filter options shared by all logistic dashboards, loaded from the
// server (serviq.logistics.meta): the segments (installation categories)
// and the product types (component roles). Nothing is hardcoded: the
// dashboards follow the categories and roles configured in Installaties.
// Every dashboard calls loadFilterOptions() in onWillStart, so changes to
// the categories / roles show on the next opening.

export const filterOptions = {
    segments: [],  // [{value, label}] ordered by sequence
    types: [],  // [{key, label, spare}] ordered by sequence, "none" last
};

export async function loadFilterOptions(orm) {
    try {
        const res = await orm.call("serviq.logistics.meta", "get_filter_options", []);
        filterOptions.segments = res.segments || [];
        filterOptions.types = res.types || [];
    } catch {
        // keep the previous (or empty) options: the dashboards still work,
        // types just show their key
    }
    return filterOptions;
}
