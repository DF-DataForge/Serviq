/** @odoo-module **/
/*
 * 'Inplannen via kalender': the planning calendar (same look as on the
 * Installations Overview and the portal) in which the user
 * picks the slot of an intervention. Month view to navigate; week and day
 * views with half-hour slots between 07:00 and 19:00 showing the
 * interventions already planned. The chosen start becomes the planned
 * date of the intervention, for its current duration.
 */
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

const FIRST_HOUR = 7;
const LAST_HOUR = 19;
const SLOT_MINUTES = 30;

function pad(value) {
    return String(value).padStart(2, "0");
}

function toMinutes(time) {
    const [h, m] = (time || "0:0").split(":").map(Number);
    return h * 60 + m;
}

function toTime(minutes) {
    return `${pad(Math.floor(minutes / 60) % 24)}:${pad(minutes % 60)}`;
}

class InterventionSlotPicker extends Component {
    static template = "serviq_installation.InterventionSlotPicker";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.taskId = this.props.action.params.task_id;
        this.state = useState({
            info: null,
            cal: null,
            loading: false,
            selected: null, // { date, time }
            saving: false,
            // Installer filter: the installer of the intervention by default.
            installerId: false,
        });
        onWillStart(async () => {
            this.state.info = await this.orm.call(
                "project.task", "serviq_get_slot_picker_info", [[this.taskId]]
            );
            this.state.installerId = this.state.info.installer_id || false;
            await this.load("week", this.state.info.anchor);
        });
    }

    get weekdayLabels() {
        return [_t("Ma"), _t("Di"), _t("Wo"), _t("Do"), _t("Vr"), _t("Za"), _t("Zo")];
    }

    get slots() {
        const slots = [];
        for (let m = FIRST_HOUR * 60; m < LAST_HOUR * 60; m += SLOT_MINUTES) {
            slots.push(toTime(m));
        }
        return slots;
    }

    /** Days shown in the time grid (week or day view). */
    get gridDays() {
        const cal = this.state.cal;
        if (cal.scope === "day") {
            const [y, m, d] = cal.day.split("-").map(Number);
            const date = new Date(y, m - 1, d);
            return [{ date: cal.day, day: d, weekday: (date.getDay() + 6) % 7 }];
        }
        return cal.weeks[0];
    }

    get durationLabel() {
        return toTime(Math.round((this.state.info.hours || 0) * 60));
    }

    get selectedEnd() {
        const sel = this.state.selected;
        if (!sel) {
            return "";
        }
        return toTime(toMinutes(sel.time) + Math.round(this.state.info.hours * 60));
    }

    async load(scope, anchor) {
        this.state.loading = true;
        this.state.cal = await this.orm.call(
            "serviq.installation",
            "get_planning_calendar_data",
            [scope, anchor || false, this.taskId, this.state.installerId || false]
        );
        this.state.loading = false;
    }

    onInstallerChange(ev) {
        this.state.installerId = parseInt(ev.target.value) || false;
        this.load(this.state.cal.scope, this.state.cal.anchor);
    }

    tasksOf(date) {
        return (this.state.cal.tasks_by_day || {})[date] || [];
    }

    /** Interventions starting in the slot `time` of `date`. */
    tasksAt(date, time) {
        const from = toMinutes(time);
        const isFirst = from === FIRST_HOUR * 60;
        const isLast = from === LAST_HOUR * 60 - SLOT_MINUTES;
        return this.tasksOf(date).filter((t) => {
            if (!t.start) {
                return false;
            }
            const start = toMinutes(t.start);
            return (start >= from && start < from + SLOT_MINUTES)
                || (isFirst && start < from)
                || (isLast && start >= from + SLOT_MINUTES);
        });
    }

    /** Interventions of `date` without a start time (deadline only). */
    untimedTasks(date) {
        return this.tasksOf(date).filter((t) => !t.start);
    }

    /** The slot is inside the duration of the chosen start. */
    isSelected(date, time) {
        const sel = this.state.selected;
        if (!sel || sel.date !== date) {
            return false;
        }
        const start = toMinutes(sel.time);
        const minutes = toMinutes(time);
        return minutes >= start
            && minutes < start + Math.max(SLOT_MINUTES, Math.round(this.state.info.hours * 60));
    }

    dayClass(day) {
        const cal = this.state.cal;
        let cls = "sq-cal-day";
        if (cal.scope === "month" && day.month !== cal.anchor_month) {
            cls += " sq-cal-outside";
        }
        if (day.date === cal.today) {
            cls += " sq-cal-today";
        }
        return cls;
    }

    selectSlot(date, time) {
        this.state.selected = { date, time };
    }

    formatDate(date) {
        const [y, m, d] = date.split("-");
        return `${d}/${m}/${y}`;
    }

    async confirm() {
        const sel = this.state.selected;
        if (!sel || this.state.saving) {
            return;
        }
        this.state.saving = true;
        await this.orm.call(
            "project.task", "serviq_set_planned_slot", [[this.taskId], `${sel.date} ${sel.time}`]
        );
        this.backToTask();
    }

    backToTask() {
        this.action.doAction(
            {
                type: "ir.actions.act_window",
                res_model: "project.task",
                res_id: this.taskId,
                views: [[false, "form"]],
                target: "current",
            },
            { stackPosition: "replacePreviousAction" }
        );
    }
}

registry
    .category("actions")
    .add("serviq_installation.intervention_slot_picker", InterventionSlotPicker);
