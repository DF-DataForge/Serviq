/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadFilterOptions } from "./filter_options";
import { getStoredSubgroup, segmentFilterMethods, setStoredSubgroup } from "./subgroup_filter";
import { productTypeMethods, sortTypes, typeOptions } from "./product_types";
import { openStockCards } from "./stock_cards";

class StockDashboard extends Component {
    static template = "serviq_logistics.StockDashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        this.state = useState({
            activeTab: "own",
            viewMode: "type",  // "type" (cards), "product" or "location"
            typeFilter: "",  // product type key, "none" = no type
            locationGroup: null,  // location view: the aisle card opened (group_id)
            loading: true,
            searchTerm: "",
            subgroup: getStoredSubgroup(),
            summary: { own: {}, consignment: {}, customer: {} },
            products: [],
            locations: [],
            expandedProducts: {},
            expandedLocations: {},
        });

        onWillStart(async () => {
            await loadFilterOptions(this.orm);
            this.state.subgroup = getStoredSubgroup();
            await this.loadSummary();
            await this.loadTabData();
        });
    }

    async loadSummary() {
        this.state.summary = await this.orm.call(
            "serviq.logistics.stock",
            "get_dashboard_summary",
            [this.state.subgroup]
        );
    }

    async loadTabData() {
        this.state.loading = true;
        this.state.expandedProducts = {};
        this.state.expandedLocations = {};
        this.state.locationGroup = null;
        const searchTerm = this.state.searchTerm || false;

        if (this.state.viewMode !== "location") {
            this.state.products = await this.orm.call(
                "serviq.logistics.stock",
                "get_dashboard_data",
                [this.state.activeTab, searchTerm, this.state.subgroup]
            );
            this.state.locations = [];
        } else {
            this.state.locations = await this.orm.call(
                "serviq.logistics.stock",
                "get_dashboard_data_by_location",
                [this.state.activeTab, searchTerm, this.state.subgroup]
            );
            this.state.products = [];
        }
        this.state.loading = false;
    }

    async onSubgroupClick(subgroup) {
        if (this.state.subgroup === subgroup) return;
        this.state.subgroup = subgroup;
        setStoredSubgroup(subgroup);
        await this.loadSummary();
        await this.loadTabData();
    }

    async onTabClick(tab) {
        if (this.state.activeTab === tab) return;
        this.state.activeTab = tab;
        await this.loadTabData();
    }

    async onViewModeChange(mode) {
        if (this.state.viewMode === mode) return;
        const sameData = mode !== "location" && this.state.viewMode !== "location";
        this.state.viewMode = mode;
        this.state.locationGroup = null;
        if (mode === "type") this.state.typeFilter = "";
        // the type cards and the product list use the same data
        if (!sameData) await this.loadTabData();
    }

    // ------- product type categorisation -------
    /** One card per product type of the current tab (type view). */
    get typeCards() {
        const groups = {};
        for (const p of this.state.products) {
            const key = this.typeKey(p);
            const g = groups[key] || (groups[key] = {
                key, label: this.getProductTypeLabel(p.product_type),
                product_count: 0, total_qty: 0, reserved_qty: 0, serial_count: 0, top: [],
            });
            g.product_count += 1;
            g.total_qty += p.total_qty;
            g.reserved_qty += p.reserved_qty || 0;
            g.serial_count += p.serial_count;
            g.top.push(p);
        }
        return sortTypes(Object.values(groups).map((g) => ({
            ...g,
            available_qty: g.total_qty - g.reserved_qty,
            top: g.top.sort((a, b) => b.total_qty - a.total_qty).slice(0, 3),
        })));
    }

    /** Type chips for the product and location views, with counts. */
    get typeOptions() {
        return typeOptions(this.state.viewMode === "location"
            ? this.state.locations.flatMap((l) => l.products)
            : this.state.products);
    }

    get visibleProducts() {
        const f = this.state.typeFilter;
        return f ? this.state.products.filter((p) => this.typeKey(p) === f) : this.state.products;
    }

    get visibleLocations() {
        const f = this.state.typeFilter;
        if (!f) return this.state.locations;
        const result = [];
        for (const loc of this.state.locations) {
            const products = loc.products.filter((p) => this.typeKey(p) === f);
            if (!products.length) continue;
            result.push({
                ...loc,
                products,
                product_count: products.length,
                total_qty: products.reduce((a, p) => a + p.qty, 0),
                serial_count: products.reduce((a, p) => a + p.serial_numbers.length, 0),
            });
        }
        return result;
    }

    // ------- location view: cards per warehouse aisle ("gang") -------
    /** Sections per warehouse (own main warehouse first), each with one
     *  card per aisle / first-level location. */
    get locationSections() {
        const cards = {};
        for (const loc of this.visibleLocations) {
            const key = loc.group_id || loc.location_id;
            const c = cards[key] || (cards[key] = {
                key,
                name: loc.group_short || loc.location_name,
                full: loc.group_name || loc.location_full,
                is_aisle: !!loc.group_is_aisle,
                is_stock: !!loc.group_is_stock,
                warehouse_id: loc.warehouse_id || 0,
                warehouse: loc.warehouse_name || "",
                is_main: !!loc.is_main_warehouse,
                location_count: 0, total_qty: 0, serial_count: 0,
                products: new Set(), types: {},
            });
            c.location_count += 1;
            c.total_qty += loc.total_qty;
            c.serial_count += loc.serial_count;
            for (const p of loc.products) {
                c.products.add(p.product_id);
                const t = this.typeKey(p);
                c.types[t] = (c.types[t] || 0) + p.qty;
            }
        }
        const sections = {};
        for (const c of Object.values(cards)) {
            const sk = c.warehouse_id;
            const sec = sections[sk] || (sections[sk] = {
                key: sk, title: c.warehouse || "Zonder magazijn", is_main: c.is_main, cards: [],
            });
            sec.cards.push({
                ...c,
                product_count: c.products.size,
                types: Object.entries(c.types)
                    .map(([key, qty]) => ({ key, qty, label: this.getProductTypeLabel(key) }))
                    .sort((a, b) => b.qty - a.qty),
            });
        }
        const natural = (a, b) => a.localeCompare(b, undefined, { numeric: true });
        for (const sec of Object.values(sections)) {
            // the stock location itself (WH/Stock), then its aisles (G1,
            // G2, ... G10), then the other locations of the warehouse
            const rank = (c) => (c.is_stock ? 0 : c.is_aisle ? 1 : 2);
            sec.cards.sort((a, b) => (rank(a) - rank(b)) || natural(a.name, b.name));
        }
        return Object.values(sections).sort((a, b) =>
            (b.is_main - a.is_main) || (!a.key - !b.key) || natural(a.title, b.title));
    }

    get shownLocations() {
        const g = this.state.locationGroup;
        return g ? this.visibleLocations.filter((l) => (l.group_id || l.location_id) === g) : this.visibleLocations;
    }

    get openLocationCard() {
        const g = this.state.locationGroup;
        if (!g) return null;
        for (const sec of this.locationSections) {
            const card = sec.cards.find((c) => c.key === g);
            if (card) return { ...card, section: sec.title };
        }
        return null;
    }

    openLocationGroup(card) {
        this.state.locationGroup = card.key;
        // a single location: show its products right away
        const locs = this.shownLocations;
        if (locs.length === 1) this.state.expandedLocations = { [locs[0].location_id]: true };
    }

    closeLocationGroup() {
        this.state.locationGroup = null;
        this.state.expandedLocations = {};
    }

    openTypeCard(card) {
        this.state.typeFilter = card.key;
        this.state.viewMode = "product";
    }

    availablePct(card) {
        return card.total_qty > 0 ? Math.max(Math.min(card.available_qty / card.total_qty, 1), 0) * 100 : 0;
    }

    async onSearchInput(ev) {
        this.state.searchTerm = ev.target.value;
        // Debounce: wait 400ms after last keystroke
        clearTimeout(this._searchTimeout);
        this._searchTimeout = setTimeout(() => this.loadTabData(), 400);
    }

    async onSearchClear() {
        this.state.searchTerm = "";
        await this.loadTabData();
    }

    /** Available stock as cards (own stock, live), for the current segment. */
    onOpenStockCards() {
        openStockCards(this.action, { subgroup: this.state.subgroup });
    }

    onExportExcel() {
        const params = new URLSearchParams({
            stock_type: this.state.activeTab,
            view_mode: this.state.viewMode,
            search_term: this.state.searchTerm || "",
            subgroup: this.state.subgroup || "all",
            product_type: this.state.viewMode === "type" ? "" : this.state.typeFilter,
        });
        window.open(`/serviq_logistics/export_excel?${params.toString()}`, "_blank");
    }

    toggleProduct(productId) {
        if (this.state.expandedProducts[productId]) {
            delete this.state.expandedProducts[productId];
        } else {
            this.state.expandedProducts[productId] = true;
        }
        this.state.expandedProducts = { ...this.state.expandedProducts };
    }

    isExpanded(productId) {
        return !!this.state.expandedProducts[productId];
    }

    toggleLocation(locationId) {
        if (this.state.expandedLocations[locationId]) {
            delete this.state.expandedLocations[locationId];
        } else {
            this.state.expandedLocations[locationId] = true;
        }
        this.state.expandedLocations = { ...this.state.expandedLocations };
    }

    isLocationExpanded(locationId) {
        return !!this.state.expandedLocations[locationId];
    }

    openSerialNumber(lotId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "stock.lot",
            res_id: lotId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openProduct(productId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "product.product",
            res_id: productId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    get tabLabel() {
        const labels = {
            own: "Eigen voorraad",
            consignment: "Consignatievoorraad",
            customer: "Voorraad bij klanten",
        };
        return labels[this.state.activeTab];
    }

    get activeSummary() {
        return this.state.summary[this.state.activeTab] || {};
    }

    get hasData() {
        if (this.state.viewMode === "location") {
            return this.visibleLocations.length > 0;
        }
        return this.visibleProducts.length > 0;
    }

    formatQty(qty) {
        if (qty === undefined || qty === null) return "0";
        return Number.isInteger(qty) ? qty.toString() : qty.toFixed(2);
    }

}

Object.assign(StockDashboard.prototype, productTypeMethods);

Object.assign(StockDashboard.prototype, segmentFilterMethods);

registry.category("actions").add("serviq_logistics.stock_dashboard", StockDashboard);
