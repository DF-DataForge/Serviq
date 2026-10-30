/** @odoo-module **/
/*
 * 'Urenoverzicht interventies': hours logged on the interventions of
 * installations in a period, per installer, per employee, per
 * distributor and per type of intervention. Every number opens the
 * timesheet lines behind it.
 */
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

class HoursOverview extends Component {
    static template = "serviq_installation.HoursOverview";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.periods = [
            { key: "week", label: _t("Deze week") },
            { key: "last_week", label: _t("Vorige week") },
            { key: "month", label: _t("Deze maand") },
            { key: "last_month", label: _t("Vorige maand") },
            { key: "year", label: _t("Dit jaar") },
        ];
        this.state = useState({
            data: null,
            loading: false,
            dateFrom: "",
            dateTo: "",
        });
        onWillStart(() => this.load("week"));
    }

    async load(period, dateFrom, dateTo) {
        this.state.loading = true;
        this.state.data = await this.orm.call(
            "serviq.installation",
            "get_hours_overview_data",
            [period, dateFrom || false, dateTo || false]
        );
        this.state.dateFrom = this.state.data.date_from;
        this.state.dateTo = this.state.data.date_to;
        this.state.loading = false;
    }

    loadCustom() {
        if (this.state.dateFrom && this.state.dateTo) {
            this.load("custom", this.state.dateFrom, this.state.dateTo);
        }
    }

    onDateFrom(ev) {
        this.state.dateFrom = ev.target.value;
        this.loadCustom();
    }

    onDateTo(ev) {
        this.state.dateTo = ev.target.value;
        this.loadCustom();
    }

    open(action) {
        if (action) {
            this.action.doAction(action);
        }
    }
}

registry.category("actions").add("serviq_installation.hours_overview", HoursOverview);
