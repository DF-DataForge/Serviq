from odoo import models, api

from .labels import product_type, segment_domain, state_label, type_order, type_rank
from odoo.tools.float_utils import float_compare
from .dashboard_access import check_dashboard_access


class SnTrackingDashboard(models.AbstractModel):
    _name = 'serviq.logistics.sn'
    _description = 'Logistiek: serienummers'

    # Confirmed (and locked) purchase orders count as "ordered".
    _PO_CONFIRMED_STATES = ('purchase', 'done')

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------
    def _product_domain(self, subgroup=None, search_term=None):
        """Domain selecting serial-tracked products for the dashboard."""
        domain = [('tracking', '=', 'serial')]
        domain += segment_domain(subgroup, 'product_tmpl_id')
        if search_term:
            domain += [
                '|',
                ('name', 'ilike', search_term),
                ('default_code', 'ilike', search_term),
            ]
        return domain

    def _tracked_products(self, subgroup=None, search_term=None):
        return self.env['product.product'].sudo().search(
            self._product_domain(subgroup, search_term))

    def _installed_lot_map(self):
        """Map lot_id -> installation info for every serial that is
        registered on an installation.

        A serial counts as "installed" when it is registered as a component
        of an installation, i.e. it appears on a serviq.installation.line,
        is linked via stock.lot.serviq_installation_id, or is the main
        serial of a serviq.installation record.
        """
        installed = {}

        def _register(lot, installation):
            if not lot or not installation or lot.id in installed:
                return
            installed[lot.id] = {
                'system_id': installation.id,
                'system_name': installation.name or installation.code or ('INST-%s' % installation.id),
            }

        Line = self.env['serviq.installation.line'].sudo()
        for line in Line.search([('lot_id', '!=', False)]):
            _register(line.lot_id, line.installation_id)

        Lot = self.env['stock.lot'].sudo()
        for lot in Lot.search([('serviq_installation_id', '!=', False)]):
            _register(lot, lot.serviq_installation_id)

        Installation = self.env['serviq.installation'].sudo()
        for installation in Installation.search([('lot_id', '!=', False)]):
            _register(installation.lot_id, installation)

        return installed

    def _new_product_entry(self, product):
        tmpl = product.product_tmpl_id
        return {
            'product_id': product.id,
            'product_name': product.display_name,
            'default_code': product.default_code or '',
            'product_type': product_type(tmpl),
            'subgroup': tmpl.serviq_category_code or '',
            'subgroup_label': tmpl.serviq_category_id.name or '',
            'uom': product.uom_id.name,
        }

    # ------------------------------------------------------------------
    # Segment: ordered items (confirmed purchase orders)
    # ------------------------------------------------------------------
    def _open_po_lines(self, products):
        """Purchase order lines on confirmed POs that still have quantity
        to receive for the given products."""
        lines = self.env['purchase.order.line'].sudo().search([
            ('order_id.state', 'in', list(self._PO_CONFIRMED_STATES)),
            ('product_id', 'in', products.ids),
            ('display_type', '=', False),
        ], order='date_planned, id')
        return lines.filtered(
            lambda l: float_compare(
                l.qty_received, l.product_qty,
                precision_rounding=l.product_id.uom_id.rounding or 0.01) < 0
        )

    def _line_serials(self, line):
        """Serial numbers already linked to a PO line via its receipt moves."""
        serials = []
        seen = set()
        for move in line.move_ids.filtered(lambda m: m.state != 'cancel'):
            for ml in move.move_line_ids:
                if ml.lot_id and ml.lot_id.id not in seen:
                    seen.add(ml.lot_id.id)
                    serials.append({
                        'lot_id': ml.lot_id.id,
                        'lot_name': ml.lot_id.name,
                    })
        return serials

    def _get_ordered_data(self, subgroup=None, search_term=None):
        products = self._tracked_products(subgroup, search_term)
        if not products:
            return []
        lines = self._open_po_lines(products)

        product_map = {}
        for line in lines:
            pid = line.product_id.id
            if pid not in product_map:
                entry = self._new_product_entry(line.product_id)
                entry.update({
                    'ordered_qty': 0.0,
                    'received_qty': 0.0,
                    'pending_qty': 0.0,
                    'order_count': 0,
                    'orders': [],
                })
                product_map[pid] = entry
            entry = product_map[pid]

            order = line.order_id
            received = line.qty_received or 0.0
            pending = max(line.product_qty - received, 0.0)
            entry['ordered_qty'] += line.product_qty
            entry['received_qty'] += received
            entry['pending_qty'] += pending
            entry['order_count'] += 1

            entry['orders'].append({
                'order_id': order.id,
                'order_name': order.name,
                'supplier': order.partner_id.display_name if order.partner_id else '',
                'date_planned': line.date_planned.strftime('%Y-%m-%d') if line.date_planned else '',
                'state': order.state,
                'state_label': state_label(order),
                'qty': line.product_qty,
                'received_qty': received,
                'pending_qty': pending,
                'serial_numbers': self._line_serials(line),
            })

        result = sorted(product_map.values(), key=lambda x: x['product_name'])
        return result

    # ------------------------------------------------------------------
    # Segments: in-house / customer stock (quant based)
    # ------------------------------------------------------------------
    def _segment_quants(self, segment, products):
        domain = [
            ('product_id', 'in', products.ids),
            ('quantity', '>', 0),
            ('location_id.usage', '=', 'internal' if segment == 'inhouse' else 'customer'),
        ]
        return self.env['stock.quant'].sudo().search(domain)

    def _get_inhouse_data(self, subgroup=None, search_term=None):
        products = self._tracked_products(subgroup, search_term)
        if not products:
            return []
        quants = self._segment_quants('inhouse', products)

        product_map = {}
        for quant in quants:
            pid = quant.product_id.id
            if pid not in product_map:
                entry = self._new_product_entry(quant.product_id)
                entry.update({
                    'total_qty': 0.0,
                    'reserved_qty': 0.0,
                    'available_qty': 0.0,
                    'serial_numbers': [],
                })
                product_map[pid] = entry
            entry = product_map[pid]

            entry['total_qty'] += quant.quantity
            entry['reserved_qty'] += quant.reserved_quantity
            if quant.lot_id:
                entry['serial_numbers'].append({
                    'lot_id': quant.lot_id.id,
                    'lot_name': quant.lot_id.name,
                    'location': quant.location_id.complete_name,
                    'quantity': quant.quantity,
                    'reserved': quant.reserved_quantity > 0,
                    'owner': quant.owner_id.name if quant.owner_id else '',
                })

        result = []
        for entry in product_map.values():
            entry['available_qty'] = entry['total_qty'] - entry['reserved_qty']
            entry['serial_count'] = len(entry['serial_numbers'])
            entry['serial_numbers'].sort(key=lambda s: (not s['reserved'], s['lot_name'] or ''))
            result.append(entry)

        result.sort(key=lambda x: x['product_name'])
        return result

    def _get_customer_data(self, subgroup=None, search_term=None):
        """Customer stock grouped per customer location: one card per
        distributor with the delivered products and their installation
        progress."""
        products = self._tracked_products(subgroup, search_term)
        if not products:
            return []
        quants = self._segment_quants('customer', products)
        installed_map = self._installed_lot_map()

        customer_map = {}
        for quant in quants:
            location = quant.location_id
            lid = location.id
            if lid not in customer_map:
                partner = location.partner_id
                customer_map[lid] = {
                    'location_id': lid,
                    'partner_id': partner.id if partner else False,
                    'customer_name': partner.display_name if partner else location.complete_name,
                    'location_name': location.complete_name,
                    'total_qty': 0.0,
                    'serial_count': 0,
                    'installed_count': 0,
                    'products': {},
                }
            entry = customer_map[lid]
            entry['total_qty'] += quant.quantity

            pid = quant.product_id.id
            if pid not in entry['products']:
                prod = self._new_product_entry(quant.product_id)
                prod.update({
                    'qty': 0.0,
                    'serial_count': 0,
                    'installed_count': 0,
                    'serial_numbers': [],
                })
                entry['products'][pid] = prod
            prod = entry['products'][pid]
            prod['qty'] += quant.quantity

            if quant.lot_id:
                system = installed_map.get(quant.lot_id.id)
                prod['serial_count'] += 1
                entry['serial_count'] += 1
                if system:
                    prod['installed_count'] += 1
                    entry['installed_count'] += 1
                prod['serial_numbers'].append({
                    'lot_id': quant.lot_id.id,
                    'lot_name': quant.lot_id.name,
                    'installed': bool(system),
                    'system_id': system['system_id'] if system else False,
                    'system_name': system['system_name'] if system else '',
                })

        order = type_order(self.env)

        result = []
        for entry in customer_map.values():
            products_list = sorted(
                entry['products'].values(), key=lambda x: x['product_name'])
            for prod in products_list:
                prod['serial_numbers'].sort(
                    key=lambda s: (not s['installed'], s['lot_name'] or ''))
            entry['product_count'] = len(products_list)

            # Structure the card per product type: number of items and
            # how many of them are installed, plus the product detail
            # used by the distributor overview.
            types_map = {}
            for prod in products_list:
                ptype = prod['product_type'] or 'none'
                if ptype not in types_map:
                    types_map[ptype] = {
                        'ptype': ptype,
                        'qty': 0.0,
                        'serial_count': 0,
                        'installed_count': 0,
                        'product_count': 0,
                        'products': [],
                    }
                tentry = types_map[ptype]
                tentry['qty'] += prod['qty']
                tentry['serial_count'] += prod['serial_count']
                tentry['installed_count'] += prod['installed_count']
                tentry['product_count'] += 1
                tentry['products'].append(prod)

            entry['types'] = sorted(
                types_map.values(),
                key=lambda t: type_rank(order, t['ptype']))
            del entry['products']
            result.append(entry)

        result.sort(key=lambda x: (x['customer_name'] or '').lower())
        return result

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @api.model
    def get_segment_data(self, segment, subgroup=None, search_term=None):
        """Return product rows for one dashboard segment.

        Args:
            segment: 'ordered', 'inhouse' or 'customer'
            subgroup: 'all' or a segment (installation category code)
            search_term: optional product name / internal reference filter
        """
        check_dashboard_access(self.env, 'sn')
        if segment == 'ordered':
            return self._get_ordered_data(subgroup, search_term)
        if segment == 'inhouse':
            return self._get_inhouse_data(subgroup, search_term)
        if segment == 'customer':
            return self._get_customer_data(subgroup, search_term)
        return []

    @api.model
    def get_summary(self, subgroup=None, search_term=None):
        """Top-line counters for the three segments, honouring the filters."""
        check_dashboard_access(self.env, 'sn')
        products = self._tracked_products(subgroup, search_term)
        empty = {
            'ordered': {'product_count': 0, 'total_qty': 0.0, 'received_qty': 0.0, 'pending_qty': 0.0},
            'inhouse': {'product_count': 0, 'total_qty': 0.0, 'reserved_qty': 0.0},
            'customer': {'product_count': 0, 'total_qty': 0.0, 'installed_count': 0, 'serial_count': 0, 'customer_count': 0},
        }
        if not products:
            return empty

        po_lines = self._open_po_lines(products)
        ordered_qty = sum(po_lines.mapped('product_qty'))
        received_qty = sum(po_lines.mapped('qty_received'))
        empty['ordered'] = {
            'product_count': len(set(po_lines.mapped('product_id.id'))),
            'total_qty': ordered_qty,
            'received_qty': received_qty,
            'pending_qty': max(ordered_qty - received_qty, 0.0),
        }

        inhouse_quants = self._segment_quants('inhouse', products)
        empty['inhouse'] = {
            'product_count': len(set(inhouse_quants.mapped('product_id.id'))),
            'total_qty': sum(inhouse_quants.mapped('quantity')),
            'reserved_qty': sum(inhouse_quants.mapped('reserved_quantity')),
        }

        customer_quants = self._segment_quants('customer', products)
        installed_map = self._installed_lot_map()
        customer_lots = customer_quants.filtered('lot_id').mapped('lot_id')
        installed = len([lot for lot in customer_lots if lot.id in installed_map])
        empty['customer'] = {
            'product_count': len(set(customer_quants.mapped('product_id.id'))),
            'total_qty': sum(customer_quants.mapped('quantity')),
            'installed_count': installed,
            'serial_count': len(customer_lots),
            'customer_count': len(set(customer_quants.mapped('location_id.id'))),
        }
        return empty
