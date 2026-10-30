/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadFilterOptions } from "./filter_options";
import { getStoredSubgroup, segmentFilterMethods, setStoredSubgroup } from "./subgroup_filter";

class HomeDashboard extends Component {
    static template = "serviq_logistics.HomeDashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        this.state = useState({
            loading: true,
            subgroup: getStoredSubgroup(),
            data: null,
        });

        onWillStart(async () => {
            await loadFilterOptions(this.orm);
            this.state.subgroup = getStoredSubgroup();
            await this.reload();
        });
    }

    async reload(force = false) {
        // Results are cached server-side; force recomputes.
        const subgroup = this.state.subgroup;
        const token = (this._loadToken = (this._loadToken || 0) + 1);
        this.state.loading = true;
        const data = await this.orm.call("serviq.logistics.home", "get_home_data", [subgroup, force]);
        // ignore answers of an earlier load (subgroup switched meanwhile)
        if (token !== this._loadToken) return;
        this.state.data = data;
        this.state.loading = false;
    }

    /** May the user open dashboard `key` (see dashboard_access.py)? */
    can(key) {
        const access = this.state.data && this.state.data.access;
        return !!(access && access[key]);
    }

    get hasOperational() {
        return ["stock", "sn", "incoming", "outgoing", "spare"].some((k) => this.can(k));
    }

    async onSubgroupClick(subgroup) {
        if (this.state.subgroup === subgroup) return;
        this.state.subgroup = subgroup;
        setStoredSubgroup(subgroup);
        await this.reload();
    }

    openDashboard(actionXmlId) {
        this.action.doAction(actionXmlId);
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

Object.assign(HomeDashboard.prototype, segmentFilterMethods);

registry.category("actions").add("serviq_logistics.home_dashboard", HomeDashboard);
