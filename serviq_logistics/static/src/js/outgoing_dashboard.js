/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadFilterOptions } from "./filter_options";
import { getStoredSubgroup, segmentFilterMethods, setStoredSubgroup } from "./subgroup_filter";
import { productTypeMethods, typeOptionsMulti } from "./product_types";

class OutgoingGoodsDashboard extends Component {
    static template = "serviq_logistics.OutgoingGoodsDashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        this.state = useState({
            loading: true,
            searchTerm: "",
            subgroup: getStoredSubgroup(),
            summary: {},
            customers: [],
            expandedCustomers: {},
            expandedOrders: {},
            typeFilter: "",  // product type key, "" = all
            expandedPickings: {},
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
            "serviq.logistics.outgoing",
            "get_outgoing_summary",
            [this.state.subgroup]
        );
    }

    async loadData() {
        this.state.loading = true;
        this.state.expandedCustomers = {};
        this.state.expandedOrders = {};
        this.state.expandedPickings = {};
        const searchTerm = this.state.searchTerm || false;
        this.state.customers = await this.orm.call(
            "serviq.logistics.outgoing",
            "get_outgoing_data",
            [searchTerm, this.state.subgroup]
        );
        this.state.loading = false;
    }

    async onSubgroupClick(subgroup) {
        if (this.state.subgroup === subgroup) return;
        this.state.subgroup = subgroup;
        setStoredSubgroup(subgroup);
        await this.loadSummary();
        await this.loadData();
    }

    // ------- product type filter (shared, see product_types.js) -------
    get typeOptions() {
        return typeOptionsMulti(this.state.customers.flatMap((c) => c.sale_orders));
    }

    /** Customers with only the SOs of the selected product type. */
    get visibleCustomers() {
        if (!this.state.typeFilter) return this.state.customers;
        const result = [];
        for (const cust of this.state.customers) {
            const sos = cust.sale_orders.filter((so) => this.matchesType(so.product_types || []));
            if (!sos.length) continue;
            const count = (status) => sos.filter((so) => so.delivery_status === status).length;
            result.push({
                ...cust, sale_orders: sos, total_orders: sos.length,
                fully_delivered: count("fully_delivered"), partially_delivered: count("partially_delivered"),
                waiting: count("waiting"),
            });
        }
        return result;
    }

    async onSearchInput(ev) {
        this.state.searchTerm = ev.target.value;
        clearTimeout(this._searchTimeout);
        this._searchTimeout = setTimeout(() => this.loadData(), 400);
    }

    async onSearchClear() {
        this.state.searchTerm = "";
        await this.loadData();
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

    toggleOrder(soId) {
        if (this.state.expandedOrders[soId]) {
            delete this.state.expandedOrders[soId];
        } else {
            this.state.expandedOrders[soId] = true;
        }
        this.state.expandedOrders = { ...this.state.expandedOrders };
    }

    isOrderExpanded(soId) {
        return !!this.state.expandedOrders[soId];
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

    openSaleOrder(soId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "sale.order",
            res_id: soId,
            views: [[false, "form"]],
            target: "current",
        });
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

    downloadDocument(docId) {
        window.open(`/web/content/${docId}?download=true`, "_blank");
    }

    getStatusClass(status) {
        const classes = {
            fully_delivered: "sq-status-done",
            partially_delivered: "sq-status-partial",
            waiting: "sq-status-waiting",
        };
        return classes[status] || "sq-status-waiting";
    }

    getStatusLabel(status) {
        const labels = {
            fully_delivered: "Volledig geleverd",
            partially_delivered: "Deels geleverd",
            waiting: "Wachtend",
        };
        return labels[status] || status;
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

    getMoveStateLabel(state) {
        const labels = {
            draft: "Concept",
            waiting: "Wachtend",
            confirmed: "Bevestigd",
            partially_available: "Deels",
            assigned: "Beschikbaar",
            done: "Afgewerkt",
            cancel: "Geannuleerd",
        };
        return labels[state] || state;
    }

    onExportExcel() {
        const params = new URLSearchParams({
            search_term: this.state.searchTerm || "",
            subgroup: this.state.subgroup || "all",
        });
        window.open(`/serviq_logistics/export_outgoing_excel?${params.toString()}`, "_blank");
    }
}

Object.assign(OutgoingGoodsDashboard.prototype, productTypeMethods);

Object.assign(OutgoingGoodsDashboard.prototype, segmentFilterMethods);

registry.category("actions").add("serviq_logistics.outgoing_dashboard", OutgoingGoodsDashboard);
