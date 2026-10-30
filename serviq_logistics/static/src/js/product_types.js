/** @odoo-module **/

// Shared product type categorisation for all logistic dashboards: the
// product type of a product is the code of its component role
// (serviq.component.role); order and labels follow the roles (sequence,
// name), products without role are "none" ("Niet ingedeeld", last). The
// badge colours are assigned from a fixed palette in role order. A
// dashboard uses it with `Object.assign(MyDashboard.prototype,
// productTypeMethods)` and keeps `state.typeFilter` ("" = all); the
// templates TypeChips / TypeCardHead in product_types.xml rely on these
// methods. The roles are loaded by loadFilterOptions (filter_options.js).

import { filterOptions } from "./filter_options";

const NONE = "none";
const PALETTE_SIZE = 8;

/** Type keys in display order: the roles by sequence, "none" last. */
export function typeOrder() {
    const keys = filterOptions.types.map((t) => t.key).filter((k) => k !== NONE);
    return [...keys, NONE];
}

/** Type key of a product dict ({product_type}); "none" without type. */
export function typeKey(item) {
    return (item && (item.product_type || item.ptype)) || NONE;
}

function typeRank(key) {
    const order = typeOrder();
    const i = order.indexOf(key);
    return i === -1 ? order.length - 1 : i;
}

/** Sort type groups: role order, products without type last. */
export function sortTypes(groups) {
    return groups.sort((a, b) => typeRank(a.key) - typeRank(b.key)
        || String(a.label).localeCompare(String(b.label)));
}

/**
 * Group `items` per product type: [{key, label, items, count}].
 * keyOf(item) returns the type key (default typeKey).
 */
export function groupByType(items, keyOf = typeKey) {
    const groups = {};
    for (const item of items) {
        const key = keyOf(item);
        const g = groups[key] || (groups[key] = { key, label: typeLabel(key), items: [], count: 0 });
        g.items.push(item);
        g.count += 1;
    }
    return sortTypes(Object.values(groups));
}

export function typeLabel(key) {
    key = key || NONE;
    const type = filterOptions.types.find((t) => t.key === key);
    if (type) return type.label;
    return key === NONE ? "Niet ingedeeld" : key;
}

/** Badge colour class: a palette colour per role (in role order), grey
 *  for products without role. */
export function typeClass(key) {
    if (!key || key === NONE) return "sq-type-none";
    const i = typeOrder().indexOf(key);
    return i === -1 ? "sq-type-none" : `sq-type-c${i % PALETTE_SIZE}`;
}

/** Chips for the type filter: one per type present in `items` (with count). */
export function typeOptions(items, keyOf = typeKey) {
    return groupByType(items, keyOf).map((g) => ({ key: g.key, label: g.label, count: g.count }));
}

export const productTypeMethods = {
    typeKey(item) {
        return typeKey(item);
    },
    getProductTypeLabel(ptype) {
        return typeLabel(ptype || NONE);
    },
    getProductTypeClass(ptype) {
        return typeClass(ptype);
    },
    /** "1 product" / "3 producten" */
    countLabel(n, one, many) {
        return `${n} ${n === 1 ? one : many}`;
    },
    onTypeFilter(key) {
        this.state.typeFilter = this.state.typeFilter === key ? "" : key;
    },
    /** Does `item` (or a list of type keys) match the active type filter? */
    matchesType(item) {
        const f = this.state.typeFilter;
        if (!f) return true;
        if (Array.isArray(item)) return item.includes(f);
        return typeKey(item) === f;
    },
};

/** Chips for items that carry several types (orders, deliveries):
 *  keysOf(item) returns the item's type keys; count = items per type. */
export function typeOptionsMulti(items, keysOf = (item) => item.product_types || []) {
    const counts = {};
    for (const item of items) {
        for (const key of new Set(keysOf(item))) counts[key] = (counts[key] || 0) + 1;
    }
    return sortTypes(Object.keys(counts).map((key) => ({ key, label: typeLabel(key), count: counts[key] })));
}
