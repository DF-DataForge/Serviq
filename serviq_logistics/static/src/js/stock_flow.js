/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const STORAGE_KEY = "serviq_logistics.stock_flow_warehouse";

// Voorraadstroom: per warehouse its operations as a flow - receipt ->
// putaway -> stock -> picking -> packing -> delivery, and the returns back
// to stock (directly through the putaway, or through repair and its
// putaway) - with the live counters of each operation type. Every card and
// counter opens exactly the operations it counts; the stock card opens the
// stock of the warehouse. One warehouse (or all) is shown, remembered per
// browser.
class StockFlow extends Component {
    static template = "serviq_logistics.StockFlow";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ loading: true, warehouses: [], selected: "", noAccess: false });
        onWillStart(() => this.reload());
    }

    get storedSelection() {
        try {
            return window.localStorage.getItem(STORAGE_KEY) || "";
        } catch {
            return "";
        }
    }

    onSelect(ev) {
        this.state.selected = ev.target.value;
        try {
            window.localStorage.setItem(STORAGE_KEY, this.state.selected);
        } catch {
            // localStorage unavailable (private mode) - the choice just won't persist
        }
    }

    get shownWarehouses() {
        if (this.state.selected === "all") return this.state.warehouses;
        return this.state.warehouses.filter((wh) => String(wh.id) === this.state.selected);
    }

    async reload() {
        this.state.loading = true;
        const data = await this.orm.call("serviq.logistics.flow", "get_flow_data", []);
        if (!data.access && data.fallback) {
            // No access to this dashboard (e.g. as landing page of the
            // Inventory app): open the standard inventory overview instead.
            this.action.doAction(data.fallback, { clearBreadcrumbs: true });
            return;
        }
        this.state.warehouses = data.warehouses;
        // Keep the chosen warehouse; else the remembered one; else the first.
        const ids = this.state.warehouses.map((wh) => String(wh.id));
        const wanted = this.state.selected || this.storedSelection;
        this.state.selected = wanted === "all" || ids.includes(wanted) ? wanted : ids[0] || "all";
        this.state.noAccess = !data.access;
        this.state.loading = false;
    }

    /** Forward steps of a warehouse in order, with the stock in between. */
    forward(wh) {
        return [
            ...wh.inbound.map((step) => ({ ...step, role: "step" })),
            { role: "stock" },
            ...wh.outbound.map((step) => ({ ...step, role: "step" })),
        ];
    }

    hasReturnFlow(wh) {
        return !!(wh.returns.length || wh.repair || wh.repair_putaway);
    }

    async openStep(step, filter = "ready") {
        const action = await this.orm.call(
            "serviq.logistics.flow", "open_flow_step", [step.type_id, filter]);
        this.action.doAction(action);
    }

    async openStock(wh) {
        const action = await this.orm.call(
            "serviq.logistics.flow", "open_flow_stock", [wh.id]);
        this.action.doAction(action);
    }
}

registry.category("actions").add("serviq_logistics.stock_flow", StockFlow);
