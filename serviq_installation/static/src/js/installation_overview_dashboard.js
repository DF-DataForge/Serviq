/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

const STATE_LABELS = {
    delivered: _t("Geleverd"),
    installation: _t("Installatie bezig"),
    commissioning: _t("Inbedrijfstelling gepland"),
    active: _t("Actief"),
    service: _t("Service"),
    offline: _t("Offline"),
    out_of_service: _t("Buiten dienst"),
};

class InstallationOverviewDashboard extends Component {
    static template = "serviq_installation.OverviewDashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        this.metrics = [
            { key: "total", label: _t("Installaties"), short: "#" },
            { key: "active", label: _t("Actief"), short: _t("Actief") },
            { key: "commissioning", label: _t("Inbedrijfstelling"), short: _t("Inbedr.") },
            { key: "service", label: _t("Service"), short: _t("Service") },
            { key: "not_registered", label: _t("Niet geregistreerd"), short: _t("Niet gereg.") },
        ];

        this.state = useState({
            loading: true,
            data: {
                overall: {},
                per_distributor: [],
                per_installer: [],
                sections: [],
            },
            // 'overview' or 'planning' (the planning calendar).
            view: "overview",
            calendar: null,
            calendarLoading: false,
            calendarInstaller: false,
            // Drill-down: selected cell + its installation records.
            selection: null, // { title, domain }
            records: [],
            recordsLoading: false,
        });

        onWillStart(async () => {
            this.state.data = await this.orm.call(
                "serviq.installation", "get_overview_dashboard_data", []
            );
            this.state.loading = false;
        });
    }

    _buildDomain(metric, partnerField, partnerId) {
        const domain = [];
        if (["active", "commissioning", "service"].includes(metric)) {
            domain.push(["state", "=", metric]);
        } else if (metric === "not_registered") {
            domain.push(["sn_registration_count", ">", 0]);
        }
        if (partnerField) {
            if (partnerId) {
                // Rows aggregate on the commercial entity, so match any
                // contact of that company.
                domain.push([
                    `${partnerField}.commercial_partner_id`,
                    "=",
                    partnerId,
                ]);
            } else {
                domain.push([partnerField, "=", false]);
            }
        }
        return domain;
    }

    /** Show the installations behind a number as tiles inside the
     *  dashboard. */
    async showRecords(metric, partnerField, partnerId, title) {
        const domain = this._buildDomain(metric, partnerField, partnerId);
        this.state.selection = { title, domain };
        this.state.recordsLoading = true;
        this.state.records = await this.orm.searchRead(
            "serviq.installation",
            domain,
            [
                "code",
                "product_tmpl_id",
                "customer_id",
                "distributor_id",
                "installer_id",
                "state",
                "sn_registration_count",
            ],
            { order: "code" }
        );
        this.state.recordsLoading = false;
    }

    closeRecords() {
        this.state.selection = null;
        this.state.records = [];
    }

    /** Escape hatch: open the current drill-down in the regular views. */
    openList() {
        if (!this.state.selection) {
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            name: this.state.selection.title || _t("Installaties"),
            res_model: "serviq.installation",
            views: [
                [false, "list"],
                [false, "kanban"],
                [false, "form"],
            ],
            domain: this.state.selection.domain,
            target: "current",
        });
    }

    // ------------------------------------------------------------------
    // Planning calendar (same layout as the installer portal)
    // ------------------------------------------------------------------
    get weekdayLabels() {
        return [_t("Ma"), _t("Di"), _t("Wo"), _t("Do"), _t("Vr"), _t("Za"), _t("Zo")];
    }

    async loadCalendar(scope, anchor) {
        this.state.view = "planning";
        this.state.calendarLoading = true;
        this.state.calendar = await this.orm.call(
            "serviq.installation",
            "get_planning_calendar_data",
            [scope || "month", anchor || false, false, this.state.calendarInstaller || false]
        );
        this.state.calendarLoading = false;
    }

    onCalendarInstallerChange(ev) {
        this.state.calendarInstaller = parseInt(ev.target.value) || false;
        this.loadCalendar(this.state.calendar.scope, this.state.calendar.anchor);
    }

    showOverview() {
        this.state.view = "overview";
    }

    calendarTasks(date) {
        return (this.state.calendar.tasks_by_day || {})[date] || [];
    }

    dayClass(day) {
        const cal = this.state.calendar;
        let cls = "sq-cal-day";
        if (cal.scope === "month" && day.month !== cal.anchor_month) {
            cls += " sq-cal-outside";
        }
        if (day.date === cal.today) {
            cls += " sq-cal-today";
        }
        return cls;
    }

    openTask(taskId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "project.task",
            res_id: taskId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openTaskList() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Interventies"),
            res_model: "project.task",
            domain: [["serviq_installation_id", "!=", false]],
            // 'New' creates a field service task.
            context: (this.state.calendar && this.state.calendar.task_context) || { fsm_mode: true },
            views: [
                [false, "list"],
                [false, "kanban"],
                [false, "form"],
            ],
            target: "current",
        });
    }

    /** Panels other modules add to the overview (e.g. the atlas map),
     *  registered in the 'serviq_installation_overview_panels' registry category. */
    get overviewPanels() {
        return registry.category("serviq_installation_overview_panels").getEntries();
    }

    /** Open the records behind a tile of an extra section. */
    openTile(tile) {
        if (tile.action) {
            this.action.doAction(tile.action);
        }
    }

    /** Open a installation of the drill-down; the form pager browses
     *  the other systems of the drill-down. */
    openRecord(recordId) {
        this.action.doAction(
            {
                type: "ir.actions.act_window",
                res_model: "serviq.installation",
                res_id: recordId,
                views: [[false, "form"]],
                target: "current",
            },
            { props: { resIds: this.state.records.map((rec) => rec.id) } }
        );
    }

    stateLabel(state) {
        return STATE_LABELS[state] || "-";
    }

    m2oName(value) {
        return value ? value[1] : "-";
    }
}

registry
    .category("actions")
    .add("serviq_installation.overview_dashboard", InstallationOverviewDashboard);
