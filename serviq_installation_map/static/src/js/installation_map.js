/** @odoo-module **/
/*
 * Map of the installations: a panel of the overview dashboard and a full
 * page (Installaties > Kaart). Every installation with a location is a
 * marker in the colour of its status; hovering shows its base
 * information, clicking opens it. The legend filters on status.
 */
import { Component, onMounted, onWillUnmount, useRef, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { addTileLayer, DEFAULT_BOUNDS, escapeHtml, loadLeaflet, statusIcon } from "./leaflet_loader";

export class InstallationMap extends Component {
    static template = "serviq_installation_map.InstallationMap";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.mapRef = useRef("map");
        this.markers = [];
        this.fullPage = Boolean(this.props.action);
        this.state = useState({
            loading: true,
            error: false,
            states: [],
            counts: {},
            missing: 0,
            missingIds: [],
            hidden: {},
        });
        onMounted(() => {
            if (this.fullPage) {
                this.init();
                return;
            }
            // On the overview, only start once the map is on screen so it
            // never competes with the dashboard figures.
            this.observer = new IntersectionObserver((entries) => {
                if (entries.some((entry) => entry.isIntersecting)) {
                    this.observer.disconnect();
                    this.observer = null;
                    this.init();
                }
            });
            this.observer.observe(this.mapRef.el);
        });
        onWillUnmount(() => {
            this.destroyed = true;
            if (this.observer) {
                this.observer.disconnect();
            }
            if (this.map) {
                this.map.remove();
                this.map = null;
            }
        });
    }

    async init() {
        try {
            const [{ L, tiles }, data] = await Promise.all([
                loadLeaflet(this.orm),
                this.orm.call("serviq.installation", "get_map_overview_data", []),
            ]);
            if (this.destroyed) {
                return;
            }
            this.state.states = data.states;
            this.state.missing = data.missing;
            this.state.missingIds = data.missing_ids;
            const counts = {};
            for (const inst of data.installations) {
                counts[inst.state] = (counts[inst.state] || 0) + 1;
            }
            this.state.counts = counts;
            this.renderMap(L, tiles, data.installations);
        } catch (error) {
            console.error("[Serviq] installation map failed", error);
            if (!this.destroyed) {
                this.state.error = true;
            }
        }
        if (!this.destroyed) {
            this.state.loading = false;
        }
    }

    renderMap(L, tiles, installations) {
        const el = this.mapRef.el;
        if (!L || !el) {
            return;
        }
        this.map = L.map(el, { scrollWheelZoom: this.fullPage });
        addTileLayer(L, this.map, tiles);
        const points = [];
        for (const inst of installations) {
            const marker = L.marker([inst.latitude, inst.longitude], {
                icon: statusIcon(L, inst.state),
            });
            marker.bindTooltip(this.tooltipHtml(inst), {
                className: "sq-map-tooltip",
                direction: "top",
                offset: [0, -10],
            });
            marker.on("click", () => this.openInstallation(inst.id));
            marker.sqState = inst.state;
            marker.sqId = inst.id;
            marker.addTo(this.map);
            this.markers.push(marker);
            points.push([inst.latitude, inst.longitude]);
        }
        if (points.length) {
            this.map.fitBounds(points, { padding: [30, 30], maxZoom: 13 });
        } else {
            this.map.fitBounds(DEFAULT_BOUNDS);
        }
    }

    /** Base information of an installation, shown when hovering. */
    tooltipHtml(inst) {
        const line = (icon, value) => value
            ? `<div class="sq-map-tooltip-line"><i class="fa ${icon}"></i>${escapeHtml(value)}</div>`
            : "";
        return (
            `<div class="sq-map-tooltip-top">` +
                `<strong>${escapeHtml(inst.code)}</strong>` +
                `<span class="sq-map-status sq-map-state-${escapeHtml(inst.state || "none")}">${escapeHtml(inst.stateLabel || "-")}</span>` +
            `</div>` +
            `<div class="sq-map-tooltip-product">${escapeHtml(inst.product)}</div>` +
            line("fa-tag", inst.category) +
            line("fa-user", inst.customer + (inst.location ? ", " + inst.location : "")) +
            line("fa-truck", inst.distributor) +
            line("fa-wrench", inst.installer)
        );
    }

    get filtered() {
        return this.state.states.some(([key]) => this.state.hidden[key]);
    }

    /** Legend click. With every status shown, the first click shows only
     *  that status; from there on each click adds / removes one. Hiding
     *  the last one shows them all again. */
    toggleState(key) {
        const keys = this.state.states.map(([k]) => k);
        if (!this.filtered) {
            for (const k of keys) {
                this.state.hidden[k] = k !== key;
            }
        } else {
            this.state.hidden[key] = !this.state.hidden[key];
            if (keys.every((k) => this.state.hidden[k])) {
                this.state.hidden = {};
            }
        }
        this.applyFilter();
    }

    showAll() {
        this.state.hidden = {};
        this.applyFilter();
    }

    applyFilter() {
        if (!this.map) {
            return;
        }
        for (const marker of this.markers) {
            const visible = !this.state.hidden[marker.sqState];
            if (visible && !this.map.hasLayer(marker)) {
                marker.addTo(this.map);
            } else if (!visible && this.map.hasLayer(marker)) {
                marker.remove();
            }
        }
    }

    /** Open an installation; the form pager browses the installations
     *  shown on the map. */
    openInstallation(installationId) {
        const resIds = this.markers
            .filter((marker) => this.map.hasLayer(marker))
            .map((marker) => marker.sqId);
        this.action.doAction(
            {
                type: "ir.actions.act_window",
                res_model: "serviq.installation",
                res_id: installationId,
                views: [[false, "form"]],
                target: "current",
            },
            { props: { resIds } }
        );
    }

    /** The installations that are not on the map, to complete them. */
    openMissing() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Installaties zonder locatie"),
            res_model: "serviq.installation",
            domain: [["id", "in", this.state.missingIds]],
            views: [[false, "list"], [false, "form"]],
            target: "current",
        });
    }
}

registry.category("serviq_installation_overview_panels").add("installation_map", InstallationMap);
registry.category("actions").add("serviq_installation_map.map", InstallationMap);
