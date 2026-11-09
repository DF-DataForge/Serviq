/** @odoo-module **/
/*
 * 'Urenoverzicht interventies': hours logged on the interventions of
 * installations in a period, per installer, per distributor and per
 * type of intervention. Every number opens the timesheet lines behind it.
 * The icon next to an installer shows the installer's user rights.
 */
import { Component, onWillStart, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { SystemFilterBar, loadSystemFilters } from "./system_filters";

/** Rights of an installer: distributors and, with serviq_portal, the
 *  portal access. */
class InstallerRightsDialog extends Component {
    static template = "serviq_installation.InstallerRightsDialog";
    static components = { Dialog };
    static props = ["rights", "close"];
}

class HoursOverview extends Component {
    static template = "serviq_installation.HoursOverview";
    static components = { SystemFilterBar };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.dialog = useService("dialog");
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
            filters: loadSystemFilters(),
        });
        onWillStart(() => this.load("week"));
    }

    async load(period, dateFrom, dateTo) {
        this.state.loading = true;
        this.state.data = await this.orm.call(
            "serviq.installation",
            "get_hours_overview_data",
            [period, dateFrom || false, dateTo || false, this.state.filters]
        );
        this.state.dateFrom = this.state.data.date_from;
        this.state.dateTo = this.state.data.date_to;
        this.state.loading = false;
    }

    onFiltersChange(filters) {
        this.state.filters = filters;
        const data = this.state.data;
        if (data && data.period === "custom") {
            this.load("custom", this.state.dateFrom, this.state.dateTo);
        } else {
            this.load((data && data.period) || "week");
        }
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

    async showRights(row) {
        const partnerId = parseInt(row.key);
        if (!partnerId) {
            return;
        }
        const rights = await this.orm.call(
            "res.partner", "serviq_get_installer_rights", [[partnerId]]
        );
        this.dialog.add(InstallerRightsDialog, { rights });
    }

    open(action) {
        if (action) {
            this.action.doAction(action);
        }
    }
}

registry.category("actions").add("serviq_installation.hours_overview", HoursOverview);
