/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadFilterOptions } from "./filter_options";
import { getStoredSubgroup, segmentFilterMethods, setStoredSubgroup } from "./subgroup_filter";
import { productTypeMethods, typeOptionsMulti } from "./product_types";

class IncomingGoodsDashboard extends Component {
    static template = "serviq_logistics.IncomingGoodsDashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        this.state = useState({
            loading: true,
            searchTerm: "",
            subgroup: getStoredSubgroup(),
            summary: {},
            suppliers: [],
            expandedSuppliers: {},
            expandedOrders: {},
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
            "serviq.logistics.incoming",
            "get_incoming_summary",
            [this.state.subgroup]
        );
    }

    async loadData() {
        this.state.loading = true;
        this.state.expandedSuppliers = {};
        this.state.expandedOrders = {};
        const searchTerm = this.state.searchTerm || false;
        this.state.suppliers = await this.orm.call(
            "serviq.logistics.incoming",
            "get_incoming_data",
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
        return typeOptionsMulti(this.state.suppliers.flatMap((s) => s.purchase_orders));
    }

    /** Suppliers with only the POs of the selected product type. */
    get visibleSuppliers() {
        if (!this.state.typeFilter) return this.state.suppliers;
        const result = [];
        for (const sup of this.state.suppliers) {
            const pos = sup.purchase_orders.filter((po) => this.matchesType(po.product_types || []));
            if (!pos.length) continue;
            const count = (status) => pos.filter((po) => po.reception_status === status).length;
            result.push({
                ...sup, purchase_orders: pos, total_orders: pos.length,
                fully_received: count("fully_received"), partially_received: count("partially_received"),
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

    toggleSupplier(partnerId) {
        if (this.state.expandedSuppliers[partnerId]) {
            delete this.state.expandedSuppliers[partnerId];
        } else {
            this.state.expandedSuppliers[partnerId] = true;
        }
        this.state.expandedSuppliers = { ...this.state.expandedSuppliers };
    }

    isSupplierExpanded(partnerId) {
        return !!this.state.expandedSuppliers[partnerId];
    }

    toggleOrder(poId) {
        if (this.state.expandedOrders[poId]) {
            delete this.state.expandedOrders[poId];
        } else {
            this.state.expandedOrders[poId] = true;
        }
        this.state.expandedOrders = { ...this.state.expandedOrders };
    }

    isOrderExpanded(poId) {
        return !!this.state.expandedOrders[poId];
    }

    openPurchaseOrder(poId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "purchase.order",
            res_id: poId,
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
            fully_received: "sq-status-done",
            partially_received: "sq-status-partial",
            waiting: "sq-status-waiting",
        };
        return classes[status] || "sq-status-waiting";
    }

    getStatusLabel(status) {
        const labels = {
            fully_received: "Volledig ontvangen",
            partially_received: "Deels ontvangen",
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

    onExportExcel() {
        const params = new URLSearchParams({
            search_term: this.state.searchTerm || "",
            subgroup: this.state.subgroup || "all",
        });
        window.open(`/serviq_logistics/export_incoming_excel?${params.toString()}`, "_blank");
    }
}

Object.assign(IncomingGoodsDashboard.prototype, productTypeMethods);

Object.assign(IncomingGoodsDashboard.prototype, segmentFilterMethods);

registry.category("actions").add("serviq_logistics.incoming_dashboard", IncomingGoodsDashboard);
