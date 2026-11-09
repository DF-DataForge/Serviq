/** @odoo-module **/
/*
 * Camera scanner for serial numbers in the Serviq portal: next to every
 * input or select with the 'sq-scan' class a button opens Odoo's barcode
 * dialog (camera of the phone or tablet, barcodes and QR codes).
 *
 * - input: the scanned value is put in the input, which then fires its
 *   usual 'input' / 'change' events so the existing checks (e.g. the live
 *   serial check of a flow) run as if it was typed;
 * - select: the option whose 'data-scan-value' (or else its text) equals
 *   the scanned value is selected and 'change' is fired.
 *
 * The button is hidden when the browser has no camera access. Flows only
 * have to add the 'sq-scan' class to their serial fields.
 */
import { scanBarcode } from "@web/core/barcode/barcode_dialog";
import { isBarcodeScannerSupported } from "@web/core/barcode/barcode_video_scanner";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { Interaction } from "@web/public/interaction";

export class SerialScanner extends Interaction {
    static selector = "input.sq-scan, select.sq-scan";

    start() {
        if (!isBarcodeScannerSupported()) {
            return;
        }
        const field = this.el;
        // Put the button right of the field: reuse its input-group, or
        // wrap the field in one for the time the interaction runs.
        let group = field.parentElement;
        if (!group.classList.contains("input-group")) {
            group = document.createElement("div");
            group.className = "input-group flex-nowrap sq-scan-group";
            if (field.classList.contains("form-control-sm")
                    || field.classList.contains("form-select-sm")) {
                group.classList.add("input-group-sm");
            }
            field.before(group);
            group.append(field);
            this.registerCleanup(() => {
                group.before(field);
                group.remove();
            });
        }
        const button = document.createElement("button");
        button.type = "button";
        button.className = "btn btn-outline-secondary sq-scan-btn";
        button.title = _t("Scan het serienummer met de camera");
        button.setAttribute("aria-label", button.title);
        button.innerHTML = '<i class="fa fa-barcode"></i>';
        field.after(button);
        this.registerCleanup(() => button.remove());
        this.addListener(button, "click", this.onScan);
    }

    async onScan() {
        let code;
        try {
            code = await this.waitFor(scanBarcode(this.env));
        } catch (error) {
            this.services.notification.add(
                (error && error.message) || _t("Scannen is niet gelukt."),
                { type: "danger" }
            );
            return;
        }
        code = (code || "").trim();
        if (!code) {
            return;
        }
        const field = this.el;
        if (field.tagName === "SELECT") {
            const option = [...field.options].find(
                (opt) => opt.value
                    && (opt.dataset.scanValue || opt.textContent).trim() === code
            );
            if (!option) {
                this.services.notification.add(
                    _t("Serienummer %s staat niet in de lijst.", code),
                    { type: "warning" }
                );
                return;
            }
            option.hidden = false;
            field.value = option.value;
        } else {
            field.value = code;
            field.dispatchEvent(new Event("input", { bubbles: true }));
        }
        field.dispatchEvent(new Event("change", { bubbles: true }));
        field.focus();
    }
}

registry
    .category("public.interactions")
    .add("serviq_portal.serial_scanner", SerialScanner);
