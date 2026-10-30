/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { formatDay, monthEndOptions, stepPeriodValue } from "./period_filter";
import { loadFilterOptions } from "./filter_options";
import { getStoredSubgroup, segmentFilterMethods, setStoredSubgroup } from "./subgroup_filter";
import { typeClass } from "./product_types";

// Available stock as smart cards: one card per product type, clicking a
// type shows the same cards per product. Opened from the menu
// (Beschikbare voorraad) or from the Voorraadoverzicht, keeping its
// segment; "situatie per" rolls the stock back to a past month end.
class StockCards extends Component {
    static template = "serviq_logistics.StockCards";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        const params = (this.props.action && this.props.action.params) || {};
        this.state = useState({
            loading: true,
            asOf: params.as_of || "",
            subgroup: params.subgroup || getStoredSubgroup(),
            data: null,
            view: params.ptype ? "product" : "type",
            ptype: params.ptype || null,
            search: "",
            sort: "value",
        });
        onWillStart(async () => {
            await loadFilterOptions(this.orm);
            this.state.subgroup = params.subgroup || getStoredSubgroup();
            await this.reload();
        });
    }

    async reload(force = false) {
        this.state.loading = true;
        this.state.data = await this.orm.call(
            "serviq.logistics.stock.cards", "get_stock_cards",
            [this.state.subgroup, this.state.asOf || false, force]);
        this.state.loading = false;
    }

    // ------- filters -------
    get periodOptions() {
        return monthEndOptions();
    }

    get isHistorical() {
        return !!(this.state.data && this.state.data.as_of);
    }

    formatDay(iso) {
        return formatDay(iso);
    }

    async onPeriodChange(ev) {
        this.state.asOf = ev.target.value;
        await this.reload();
    }

    async stepPeriod(delta) {
        const next = stepPeriodValue(this.state.asOf, delta, this.periodOptions);
        if (next === this.state.asOf) return;
        this.state.asOf = next;
        await this.reload();
    }

    async onSubgroupClick(subgroup) {
        if (this.state.subgroup === subgroup) return;
        this.state.subgroup = subgroup;
        setStoredSubgroup(subgroup);
        await this.reload();
    }

    onSearch(ev) {
        this.state.search = ev.target.value;
    }

    onSort(ev) {
        this.state.sort = ev.target.value;
    }

    setView(view) {
        // the switch shows everything; clicking a type card filters
        this.state.view = view;
        this.state.ptype = null;
    }

    openType(type) {
        this.state.ptype = type.ptype;
        this.state.view = "product";
    }

    clearType() {
        this.state.ptype = null;
    }

    // ------- data -------
    get live() {
        return !!(this.state.data && this.state.data.live);
    }

    get products() {
        let cards = (this.state.data && this.state.data.cards) || [];
        if (this.state.ptype) cards = cards.filter((c) => c.ptype === this.state.ptype);
        const term = this.state.search.trim().toLowerCase();
        if (term) {
            cards = cards.filter((c) => [c.name, c.code].some((v) => (v || "").toLowerCase().includes(term)));
        }
        return [...cards].sort(this.sorter);
    }

    get types() {
        const types = (this.state.data && this.state.data.types) || [];
        const term = this.state.search.trim().toLowerCase();
        const list = term ? types.filter((t) => t.label.toLowerCase().includes(term)) : types;
        return this.state.sort === "type" ? list : [...list].sort(this.sorter);
    }

    get sorter() {
        const by = {
            value: (a, b) => b.value - a.value,
            available: (a, b) => b.available_qty - a.available_qty,
            qty: (a, b) => b.qty - a.qty,
            free: (a, b) => (b.free_qty ?? b.available_qty) - (a.free_qty ?? a.available_qty),
            name: (a, b) => (a.name || a.label).localeCompare(b.name || b.label),
            type: () => 0,
        };
        return by[this.state.sort] || by.value;
    }

    get typeLabel() {
        const t = ((this.state.data && this.state.data.types) || []).find((x) => x.ptype === this.state.ptype);
        return t ? t.label : "";
    }

    get totals() {
        const list = this.state.view === "type" ? this.types : this.products;
        return list.reduce((acc, x) => ({
            products: acc.products + (x.product_count || 1),
            qty: acc.qty + x.qty,
            available: acc.available + x.available_qty,
            value: acc.value + x.value,
        }), { products: 0, qty: 0, available: 0, value: 0 });
    }

    availablePct(x) {
        return x.qty > 0 ? Math.max(Math.min((x.available_qty / x.qty) * 100, 100), 0) : 0;
    }

    typeClass(ptype) {
        return typeClass(ptype);
    }

    // ------- drill-down -------
    openProduct(card) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "product.product",
            res_id: card.product_id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openProductStock(card) {
        if (this.isHistorical) {
            this.action.doAction({
                type: "ir.actions.act_window",
                res_model: "stock.move.line",
                name: `Voorraadbewegingen ${card.name} t.e.m. ${this.formatDay(this.state.data.as_of)}`,
                domain: [["product_id", "=", card.product_id], ["state", "=", "done"],
                         ["date", "<=", `${this.state.data.as_of} 23:59:59`]],
                views: [[false, "list"], [false, "form"]],
                target: "current",
            });
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "stock.quant",
            name: `Voorraad ${card.name}`,
            domain: [["product_id", "=", card.product_id], ["location_id.usage", "=", "internal"]],
            views: [[false, "list"], [false, "form"]],
            target: "current",
        });
    }

    // ------- formatting -------
    formatCurrency(value) {
        if (value === undefined || value === null) value = 0;
        const code = (this.state.data && this.state.data.currency) || "EUR";
        try {
            return new Intl.NumberFormat("nl-BE", { style: "currency", currency: code, maximumFractionDigits: 0 }).format(value);
        } catch {
            return `${value.toFixed(0)} ${code}`;
        }
    }

    formatQty(qty) {
        if (qty === undefined || qty === null) return "—";
        return Number.isInteger(qty) ? qty.toString() : qty.toFixed(2);
    }
}

Object.assign(StockCards.prototype, segmentFilterMethods);

registry.category("actions").add("serviq_logistics.stock_cards", StockCards);

/** Open the stock cards from a dashboard (keeps date and subgroup). */
export function openStockCards(action, { asOf = "", subgroup = null, ptype = null, title = "Beschikbare voorraad" } = {}) {
    action.doAction({
        type: "ir.actions.client",
        tag: "serviq_logistics.stock_cards",
        name: title,
        params: { as_of: asOf || "", subgroup, ptype },
    });
}
