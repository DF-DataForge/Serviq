from datetime import datetime, time
from zoneinfo import ZoneInfo

from odoo import models, fields, api

from .dashboard_cache import cached
from .labels import product_type, segment_domain, type_labels, type_order, type_rank
from .dashboard_access import check_dashboard_access


class StockCards(models.AbstractModel):
    """Available stock as cards per product type (component role), with a
    drill-down per product: own stock only (consignment excluded), live or
    rolled back to the end of a past day, with the reserved, incoming
    (open purchase) and committed (sold, not delivered) quantities when
    live."""
    _name = 'serviq.logistics.stock.cards'
    _description = 'Logistiek: beschikbare voorraad (kaarten)'

    _PO_CONFIRMED_STATES = ('purchase', 'done')
    _SO_CONFIRMED_STATES = ('sale', 'done')

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _period(self, as_of):
        """Reference context of one dashboard run.

        as_of: None/False for the live situation, or a 'YYYY-MM-DD' string.
        Returns (as_of_date or None, reference day, cutoff datetime in UTC
        = end of the as_of day in the user's time zone, or None when
        live)."""
        today = fields.Date.context_today(self)
        if not as_of:
            return None, today, None
        day = fields.Date.to_date(as_of)
        if day >= today:
            return None, today, None
        try:
            tz = ZoneInfo(self.env.context.get('tz') or self.env.user.tz or 'UTC')
        except (ValueError, KeyError):
            tz = ZoneInfo('UTC')
        local_end = datetime.combine(day, time(23, 59, 59)).replace(tzinfo=tz)
        cutoff = local_end.astimezone(ZoneInfo('UTC')).replace(tzinfo=None)
        return day, day, cutoff

    def _svl_available(self):
        """Stock valuation layers exist up to Odoo 18; Odoo 19 values the
        stock differently, then the current product cost is used for a
        past date."""
        return 'stock.valuation.layer' in self.env

    # ------------------------------------------------------------------
    # Stock positions (live or rolled back to a date)
    # ------------------------------------------------------------------
    def _stock_positions_live(self, subgroup):
        """(location, product, owner, qty, value, reserved) per quant, and
        whether the value is exact (always, for the live stock)."""
        Quant = self.env['stock.quant'].sudo()
        quants = Quant.search([
            ('company_id', '=', self.env.company.id),
            ('location_id.usage', '=', 'internal'),
            ('quantity', '!=', 0),
        ] + segment_domain(subgroup))
        has_value = 'value' in Quant._fields
        positions = []
        for quant in quants:
            value = quant.value if has_value \
                else quant.quantity * quant.product_id.standard_price
            positions.append((quant.location_id, quant.product_id, quant.owner_id,
                              quant.quantity, value, quant.reserved_quantity))
        return positions, True

    def _unit_costs_at(self, products, cutoff):
        """Unit cost per product at the cutoff: from the stock valuation
        layers when available (value / quantity of the layers created by
        then), otherwise the current product cost. Returns (costs, exact)."""
        costs = {p.id: p.standard_price for p in products}
        if not self._svl_available() or not products:
            return costs, False
        rows = self.env['stock.valuation.layer'].sudo()._read_group(
            [
                ('company_id', '=', self.env.company.id),
                ('product_id', 'in', products.ids),
                ('create_date', '<=', cutoff),
            ], ['product_id'], ['value:sum', 'quantity:sum'])
        for product, value, qty in rows:
            if qty:
                costs[product.id] = (value or 0.0) / qty
        return costs, True

    def _stock_positions_at(self, subgroup, cutoff):
        """Stock per (location, product, owner) at the cutoff: the current
        quants with every move line done after the cutoff undone."""
        company = self.env.company
        qty = {}
        Quant = self.env['stock.quant'].sudo()
        for quant in Quant.search([
            ('company_id', '=', company.id),
            ('location_id.usage', '=', 'internal'),
            ('quantity', '!=', 0),
        ] + segment_domain(subgroup)):
            key = (quant.location_id.id, quant.product_id.id, quant.owner_id.id)
            qty[key] = qty.get(key, 0.0) + quant.quantity

        MoveLine = self.env['stock.move.line'].sudo()
        uom_field = 'quantity_product_uom' if 'quantity_product_uom' in MoveLine._fields \
            else 'quantity'
        later = MoveLine.search([
            ('company_id', '=', company.id),
            ('state', '=', 'done'),
            ('date', '>', cutoff),
            '|',
            ('location_id.usage', '=', 'internal'),
            ('location_dest_id.usage', '=', 'internal'),
        ] + segment_domain(subgroup))
        for ml in later:
            q = ml[uom_field]
            owner = ml.owner_id.id
            if ml.location_dest_id.usage == 'internal':
                key = (ml.location_dest_id.id, ml.product_id.id, owner)
                qty[key] = qty.get(key, 0.0) - q
            if ml.location_id.usage == 'internal':
                key = (ml.location_id.id, ml.product_id.id, owner)
                qty[key] = qty.get(key, 0.0) + q

        keys = [k for k, v in qty.items() if abs(v) > 1e-6]
        Location = self.env['stock.location'].sudo()
        Product = self.env['product.product'].sudo().with_context(active_test=False)
        Partner = self.env['res.partner'].sudo().with_context(active_test=False)
        locations = {l.id: l for l in Location.browse(list({k[0] for k in keys}))}
        products = Product.browse(list({k[1] for k in keys}))
        product_map = {p.id: p for p in products}
        owners = {o.id: o for o in Partner.browse(list({k[2] for k in keys if k[2]}))}
        costs, exact = self._unit_costs_at(products, cutoff)

        positions = []
        for loc_id, prod_id, owner_id in keys:
            q = qty[(loc_id, prod_id, owner_id)]
            positions.append((locations[loc_id], product_map[prod_id],
                              owners.get(owner_id, Partner), q,
                              q * costs.get(prod_id, 0.0), None))
        return positions, exact

    # ------------------------------------------------------------------
    # Stock cards: per product type, drill-down per product
    # ------------------------------------------------------------------
    def _open_qty_by_product(self, kind, subgroup):
        """Live quantity still to receive (purchase) or still to deliver
        (sale) per product on confirmed orders."""
        if kind == 'purchase':
            Line, states = self.env['purchase.order.line'].sudo(), self._PO_CONFIRMED_STATES
            qty_field, done_field = 'product_qty', 'qty_received'
        else:
            Line, states = self.env['sale.order.line'].sudo(), self._SO_CONFIRMED_STATES
            qty_field, done_field = 'product_uom_qty', 'qty_delivered'
        result = {}
        for line in Line.search([
            ('order_id.state', 'in', list(states)),
            ('order_id.company_id', '=', self.env.company.id),
            ('display_type', '=', False),
            ('product_id.type', '!=', 'service'),
        ] + segment_domain(subgroup)):
            remaining = max(line[qty_field] - line[done_field], 0.0)
            if remaining:
                result[line.product_id.id] = result.get(line.product_id.id, 0.0) + remaining
        return result

    def _new_card(self, product):
        tmpl = product.product_tmpl_id
        return {
            'product_id': product.id,
            'name': product.display_name,
            'code': product.default_code or '',
            'ptype': product_type(tmpl),
            'subgroup': tmpl.serviq_category_code or 'none',
            'qty': 0.0, 'value': 0.0, 'reserved_qty': 0.0, 'warehouses': {},
        }

    def _stock_cards(self, subgroup, as_of):
        as_of_day, _ref_day, cutoff = self._period(as_of)
        company = self.env.company
        own_owners = (False, company.partner_id.id)
        positions, valuation_exact = self._stock_positions_at(subgroup, cutoff) \
            if cutoff else self._stock_positions_live(subgroup)
        live = not cutoff
        incoming = self._open_qty_by_product('purchase', subgroup) if live else {}
        committed = self._open_qty_by_product('sale', subgroup) if live else {}
        labels = type_labels(self.env)
        order = type_order(self.env)

        products = {}
        for location, product, owner, qty, value, reserved in positions:
            if owner.id not in own_owners:
                continue
            entry = products.get(product.id)
            if entry is None:
                entry = products[product.id] = self._new_card(product)
                if not live:
                    entry['reserved_qty'] = None
            entry['qty'] += qty
            entry['value'] += value
            if live and reserved:
                entry['reserved_qty'] += reserved
            wh = location.warehouse_id
            wh_name = wh.name if wh else 'Geen magazijn'
            entry['warehouses'][wh_name] = entry['warehouses'].get(wh_name, 0.0) + qty

        # products only on order / sold, without stock yet, still matter
        # for availability
        missing = (set(incoming) | set(committed)) - set(products)
        for product in self.env['product.product'].sudo().browse(list(missing)):
            products[product.id] = self._new_card(product)

        cards = []
        for entry in products.values():
            pid = entry['product_id']
            qty = entry['qty']
            reserved = entry['reserved_qty']
            entry['available_qty'] = qty - (reserved or 0.0)
            entry['incoming_qty'] = incoming.get(pid, 0.0) if live else None
            entry['committed_qty'] = committed.get(pid, 0.0) if live else None
            entry['free_qty'] = (qty - max(reserved or 0.0, entry['committed_qty'] or 0.0)) if live else None
            entry['unit_cost'] = (entry['value'] / qty) if qty else 0.0
            entry['ptype_label'] = labels.get(entry['ptype'], entry['ptype'])
            entry['warehouses'] = [
                {'name': n, 'qty': q} for n, q in sorted(entry['warehouses'].items(), key=lambda x: -x[1])
                if abs(q) > 1e-6]
            if not qty and not entry['incoming_qty'] and not entry['committed_qty']:
                continue
            cards.append(entry)

        types = {}
        for card in cards:
            t = types.setdefault(card['ptype'], {
                'ptype': card['ptype'], 'label': card['ptype_label'],
                'product_count': 0, 'qty': 0.0, 'value': 0.0,
                'reserved_qty': 0.0 if live else None, 'available_qty': 0.0,
                'incoming_qty': 0.0 if live else None, 'committed_qty': 0.0 if live else None,
                'free_qty': 0.0 if live else None, 'out_of_stock': 0,
            })
            t['product_count'] += 1
            t['qty'] += card['qty']
            t['value'] += card['value']
            t['available_qty'] += card['available_qty']
            if card['qty'] <= 0:
                t['out_of_stock'] += 1
            if live:
                t['reserved_qty'] += card['reserved_qty']
                t['incoming_qty'] += card['incoming_qty']
                t['committed_qty'] += card['committed_qty']
                t['free_qty'] += card['free_qty']
        type_rows = sorted(types.values(), key=lambda t: type_rank(order, t['ptype']))
        cards.sort(key=lambda c: -c['value'])
        return {
            'currency': company.currency_id.name,
            'as_of': fields.Date.to_string(as_of_day) if as_of_day else False,
            'live': live,
            'valuation_exact': valuation_exact,
            'types': type_rows,
            'cards': cards,
        }

    @api.model
    def get_stock_cards(self, subgroup=None, as_of=None, force=False):
        """Available stock as cards per product type, with the cards per
        product for the drill-down. Own stock only (consignment excluded).
        Reserved / sold-not-delivered / incoming quantities are only known
        live; for a past date they are None."""
        check_dashboard_access(self.env, 'stock')
        return cached(self, 'logistics.stock_cards', (subgroup, as_of),
                      lambda: self._stock_cards(subgroup, as_of), force=force)
