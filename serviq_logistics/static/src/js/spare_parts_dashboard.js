/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadFilterOptions } from "./filter_options";
import { getStoredSubgroup, segmentFilterMethods, setStoredSubgroup } from "./subgroup_filter";
import { productTypeMethods, typeOptionsMulti } from "./product_types";

class SparePartsDashboard extends Component {
    static template = "serviq_logistics.SparePartsDashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        this.state = useState({
            loading: true,
            searchTerm: "",
            subgroup: getStoredSubgroup(),
            dateFrom: "",
            dateTo: "",
            summary: {},
            customers: [],
            expandedCustomers: {},
            expandedPickings: {},
            typeFilter: "",  // product type key, "" = all
        });

        onWillStart(async () => {
            await loadFilterOptions(this.orm);
            this.state.subgroup = getStoredSubgroup();
            await this.loadSummary();
            await this.loadData();
        });
    }

    async loadSummary() {
        this.state.summary = await this.orm.call(
            "serviq.logistics.spare",
            "get_spare_stock_summary",
            [this.state.dateFrom || false, this.state.dateTo || false, this.state.subgroup]
        );
    }

    async loadData() {
        this.state.loading = true;
        this.state.expandedCustomers = {};
        this.state.expandedPickings = {};
        const searchTerm = this.state.searchTerm || false;
        this.state.customers = await this.orm.call(
            "serviq.logistics.spare",
            "get_spare_stock_data",
            [searchTerm, this.state.dateFrom || false, this.state.dateTo || false, this.state.subgroup]
        );
        this.state.loading = false;
    }

    async reload() {
        await this.loadSummary();
        await this.loadData();
    }

    async onSubgroupClick(subgroup) {
        if (this.state.subgroup === subgroup) return;
        this.state.subgroup = subgroup;
        setStoredSubgroup(subgroup);
        await this.reload();
    }

    // ------- product type filter (shared, see product_types.js) -------
    get typeOptions() {
        return typeOptionsMulti(this.state.customers.flatMap((c) => c.pickings));
    }

    /** Clients with only the deliveries holding the selected product type. */
    get visibleCustomers() {
        if (!this.state.typeFilter) return this.state.customers;
        const result = [];
        for (const cust of this.state.customers) {
            const pickings = cust.pickings.filter((p) => this.matchesType(p.product_types || []));
            if (!pickings.length) continue;
            const done = pickings.filter((p) => p.state === "done").length;
            result.push({
                ...cust, pickings, total_pickings: pickings.length, done_pickings: done,
                pending_pickings: pickings.length - done,
                total_qty: pickings.reduce((a, p) => a + p.total_qty, 0),
            });
        }
        return result;
    }

    onSearchInput(ev) {
        this.state.searchTerm = ev.target.value;
        clearTimeout(this._searchTimeout);
        this._searchTimeout = setTimeout(() => this.loadData(), 400);
    }

    async onSearchClear() {
        this.state.searchTerm = "";
        await this.loadData();
    }

    async onDateFromChange(ev) {
        this.state.dateFrom = ev.target.value;
        await this.reload();
    }

    async onDateToChange(ev) {
        this.state.dateTo = ev.target.value;
        await this.reload();
    }

    async onDateRangeClear() {
        this.state.dateFrom = "";
        this.state.dateTo = "";
        await this.reload();
    }

    toggleCustomer(partnerId) {
        if (this.state.expandedCustomers[partnerId]) {
            delete this.state.expandedCustomers[partnerId];
        } else {
            this.state.expandedCustomers[partnerId] = true;
        }
        this.state.expandedCustomers = { ...this.state.expandedCustomers };
    }

    isCustomerExpanded(partnerId) {
        return !!this.state.expandedCustomers[partnerId];
    }

    togglePicking(pickingId) {
        if (this.state.expandedPickings[pickingId]) {
            delete this.state.expandedPickings[pickingId];
        } else {
            this.state.expandedPickings[pickingId] = true;
        }
        this.state.expandedPickings = { ...this.state.expandedPickings };
    }

    isPickingExpanded(pickingId) {
        return !!this.state.expandedPickings[pickingId];
    }

    openPicking(pickingId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "stock.picking",
            res_id: pickingId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    getPickingStateClass(state) {
        const classes = {
            done: "bg-success",
            assigned: "bg-primary",
            confirmed: "bg-info",
            waiting: "bg-warning",
            draft: "bg-secondary",
            cancel: "bg-danger",
        };
        return classes[state] || "bg-secondary";
    }

    onExportExcel() {
        const params = new URLSearchParams({
            search_term: this.state.searchTerm || "",
            date_from: this.state.dateFrom || "",
            date_to: this.state.dateTo || "",
            subgroup: this.state.subgroup || "all",
        });
        window.open(`/serviq_logistics/export_spare_stock_excel?${params.toString()}`, "_blank");
    }
}

Object.assign(SparePartsDashboard.prototype, productTypeMethods);

Object.assign(SparePartsDashboard.prototype, segmentFilterMethods);

registry.category("actions").add("serviq_logistics.spare_parts_dashboard", SparePartsDashboard);
