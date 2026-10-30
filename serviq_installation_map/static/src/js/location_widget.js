/** @odoo-module **/
/*
 * Map on the installation form: the location of the installation. In edit
 * mode the position can be set by clicking on the map or dragging the
 * marker; it is stored in the latitude / longitude of the installation.
 */
import { Component, onMounted, onWillUnmount, onWillUpdateProps, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { addTileLayer, DEFAULT_BOUNDS, loadLeaflet, statusIcon } from "./leaflet_loader";

export class InstallationLocationMap extends Component {
    static template = "serviq_installation_map.InstallationLocationMap";
    static props = { ...standardWidgetProps };

    setup() {
        this.orm = useService("orm");
        this.mapRef = useRef("map");
        this.state = useState({ error: false });
        onMounted(() => this.init());
        onWillUpdateProps((nextProps) => this.syncMarker(nextProps.record));
        onWillUnmount(() => {
            this.destroyed = true;
            if (this.map) {
                this.map.remove();
                this.map = null;
            }
        });
    }

    get editable() {
        return !this.props.readonly && !this.props.record.data.is_locked;
    }

    get hasLocation() {
        const { latitude, longitude } = this.props.record.data;
        return Boolean(latitude || longitude);
    }

    async init() {
        try {
            const { L, tiles } = await loadLeaflet(this.orm);
            if (this.destroyed || !this.mapRef.el) {
                return;
            }
            this.L = L;
            this.map = L.map(this.mapRef.el, { scrollWheelZoom: false });
            addTileLayer(L, this.map, tiles);
            this.map.on("click", (ev) => {
                if (this.editable) {
                    this.setPosition(ev.latlng);
                }
            });
            this.syncMarker(this.props.record, true);
        } catch (error) {
            console.error("[Serviq] location map failed", error);
            if (!this.destroyed) {
                this.state.error = true;
            }
        }
    }

    /** Marker at the position of `record` (none without location). */
    syncMarker(record, fit = false) {
        if (!this.map) {
            return;
        }
        const { latitude, longitude, state } = record.data;
        if (!latitude && !longitude) {
            if (this.marker) {
                this.marker.remove();
                this.marker = null;
            }
            if (fit) {
                this.map.fitBounds(DEFAULT_BOUNDS);
            }
            return;
        }
        const position = [latitude, longitude];
        if (!this.marker) {
            this.marker = this.L.marker(position, {
                icon: statusIcon(this.L, state),
                draggable: true,
            }).addTo(this.map);
            this.marker.on("dragend", () => this.setPosition(this.marker.getLatLng()));
            fit = true;
        } else {
            this.marker.setLatLng(position);
            this.marker.setIcon(statusIcon(this.L, state));
        }
        if (this.marker.dragging) {
            this.editable ? this.marker.dragging.enable() : this.marker.dragging.disable();
        }
        if (fit) {
            this.map.setView(position, 15);
        }
    }

    setPosition(latlng) {
        this.props.record.update({
            latitude: Math.round(latlng.lat * 1e7) / 1e7,
            longitude: Math.round(latlng.lng * 1e7) / 1e7,
        });
    }
}

export const installationLocationMap = {
    component: InstallationLocationMap,
    fieldDependencies: [
        { name: "latitude", type: "float" },
        { name: "longitude", type: "float" },
        { name: "state", type: "selection" },
        { name: "is_locked", type: "boolean" },
    ],
};

registry.category("view_widgets").add("serviq_installation_location_map", installationLocationMap);
