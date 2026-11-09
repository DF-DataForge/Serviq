/** @odoo-module **/
/*
 * 'Tijd & km' form of the intervention page: shows the durations of the
 * ride there, the time on site and the ride back while they are filled in,
 * and copies the departure to the customer into an empty arrival (same day).
 */
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { Interaction } from "@web/public/interaction";

function minutes(from, to) {
    if (!from || !to || !from.value || !to.value) {
        return null;
    }
    return Math.round((new Date(to.value) - new Date(from.value)) / 60000);
}

function format(total) {
    const hours = Math.floor(total / 60);
    const rest = String(total % 60).padStart(2, "0");
    return _t("%(hours)s u %(minutes)s min", { hours, minutes: rest });
}

export class TimeForm extends Interaction {
    static selector = "form.sq-time-form";

    start() {
        this.travel = this.el.querySelector(".sq-t-travel");
        this.arrival = this.el.querySelector(".sq-t-arrival");
        this.departure = this.el.querySelector(".sq-t-departure");
        this.back = this.el.querySelector(".sq-t-back");
        this.summary = this.el.querySelector(".sq-t-summary");
        if (!this.arrival || !this.departure || !this.summary) {
            return;
        }
        if (this.travel) {
            this.addListener(this.travel, "change", () => {
                if (this.travel.value && !this.arrival.value) {
                    this.arrival.value = this.travel.value;
                }
                this.refresh();
            });
        }
        for (const field of [this.arrival, this.departure, this.back]) {
            if (field) {
                this.addListener(field, "change", this.refresh);
            }
        }
        this.refresh();
    }

    refresh() {
        const parts = [];
        const there = minutes(this.travel, this.arrival);
        const onSite = minutes(this.arrival, this.departure);
        const back = minutes(this.departure, this.back);
        if (there !== null) {
            parts.push(there > 0
                ? _t("Heenrit: %s", format(there))
                : _t("Het vertrek naar de klant ligt niet voor de aankomst."));
        }
        if (onSite !== null) {
            parts.push(onSite > 0
                ? _t("Interventie: %s", format(onSite))
                : _t("Het vertrek bij de klant ligt niet na de aankomst."));
        }
        if (back !== null) {
            parts.push(back > 0
                ? _t("Terugrit: %s", format(back))
                : _t("Terug aangekomen ligt niet na het vertrek bij de klant."));
        }
        this.summary.textContent = parts.join(" · ");
    }
}

registry
    .category("public.interactions")
    .add("serviq_portal.time_form", TimeForm);
