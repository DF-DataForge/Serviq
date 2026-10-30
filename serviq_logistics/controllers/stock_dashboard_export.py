import io
import json
import logging
import re
from datetime import datetime

from odoo import http
from odoo.http import request, content_disposition

from ..models.labels import type_labels

_logger = logging.getLogger(__name__)

# Characters that the OOXML spec / Excel reject.
# - Below 0x20 except \t \n \r
# - Unpaired surrogates (\uD800-\uDFFF) — must never appear in xlsx XML
# - Unicode noncharacters ￾ and ￿
_ILLEGAL_XLSX_CHARS = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\ud800-\udfff￾￿]"
)

# Excel's hard cap for a single cell value.
_MAX_CELL_LEN = 32000


def _safe(value):
    """Make a value safe to write to an .xlsx cell.

    Returns None for empty/falsy values so openpyxl emits a truly empty
    cell rather than ``<c t="inlineStr"/>`` (which is invalid OOXML and
    causes Excel to display a "we found a problem" repair dialog).
    """
    if value is None or value is False:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    text = _ILLEGAL_XLSX_CHARS.sub("", str(value))
    if not text:
        return None
    if len(text) > _MAX_CELL_LEN:
        text = text[:_MAX_CELL_LEN]
    return text

try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
except ImportError:
    Workbook = None

RECEPTION_LABELS = {
    "fully_received": "Volledig ontvangen",
    "partially_received": "Deels ontvangen",
    "waiting": "Wachtend",
}

DELIVERY_LABELS = {
    "fully_delivered": "Volledig geleverd",
    "partially_delivered": "Deels geleverd",
    "waiting": "Wachtend",
}


