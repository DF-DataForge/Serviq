/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadFilterOptions } from "./filter_options";
import { getStoredSubgroup, segmentFilterMethods, setStoredSubgroup } from "./subgroup_filter";
import { productTypeMethods, sortTypes, typeKey, typeLabel, typeOptions } from "./product_types";

class SnTrackingDashboard extends Component {
    static template = "serviq_logistics.SnTrackingDashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        this.state = useState({
            segment: "inhouse", // "ordered" | "inhouse" | "customer"
            subgroup: getStoredSubgroup(), // "all" or an installation category code
            searchTerm: "",
            loading: true,
            summary: { ordered: {}, inhouse: {}, customer: {} },
            rows: [],
            expandedRows: {},
            selectedCustomerId: null,
            view: "type",  // ordered / in-house: "type" (cards per product type) or "product"
            typeFilter: "",  // product type key, "" = all
        });

        onWillStart(async () => {
            await loadFilterOptions(this.orm);
            this.state.subgroup = getStoredSubgroup();
            await this.reload();
        });
    }

    async reload() {
        this.state.loading = true;
        this.state.expandedRows = {};
        const subgroup = this.state.subgroup;
        const searchTerm = this.state.searchTerm || false;
        const [summary, rows] = await Promise.all([
            this.orm.call("serviq.logistics.sn", "get_summary", [subgroup, searchTerm]),
            this.orm.call("serviq.logistics.sn", "get_segment_data", [
                this.state.segment,
                subgroup,
                searchTerm,
            ]),
        ]);
        this.state.summary = summary;
        this.state.rows = rows;
        this.state.loading = false;
    }

    async loadSegmentData() {
        this.state.loading = true;
        this.state.expandedRows = {};
        this.state.rows = await this.orm.call(
            "serviq.logistics.sn",
            "get_segment_data",
            [this.state.segment, this.state.subgroup, this.state.searchTerm || false]
        );
        this.state.loading = false;
    }

    async onSegmentClick(segment) {
        if (this.state.segment === segment) return;
        this.state.segment = segment;
        this.state.selectedCustomerId = null;
        this.state.view = "type";
        this.state.typeFilter = "";
        await this.loadSegmentData();
    }

    get selectedCustomer() {
        if (this.state.segment !== "customer" || !this.state.selectedCustomerId) {
            return null;
        }
        // Re-resolve against the loaded rows so a reload (filter change)
        // refreshes the overview, or falls back to the card list when the
        // customer no longer matches the filters.
        return this.visibleRows.find(
            (row) => row.location_id === this.state.selectedCustomerId
        ) || null;
    }

    // ------- product type categorisation (shared, see product_types.js) -------
    /** Rows of the active segment after the type filter. Customers keep
     *  only the product types that match, with their totals recomputed. */
    get visibleRows() {
        const f = this.state.typeFilter;
        if (this.state.segment !== "customer") {
            return f ? this.state.rows.filter((r) => typeKey(r) === f) : this.state.rows;
        }
        if (!f) return this.state.rows;
        const result = [];
        for (const cust of this.state.rows) {
            const types = cust.types.filter((t) => (t.ptype || "none") === f);
            if (!types.length) continue;
            const sum = (k) => types.reduce((a, t) => a + t[k], 0);
            result.push({
                ...cust, types,
                total_qty: sum("qty"), serial_count: sum("serial_count"),
                installed_count: sum("installed_count"), product_count: sum("product_count"),
            });
        }
        return result;
    }

    get typeOptions() {
        if (this.state.segment === "customer") {
            return typeOptions(this.state.rows.flatMap((c) => c.types.flatMap((t) => t.products)),
                (p) => p.product_type || "none");
        }
        return typeOptions(this.state.rows);
    }

    /** Ordered / in-house: one card per product type. */
    get typeCards() {
        const ordered = this.state.segment === "ordered";
        const groups = {};
        for (const r of this.state.rows) {
            const key = typeKey(r);
            const g = groups[key] || (groups[key] = {
                key, label: typeLabel(key), product_count: 0, top: [],
                ordered_qty: 0, received_qty: 0, pending_qty: 0, order_count: 0,
                total_qty: 0, reserved_qty: 0, available_qty: 0, serial_count: 0,
            });
            g.product_count += 1;
            g.top.push(r);
            if (ordered) {
                g.ordered_qty += r.ordered_qty;
                g.received_qty += r.received_qty;
                g.pending_qty += r.pending_qty;
                g.order_count += r.order_count;
            } else {
                g.total_qty += r.total_qty;
                g.reserved_qty += r.reserved_qty;
                g.available_qty += r.available_qty;
                g.serial_count += r.serial_count;
            }
        }
        const size = (r) => (ordered ? r.pending_qty : r.total_qty);
        return sortTypes(Object.values(groups).map((g) => ({
            ...g, top: g.top.sort((a, b) => size(b) - size(a)).slice(0, 3),
        })));
    }

    get showTypeCards() {
        return this.state.segment !== "customer" && this.state.view === "type";
    }

    setView(view) {
        this.state.view = view;
        if (view === "type") this.state.typeFilter = "";
        this.state.expandedRows = {};
    }

    openTypeCard(card) {
        this.state.typeFilter = card.key;
        this.state.view = "product";
        this.state.expandedRows = {};
    }

    openCustomerOverview(locationId) {
        this.state.selectedCustomerId = locationId;
        this.state.expandedRows = {};
    }

    closeCustomerOverview() {
        this.state.selectedCustomerId = null;
        this.state.expandedRows = {};
    }

    async onSubgroupClick(subgroup) {
        if (this.state.subgroup === subgroup) return;
        this.state.subgroup = subgroup;
        setStoredSubgroup(subgroup);
        await this.reload();
    }

    onSearchInput(ev) {
        this.state.searchTerm = ev.target.value;
        clearTimeout(this._searchTimeout);
        this._searchTimeout = setTimeout(() => this.reload(), 400);
    }

    async onSearchClear() {
        this.state.searchTerm = "";
        await this.reload();
    }

    toggleRow(productId) {
        if (this.state.expandedRows[productId]) {
            delete this.state.expandedRows[productId];
        } else {
            this.state.expandedRows[productId] = true;
        }
        this.state.expandedRows = { ...this.state.expandedRows };
    }

    isExpanded(productId) {
        return !!this.state.expandedRows[productId];
    }

    openRecord(resModel, resId) {
        if (!resId) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: resModel,
            res_id: resId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openProduct(productId) {
        this.openRecord("product.product", productId);
    }

    openSerialNumber(lotId) {
        this.openRecord("stock.lot", lotId);
    }

    openPurchaseOrder(orderId) {
        this.openRecord("purchase.order", orderId);
    }

    openInstallation(installationId) {
        this.openRecord("serviq.installation", installationId);
    }

    get segmentLabel() {
        const labels = {
            ordered: "Besteld",
            inhouse: "In huis",
            customer: "Bij klanten",
        };
        return labels[this.state.segment];
    }

    get hasData() {
        return this.visibleRows.length > 0;
    }

    formatQty(qty) {
        if (qty === undefined || qty === null) return "0";
        return Number.isInteger(qty) ? qty.toString() : qty.toFixed(2);
    }

    percent(part, total) {
        if (!total) return 0;
        return Math.min(100, Math.round((part / total) * 100));
    }
}

Object.assign(SnTrackingDashboard.prototype, productTypeMethods);

Object.assign(SnTrackingDashboard.prototype, segmentFilterMethods);

registry.category("actions").add("serviq_logistics.sn_tracking_dashboard", SnTrackingDashboard);
