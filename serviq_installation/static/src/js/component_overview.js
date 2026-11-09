/** @odoo-module **/
/*
 * Components of an installation in the style of the installer portal:
 * components holding a sub-installation as cards with their
 * sub-components, the other components per rack (when racks are used)
 * and per role, in the order of the roles. The serial, the serial photo
 * and the note are edited in place on the component lines and saved with
 * the form; a switch shows the regular list.
 */
import { onWillStart, onWillUpdateProps, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { getDataURLFromFile } from "@web/core/utils/urls";
import { X2ManyField, x2ManyField } from "@web/views/fields/x2many/x2many_field";

/** Name of a many2one value, as read by the record ({id, display_name})
 *  or by search_read ([id, name]). */
function m2oName(value) {
    if (Array.isArray(value)) {
        return value[1] || "";
    }
    return (value && value.display_name) || "";
}

function m2oId(value) {
    if (Array.isArray(value)) {
        return value[0] || false;
    }
    return (value && value.id) || false;
}

export class ComponentOverviewField extends X2ManyField {
    static template = "serviq_installation.ComponentOverviewField";

    setup() {
        super.setup();
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.m2oName = m2oName;
        this.overview = useState({ mode: "overview", subLines: {} });
        onWillStart(() => this.loadSubLines(this.props));
        onWillUpdateProps((nextProps) => this.loadSubLines(nextProps));
    }

    get parentData() {
        return this.props.record.data;
    }

    get canEdit() {
        return !this.props.readonly && !this.parentData.is_locked;
    }

    /** Components of the sub-installations, read-only, like the portal. */
    async loadSubLines(props) {
        const list = props.record.data[props.name];
        const ids = [
            ...new Set(
                list.records.map((rec) => m2oId(rec.data.sub_installation_id)).filter(Boolean)
            ),
        ];
        // Only read again when the set of sub-installations changes.
        const key = ids.sort((a, b) => a - b).join(",");
        if (key === this.subLinesKey) {
            return;
        }
        this.subLinesKey = key;
        if (!ids.length) {
            this.overview.subLines = {};
            return;
        }
        const lines = await this.orm.searchRead(
            "serviq.installation.line",
            [["installation_id", "in", ids]],
            ["installation_id", "product_tmpl_id", "lot_id", "rack_number"]
        );
        const subLines = {};
        for (const line of lines) {
            const key = m2oId(line.installation_id);
            (subLines[key] = subLines[key] || []).push(line);
        }
        this.overview.subLines = subLines;
    }

    subLinesOf(rec) {
        return this.overview.subLines[m2oId(rec.data.sub_installation_id)] || [];
    }

    /** Group the components: holders of a sub-installation, then the
     *  components without rack per role, then per rack. Roles follow
     *  their sequence; components without role come last. */
    get groups() {
        const byRole = (records) => {
            const roles = new Map();
            for (const rec of records) {
                const id = m2oId(rec.data.role_id) || 0;
                if (!roles.has(id)) {
                    roles.set(id, {
                        id,
                        name: m2oName(rec.data.role_id) || _t("Overige componenten"),
                        sequence: id ? rec.data.role_sequence || 0 : Infinity,
                        records: [],
                    });
                }
                roles.get(id).records.push(rec);
            }
            return [...roles.values()].sort((a, b) => a.sequence - b.sequence || a.id - b.id);
        };
        const holders = [];
        const loose = [];
        const racks = new Map();
        for (const rec of this.list.records) {
            if (rec.data.sub_installation_id) {
                holders.push(rec);
            } else if (rec.data.rack_number) {
                const number = rec.data.rack_number;
                if (!racks.has(number)) {
                    racks.set(number, { number, records: [] });
                }
                racks.get(number).records.push(rec);
            } else {
                loose.push(rec);
            }
        }
        const sortedRacks = [...racks.values()].sort((a, b) => a.number - b.number);
        for (const rack of sortedRacks) {
            rack.records = byRole(rack.records).flatMap((role) => role.records);
        }
        return { holders, roles: byRole(loose), racks: sortedRacks };
    }

    /** Colour of a role, to tell the roles apart (left border of a card). */
    roleStyle(rec) {
        const id = m2oId(rec.data.role_id);
        return id ? `border-left-color: hsl(${(id * 67) % 360}, 50%, 50%);` : "";
    }

    photoUrl(rec) {
        const value = rec.data.serial_photo;
        if (!value) {
            return "";
        }
        // A freshly uploaded photo holds the image itself; a saved one only
        // its size (binary fields are read with bin_size).
        if (typeof value === "string" && value.length > 200) {
            return `data:image/png;base64,${value}`;
        }
        return rec.resId
            ? `/web/image/serviq.installation.line/${rec.resId}/serial_photo?unique=${encodeURIComponent(value)}`
            : "";
    }

    async update(rec, fieldName, value) {
        await rec.update({ [fieldName]: (value || "").trim() || false });
    }

    /** Swap the serial: the typed serial must exist and be usable for this
     *  component (distributor stock, product, not on another installation),
     *  like the serial dropdown of the list. The save still runs the full
     *  serial check of the component. */
    async updateSerial(rec, ev) {
        const input = ev.target;
        const name = input.value.trim();
        const current = m2oName(rec.data.lot_id);
        if (name === current) {
            return;
        }
        if (!name) {
            await rec.update({ lot_id: false });
            return;
        }
        const context = {
            serviq_distributor: m2oId(this.parentData.distributor_id),
            serviq_product_tmpl: m2oId(rec.data.product_tmpl_id),
            serviq_outside_stock: rec.data.search_outside_stock,
        };
        const lots = await this.orm.call("stock.lot", "name_search", [], {
            name,
            operator: "=",
            limit: 2,
            context,
        });
        if (lots.length !== 1) {
            this.notification.add(
                _t(
                    'Serienummer "%s" niet gevonden of niet beschikbaar voor deze component (voorraad distributeur, product, of al op een andere installatie). Een nieuw serienummer maakt u aan in de lijst.',
                    name
                ),
                { type: "danger" }
            );
            input.value = current;
            return;
        }
        await rec.update({ lot_id: { id: lots[0][0], display_name: lots[0][1] } });
    }

    async onPhoto(rec, ev) {
        const file = ev.target.files && ev.target.files[0];
        if (!file) {
            return;
        }
        const dataUrl = await getDataURLFromFile(file);
        await rec.update({
            serial_photo: dataUrl.split(",")[1] || false,
            serial_photo_filename: file.name || false,
        });
        ev.target.value = "";
    }

    /** Component details in a dialog (the component detail form). */
    openDetails(rec) {
        const mode = this.canEdit ? "edit" : "readonly";
        if (this._openRecord) {
            return this._openRecord({ record: rec, mode });
        }
        return this.openRecord(rec);
    }

    /** Open the sub-installation of a component; the installation is
     *  saved first. */
    async openSubInstallation(rec) {
        const id = m2oId(rec.data.sub_installation_id);
        if (!id) {
            return;
        }
        if (!(await this.props.record.save())) {
            return;
        }
        await this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Subcomponenten"),
            res_model: "serviq.installation",
            res_id: id,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

export const componentOverviewField = {
    ...x2ManyField,
    component: ComponentOverviewField,
};

registry.category("fields").add("serviq_component_overview", componentOverviewField);