class StockDashboardExport(http.Controller):

    HEADER_FONT = Font(bold=True, color="FFFFFF", size=11)
    HEADER_FILL = PatternFill(start_color="714B67", end_color="714B67", fill_type="solid")
    HEADER_ALIGN = Alignment(horizontal="center", vertical="center", wrap_text=True)
    SECTION_FONT = Font(bold=True, size=11)
    SECTION_FILL = PatternFill(start_color="F1F3F5", end_color="F1F3F5", fill_type="solid")
    THIN_BORDER = Border(
        bottom=Side(style="thin", color="DEE2E6"),
    )

    TAB_LABELS = {
        "own": "Eigen voorraad",
        "consignment": "Consignatievoorraad",
        "customer": "Voorraad bij klanten",
    }

    @http.route("/serviq_logistics/export_excel", type="http", auth="user")
    def export_excel(self, stock_type="own", view_mode="product", search_term="", subgroup="all",
                     product_type="", **kwargs):
        if Workbook is None:
            return request.make_response(
                "openpyxl is required for Excel export. Install it with: pip install openpyxl",
                headers=[("Content-Type", "text/plain")],
            )

        dashboard = request.env["serviq.logistics.stock"]
        search = search_term or None

        wb = Workbook()
        ws = wb.active

        tab_label = self.TAB_LABELS.get(stock_type, stock_type)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

        # product_type: the type filter of the dashboard ("none" = no type)
        def type_ok(item):
            return not product_type or (item.get("product_type") or "none") == product_type

        if view_mode == "location":
            data = dashboard.get_dashboard_data_by_location(stock_type, search, subgroup)
            if product_type:
                for loc in data:
                    loc["products"] = [p for p in loc["products"] if type_ok(p)]
                    loc["total_qty"] = sum(p["qty"] for p in loc["products"])
                    loc["product_count"] = len(loc["products"])
                    loc["serial_count"] = sum(len(p["serial_numbers"]) for p in loc["products"])
                data = [loc for loc in data if loc["products"]]
            self._write_location_view(ws, data, stock_type, tab_label, timestamp)
        else:
            data = [p for p in dashboard.get_dashboard_data(stock_type, search, subgroup) if type_ok(p)]
            self._write_product_view(ws, data, stock_type, tab_label, timestamp,
                                     type_labels(request.env))

        # Auto-width columns
        for col in ws.columns:
            max_len = 0
            col_letter = col[0].column_letter
            for cell in col:
                if cell.value:
                    max_len = max(max_len, len(str(cell.value)))
            ws.column_dimensions[col_letter].width = min(max_len + 4, 50)

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        safe_tab = stock_type.replace(" ", "_")
        filename = f"stock_dashboard_{safe_tab}_{view_mode}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"

        return request.make_response(
            output.getvalue(),
            headers=[
                ("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
                ("Content-Disposition", content_disposition(filename)),
            ],
        )

    def _style_header_row(self, ws, row, col_count):
        for col in range(1, col_count + 1):
            cell = ws.cell(row=row, column=col)
            cell.font = self.HEADER_FONT
            cell.fill = self.HEADER_FILL
            cell.alignment = self.HEADER_ALIGN

    def _write_product_view(self, ws, data, stock_type, tab_label, timestamp, labels):
        ws.title = tab_label[:31]

        # Title row
        ws.append([f"{tab_label} - per product"])
        ws.cell(row=1, column=1).font = Font(bold=True, size=14)
        ws.append([f"Geëxporteerd: {timestamp}"])
        ws.cell(row=2, column=1).font = Font(italic=True, color="7F8C8D")
        ws.append([])

        # Summary sheet: product-level overview
        headers = ["Product", "Interne ref.", "Type", "Aantal", "Eenheid", "Aantal serienummers"]
        ws.append(headers)
        self._style_header_row(ws, ws.max_row, len(headers))

        for product in data:
            ws.append([
                product["product_name"],
                product["default_code"],
                labels.get(product["product_type"], product["product_type"]),
                product["total_qty"],
                product["uom"],
                product["serial_count"],
            ])

        # Blank separator
        ws.append([])
        ws.append([])

        # Detail section: serial numbers per product
        detail_headers = ["Product", "Serienummer", "Aantal", "Locatie"]
        if stock_type == "consignment":
            detail_headers.append("Eigenaar")
        elif stock_type == "customer":
            detail_headers.append("Klant")

        ws.append(["Details serienummers"])
        ws.cell(row=ws.max_row, column=1).font = Font(bold=True, size=12)
        ws.append(detail_headers)
        self._style_header_row(ws, ws.max_row, len(detail_headers))

        for product in data:
            if not product["serial_numbers"]:
                continue
            for sn in product["serial_numbers"]:
                row = [
                    product["product_name"],
                    sn["lot_name"],
                    sn["quantity"],
                    sn["location"],
                ]
                if stock_type == "consignment":
                    row.append(sn.get("owner", ""))
                elif stock_type == "customer":
                    row.append(sn.get("partner", ""))
                ws.append(row)

    def _write_location_view(self, ws, data, stock_type, tab_label, timestamp):
        ws.title = tab_label[:31]

        # Title
        ws.append([f"{tab_label} - per locatie"])
        ws.cell(row=1, column=1).font = Font(bold=True, size=14)
        ws.append([f"Geëxporteerd: {timestamp}"])
        ws.cell(row=2, column=1).font = Font(italic=True, color="7F8C8D")
        ws.append([])

        # Location summary
        headers = ["Locatie", "Relatie", "Producten", "Totaal aantal", "Aantal serienummers"]
        ws.append(headers)
        self._style_header_row(ws, ws.max_row, len(headers))

        for loc in data:
            ws.append([
                loc["location_name"],
                loc["partner"],
                loc["product_count"],
                loc["total_qty"],
                loc["serial_count"],
            ])

        ws.append([])
        ws.append([])

        # Detail section: products and serials per location
        detail_headers = ["Locatie", "Product", "Interne ref.", "Aantal", "Serienummer"]
        if stock_type == "consignment":
            detail_headers.append("Eigenaar")

        ws.append(["Details voorraad per locatie"])
        ws.cell(row=ws.max_row, column=1).font = Font(bold=True, size=12)
        ws.append(detail_headers)
        self._style_header_row(ws, ws.max_row, len(detail_headers))

        for loc in data:
            for prod in loc["products"]:
                if prod["serial_numbers"]:
                    for sn in prod["serial_numbers"]:
                        row = [
                            loc["location_name"],
                            prod["product_name"],
                            prod["default_code"],
                            sn["quantity"],
                            sn["lot_name"],
                        ]
                        if stock_type == "consignment":
                            row.append(sn.get("owner", ""))
                        ws.append(row)
                else:
                    row = [
                        loc["location_name"],
                        prod["product_name"],
                        prod["default_code"],
                        prod["qty"],
                        "",
                    ]
                    if stock_type == "consignment":
                        row.append("")
                    ws.append(row)

    # ================================================================
    # Incoming Goods Export
    # ================================================================

    @http.route("/serviq_logistics/export_incoming_excel", type="http", auth="user")
    def export_incoming_excel(self, search_term="", subgroup="all", **kwargs):
        if Workbook is None:
            return request.make_response(
                "openpyxl is required. Install with: pip install openpyxl",
                headers=[("Content-Type", "text/plain")],
            )

        dashboard = request.env["serviq.logistics.incoming"]
        search = search_term or None
        data = dashboard.get_incoming_data(search, subgroup)

        wb = Workbook()
        ws = wb.active
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

        ws.title = "Inkomende goederen"
        ws.append(["Inkomende goederen - inkooporders per leverancier"])
        ws.cell(row=1, column=1).font = Font(bold=True, size=14)
        ws.append([f"Geëxporteerd: {timestamp}"])
        ws.cell(row=2, column=1).font = Font(italic=True, color="7F8C8D")
        ws.append([])

        # Summary table
        headers = ["Leverancier", "Inkooporders", "Volledig ontvangen", "Deels ontvangen", "Wachtend"]
        ws.append(headers)
        self._style_header_row(ws, ws.max_row, len(headers))

        for supplier in data:
            ws.append([
                supplier["partner_name"],
                supplier["total_orders"],
                supplier["fully_received"],
                supplier["partially_received"],
                supplier["waiting"],
            ])

        ws.append([])
        ws.append([])

        # Detail: PO lines with receptions
        ws.append(["Details inkooporders"])
        ws.cell(row=ws.max_row, column=1).font = Font(bold=True, size=12)

        detail_headers = [
            "Leverancier", "PO-nummer", "Orderdatum", "Geplande datum", "Bron",
            "Bedrag", "Ontvangststatus", "Ontvangst", "Status ontvangst",
            "Gepland", "Afgewerkt op", "Trackingref.", "Documenten",
        ]
        ws.append(detail_headers)
        self._style_header_row(ws, ws.max_row, len(detail_headers))

        for supplier in data:
            for po in supplier["purchase_orders"]:
                if po["pickings"]:
                    for pick in po["pickings"]:
                        doc_names = ", ".join(d["name"] for d in pick["documents"])
                        ws.append([
                            supplier["partner_name"],
                            po["po_name"],
                            po["date_order"],
                            po["date_planned"],
                            po["origin"],
                            po["amount_total"],
                            RECEPTION_LABELS.get(po["reception_status"], po["reception_status"]),
                            pick["picking_name"],
                            pick["state_label"],
                            pick["scheduled_date"],
                            pick["date_done"],
                            pick["carrier_tracking_ref"],
                            doc_names,
                        ])
                else:
                    ws.append([
                        supplier["partner_name"],
                        po["po_name"],
                        po["date_order"],
                        po["date_planned"],
                        po["origin"],
                        po["amount_total"],
                        RECEPTION_LABELS.get(po["reception_status"], po["reception_status"]),
                        "", "", "", "", "", "",
                    ])

        self._auto_width(ws)
        return self._make_excel_response(wb, "incoming_goods")

    # ================================================================
    # Outgoing Goods Export
    # ================================================================

    @http.route("/serviq_logistics/export_outgoing_excel", type="http", auth="user")
    def export_outgoing_excel(self, search_term="", subgroup="all", **kwargs):
        if Workbook is None:
            return request.make_response(
                "openpyxl is required. Install with: pip install openpyxl",
                headers=[("Content-Type", "text/plain")],
            )

        dashboard = request.env["serviq.logistics.outgoing"]
        search = search_term or None
        data = dashboard.get_outgoing_data(search, subgroup)

        wb = Workbook()
        ws = wb.active
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

        ws.title = "Uitgaande goederen"
        ws.append(["Uitgaande goederen - verkooporders per klant"])
        ws.cell(row=1, column=1).font = Font(bold=True, size=14)
        ws.append([f"Geëxporteerd: {timestamp}"])
        ws.cell(row=2, column=1).font = Font(italic=True, color="7F8C8D")
        ws.append([])

        # Summary table
        headers = ["Klant", "Verkooporders", "Volledig geleverd", "Deels geleverd", "Wachtend"]
        ws.append(headers)
        self._style_header_row(ws, ws.max_row, len(headers))

        for customer in data:
            ws.append([
                customer["partner_name"],
                customer["total_orders"],
                customer["fully_delivered"],
                customer["partially_delivered"],
                customer["waiting"],
            ])

        ws.append([])
        ws.append([])

        # Detail: SO lines with deliveries and moves
        ws.append(["Details leveringen verkooporders"])
        ws.cell(row=ws.max_row, column=1).font = Font(bold=True, size=12)

        detail_headers = [
            "Klant", "SO-nummer", "Orderdatum", "Klantref.", "Bedrag",
            "Leverstatus", "Type transfer", "Transfer", "Status transfer",
            "Gepland", "Afgewerkt op", "Product", "Gevraagd", "Afgewerkt aantal", "Eenheid",
            "Documenten",
        ]
        ws.append(detail_headers)
        self._style_header_row(ws, ws.max_row, len(detail_headers))

        for customer in data:
            for so in customer["sale_orders"]:
                if so["pickings"]:
                    for pick in so["pickings"]:
                        doc_names = ", ".join(d["name"] for d in pick["documents"])
                        if pick["moves"]:
                            for move in pick["moves"]:
                                ws.append([
                                    customer["partner_name"],
                                    so["so_name"],
                                    so["date_order"],
                                    so["client_order_ref"],
                                    so["amount_total"],
                                    DELIVERY_LABELS.get(so["delivery_status"], so["delivery_status"]),
                                    pick.get("picking_type_label", ""),
                                    pick["picking_name"],
                                    pick["state_label"],
                                    pick["scheduled_date"],
                                    pick["date_done"],
                                    move["product_name"],
                                    move["product_uom_qty"],
                                    move["quantity"],
                                    move["uom"],
                                    doc_names,
                                ])
                        else:
                            ws.append([
                                customer["partner_name"],
                                so["so_name"],
                                so["date_order"],
                                so["client_order_ref"],
                                so["amount_total"],
                                DELIVERY_LABELS.get(so["delivery_status"], so["delivery_status"]),
                                pick.get("picking_type_label", ""),
                                pick["picking_name"],
                                pick["state_label"],
                                pick["scheduled_date"],
                                pick["date_done"],
                                "", "", "", "",
                                doc_names,
                            ])
                else:
                    ws.append([
                        customer["partner_name"],
                        so["so_name"],
                        so["date_order"],
                        so["client_order_ref"],
                        so["amount_total"],
                        DELIVERY_LABELS.get(so["delivery_status"], so["delivery_status"]),
                        "", "", "", "", "", "", "", "", "", "",
                    ])

        self._auto_width(ws)
        return self._make_excel_response(wb, "outgoing_goods")

    # ================================================================
    # Spare parts deliveries export - one row per shipped spare part
    # ================================================================

    SPARE_HEADERS = [
        "#",
        "Klant",
        "Land",
        "Adres",
        "Telefoon",
        "Productcode",
        "Product",
        "Omschrijving",
        "Verzonden aantal",
        "Vervoerder",
        "Trackingnummer",
        "Verzendkosten",
        "Vertrekdatum",
        "Aankomstdatum",
    ]

    @http.route("/serviq_logistics/export_spare_stock_excel", type="http", auth="user")
    def export_spare_stock_excel(self, search_term="", date_from="", date_to="", subgroup="all", **kwargs):
        if Workbook is None:
            return request.make_response(
                "openpyxl is required. Install with: pip install openpyxl",
                headers=[("Content-Type", "text/plain")],
            )

        try:
            return self._build_spare_stock_excel(search_term, date_from, date_to, subgroup)
        except Exception as exc:
            _logger.exception("Spare parts Excel export failed")
            return request.make_response(
                f"De verzendlijst kon niet aangemaakt worden: {exc}",
                headers=[("Content-Type", "text/plain; charset=utf-8")],
                status=500,
            )

    def _build_spare_stock_excel(self, search_term, date_from="", date_to="", subgroup="all"):
        dashboard = request.env["serviq.logistics.spare"]
        Partner = request.env["res.partner"].sudo()
        data = dashboard.get_spare_stock_data(
            search_term or None,
            date_from or None,
            date_to or None,
            subgroup or None,
        )

        wb = Workbook()
        ws = wb.active
        ws.title = "Verzendlijst"

        # Pre-size columns so wrap_text has room to work
        column_widths = {
            "A": 6,   # #
            "B": 22,  # Customer
            "C": 14,  # Country
            "D": 35,  # Address
            "E": 18,  # Telephone
            "F": 16,  # Product code
            "G": 28,  # Product
            "H": 45,  # Specifications
            "I": 12,  # Qty
            "J": 18,  # Courier
            "K": 20,  # Track number
            "L": 14,  # Courier fee
            "M": 20,  # Departure
            "N": 20,  # Arrival
        }
        for letter, width in column_widths.items():
            ws.column_dimensions[letter].width = width

        ws.append([_safe(h) for h in self.SPARE_HEADERS])
        self._style_header_row(ws, 1, len(self.SPARE_HEADERS))

        wrap_alignment = Alignment(wrap_text=True, vertical="top")

        partner_cache = {}

        def get_partner(pid):
            if pid not in partner_cache:
                partner_cache[pid] = Partner.browse(pid) if pid else Partner
            return partner_cache[pid]

        line_no = 0
        for customer in data:
            partner = get_partner(customer.get("partner_id"))
            address_parts = [
                partner.street or "",
                partner.street2 or "",
                " ".join(p for p in [partner.zip or "", partner.city or ""] if p),
            ]
            address = "\n".join(p for p in address_parts if p)
            phone = partner.phone or ""

            for pick in customer.get("pickings", []):
                for move in pick.get("moves", []):
                    line_no += 1
                    row_values = [
                        line_no,
                        _safe(customer.get("partner_name")),
                        _safe(customer.get("country")),
                        _safe(address),
                        _safe(phone),
                        _safe(move.get("default_code")),
                        _safe(move.get("product_name")),
                        _safe(move.get("description")),
                        _safe(move.get("qty_shipped")),
                        _safe(pick.get("carrier")),
                        _safe(pick.get("tracking_ref")),
                        None,  # Courier fee - not tracked in Odoo
                        _safe(pick.get("departure_time")),
                        None,  # Arrival time - not tracked
                    ]
                    ws.append(row_values)
                    current_row = ws.max_row
                    for col_letter in ("D", "G", "H"):
                        ws[f"{col_letter}{current_row}"].alignment = wrap_alignment

        return self._make_excel_response(wb, "spare_parts_shipping_list")

    # ================================================================
    # Helpers
    # ================================================================

    def _auto_width(self, ws):
        for col in ws.columns:
            max_len = 0
            col_letter = col[0].column_letter
            for cell in col:
                if cell.value:
                    max_len = max(max_len, len(str(cell.value)))
            ws.column_dimensions[col_letter].width = min(max_len + 4, 50)

    def _make_excel_response(self, wb, prefix):
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        filename = f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        return request.make_response(
            output.getvalue(),
            headers=[
                ("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
                ("Content-Disposition", content_disposition(filename)),
            ],
        )
