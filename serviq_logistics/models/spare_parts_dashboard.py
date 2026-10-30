from odoo import models, api

from .labels import product_types, segment_domain, state_label
from odoo.tools import html2plaintext
from datetime import datetime, time
from .dashboard_access import check_dashboard_access


class SparePartsDashboard(models.AbstractModel):
    _name = 'serviq.logistics.spare'
    _description = 'Logistiek: leveringen van reserveonderdelen'

    # Outgoing pickings shipping spare parts are considered spare-part
    # deliveries. A product is a spare part when its component role is
    # flagged "Reserveonderdeel" (serviq.component.role.is_spare_part).
    # Optionally the deliveries are limited to the spare parts of some
    # suppliers (system parameter below, comma separated partner ids, set
    # in Voorraad > Instellingen; empty = all spare parts): a move counts when its stock is owned by
    # one of them (consignment) or when one of them is a vendor of the
    # product.
    _PICKING_STATES = ('assigned', 'confirmed', 'waiting', 'done')
    _SUPPLIER_PARAM = 'serviq_logistics.spare_supplier_ids'

    @staticmethod
    def _clean_text(value):
        """Coerce description fields (which may be Html/Markup) to plain text."""
        if not value:
            return ''
        try:
            text = html2plaintext(value)
        except Exception:
            text = str(value)
        return (text or '').strip()

    @staticmethod
    def _parse_date(value, end_of_day=False):
        """Parse 'YYYY-MM-DD' into a datetime, or return None.

        ``end_of_day`` extends the timestamp to 23:59:59 so the filter
        is inclusive of the chosen end date.
        """
        if not value:
            return None
        try:
            day = datetime.strptime(value, '%Y-%m-%d').date()
        except (TypeError, ValueError):
            return None
        return datetime.combine(day, time.max if end_of_day else time.min)

    def _supplier_ids(self):
        """Partner ids of the configured spare-part suppliers (commercial
        entities and their contacts), or an empty list for "all"."""
        value = self.env['ir.config_parameter'].sudo().get_param(self._SUPPLIER_PARAM) or ''
        ids = []
        for part in value.replace(';', ',').split(','):
            part = part.strip()
            if part.isdigit():
                ids.append(int(part))
        if not ids:
            return []
        Partner = self.env['res.partner'].sudo().with_context(active_test=False)
        partners = Partner.browse(ids).exists()
        return Partner.search([('commercial_partner_id', 'in', partners.commercial_partner_id.ids)]).ids \
            + partners.ids

    def _spare_move_domain(self, supplier_ids, prefix='move_ids.'):
        """Domain on stock.picking (prefix 'move_ids.') or stock.move
        (prefix '') selecting the spare-part moves."""
        domain = [(prefix + 'product_id.product_tmpl_id.serviq_role_id.is_spare_part', '=', True)]
        if supplier_ids:
            domain += [
                '|',
                (prefix + 'move_line_ids.owner_id', 'in', supplier_ids),
                (prefix + 'product_id.product_tmpl_id.seller_ids.partner_id', 'in', supplier_ids),
            ]
        return domain

    def _picking_domain(self, search_term=None, date_from=None, date_to=None, subgroup=None):
        supplier_ids = self._supplier_ids()
        domain = [
            ('picking_type_code', '=', 'outgoing'),
            ('state', 'in', list(self._PICKING_STATES)),
        ] + self._spare_move_domain(supplier_ids)
        domain += segment_domain(subgroup, 'move_ids.product_id.product_tmpl_id')
        dt_from = self._parse_date(date_from, end_of_day=False)
        dt_to = self._parse_date(date_to, end_of_day=True)
        if dt_from:
            domain.append(('scheduled_date', '>=', dt_from))
        if dt_to:
            domain.append(('scheduled_date', '<=', dt_to))
        if search_term:
            domain += [
                '|', '|', '|', '|',
                ('name', 'ilike', search_term),
                ('partner_id.name', 'ilike', search_term),
                ('partner_id.commercial_partner_id.name', 'ilike', search_term),
                ('carrier_tracking_ref', 'ilike', search_term),
                ('move_ids.product_id.name', 'ilike', search_term),
            ]
        return domain

    def _is_spare_move(self, move, supplier_ids):
        """True when `move` ships a spare part (of one of the configured
        suppliers, when set)."""
        tmpl = move.product_id.product_tmpl_id
        if not tmpl.serviq_role_id.is_spare_part:
            return False
        if not supplier_ids:
            return True
        supplier_set = set(supplier_ids)
        if any(ml.owner_id.id in supplier_set for ml in move.move_line_ids):
            return True
        return any(s.partner_id.id in supplier_set for s in tmpl.seller_ids)

    def _shipped_qty(self, move, supplier_ids):
        """Quantity shipped by a done move: restricted to the move lines of
        the supplier-owned stock when the move only matches through the
        owner, otherwise the whole move."""
        if supplier_ids:
            supplier_set = set(supplier_ids)
            vendor = any(s.partner_id.id in supplier_set
                         for s in move.product_id.product_tmpl_id.seller_ids)
            if not vendor:
                return sum(ml.quantity for ml in move.move_line_ids
                           if ml.owner_id.id in supplier_set)
        return move.quantity

    @api.model
    def get_spare_stock_data(self, search_term=None, date_from=None, date_to=None, subgroup=None):
        """Return spare-parts deliveries grouped by client (commercial partner)."""
        check_dashboard_access(self.env, 'spare')
        Picking = self.env['stock.picking'].sudo()
        supplier_ids = self._supplier_ids()

        pickings = Picking.search(
            self._picking_domain(search_term, date_from, date_to, subgroup),
            order='partner_id, scheduled_date desc, id desc',
        )

        customer_map = {}
        for pick in pickings:
            # Only keep moves shipping spare parts; skip the picking
            # entirely if there are none (defensive — domain already enforces it).
            spare_moves = [
                m for m in pick.move_ids
                if self._is_spare_move(m, supplier_ids)
            ]
            if not spare_moves:
                continue

            partner = pick.partner_id.commercial_partner_id or pick.partner_id
            pid = partner.id or 0
            if pid not in customer_map:
                customer_map[pid] = {
                    'partner_id': pid,
                    'partner_name': partner.display_name or '(geen klant)',
                    'country': partner.country_id.name or '',
                    'pickings': [],
                    'total_pickings': 0,
                    'done_pickings': 0,
                    'pending_pickings': 0,
                    'total_qty': 0.0,
                }
            entry = customer_map[pid]
            entry['total_pickings'] += 1
            if pick.state == 'done':
                entry['done_pickings'] += 1
            else:
                entry['pending_pickings'] += 1

            moves = []
            picking_qty = 0.0
            for move in spare_moves:
                if pick.state == 'done':
                    qty = self._shipped_qty(move, supplier_ids)
                else:
                    qty = move.product_uom_qty
                picking_qty += qty or 0.0
                product = move.product_id
                description = (
                    self._clean_text(product.description_sale)
                    or self._clean_text(move.description_picking)
                    or self._clean_text(product.product_tmpl_id.description)
                    or self._clean_text(product.description)
                )
                moves.append({
                    'move_id': move.id,
                    'product_id': product.id,
                    'product_name': product.name or product.display_name or '',
                    'default_code': product.default_code or '',
                    'description': description,
                    'product_uom_qty': move.product_uom_qty,
                    'quantity': move.quantity,
                    'qty_shipped': qty,
                    'uom': move.product_uom.name if move.product_uom else '',
                    'state': move.state,
                })
            entry['total_qty'] += picking_qty

            departure = pick.date_done or pick.scheduled_date
            entry['pickings'].append({
                'picking_id': pick.id,
                'picking_name': pick.name,
                'state': pick.state,
                'state_label': state_label(pick),
                'scheduled_date': pick.scheduled_date.strftime('%Y-%m-%d %H:%M') if pick.scheduled_date else '',
                'date_done': pick.date_done.strftime('%Y-%m-%d %H:%M') if pick.date_done else '',
                'departure_time': departure.strftime('%Y-%m-%d %H:%M') if departure else '',
                'carrier': pick.carrier_id.name if pick.carrier_id else '',
                'tracking_ref': pick.carrier_tracking_ref or '',
                'origin': pick.origin or '',
                'partner_contact': pick.partner_id.name or '',
                'moves': moves,
                'product_types': product_types(spare_moves),
                'move_count': len(moves),
                'total_qty': picking_qty,
            })

        result = sorted(customer_map.values(), key=lambda x: x['partner_name'])
        return result

    @api.model
    def get_spare_stock_summary(self, date_from=None, date_to=None, subgroup=None):
        """Top-line counters for the spare parts dashboard."""
        check_dashboard_access(self.env, 'spare')
        Picking = self.env['stock.picking'].sudo()
        supplier_ids = self._supplier_ids()

        pickings = Picking.search(self._picking_domain(date_from=date_from, date_to=date_to, subgroup=subgroup))

        total = len(pickings)
        done = len(pickings.filtered(lambda p: p.state == 'done'))
        pending = total - done
        clients = len(set(pickings.mapped('partner_id.commercial_partner_id.id')))

        product_ids = set()
        for pick in pickings:
            for move in pick.move_ids:
                if self._is_spare_move(move, supplier_ids):
                    product_ids.add(move.product_id.id)

        return {
            'total_pickings': total,
            'done_pickings': done,
            'pending_pickings': pending,
            'client_count': clients,
            'product_count': len(product_ids),
        }
