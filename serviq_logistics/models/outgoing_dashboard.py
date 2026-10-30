from odoo import models, api

from .labels import product_types, segment_domain, state_label
from .dashboard_access import check_dashboard_access


PICKING_TYPE_LABELS = {
    'incoming': 'Ontvangst',
    'outgoing': 'Levering',
    'internal': 'Pick',
}


class OutgoingGoodsDashboard(models.AbstractModel):
    _name = 'serviq.logistics.outgoing'
    _description = 'Logistiek: uitgaande goederen'

    @api.model
    def get_outgoing_data(self, search_term=None, subgroup=None):
        """Return SOs grouped by customer with delivery status and picking details.

        Includes the full transfer chain (internal Pick/Pack steps and final
        outgoing Delivery) so multi-step routes are fully visible.
        """
        check_dashboard_access(self.env, 'outgoing')
        SO = self.env['sale.order'].sudo()

        domain = [('state', 'in', ['sale', 'done'])]
        domain += segment_domain(subgroup, 'order_line.product_id.product_tmpl_id')
        if search_term:
            domain += [
                '|', '|',
                ('name', 'ilike', search_term),
                ('partner_id.name', 'ilike', search_term),
                ('client_order_ref', 'ilike', search_term),
            ]

        orders = SO.search(domain, order='partner_id, date_order desc')

        # Group by commercial partner (company, not subcontact)
        customer_map = {}
        for so in orders:
            partner = so.partner_id.commercial_partner_id
            pid = partner.id
            if pid not in customer_map:
                customer_map[pid] = {
                    'partner_id': pid,
                    'partner_name': partner.display_name,
                    'sale_orders': [],
                    'total_orders': 0,
                    'fully_delivered': 0,
                    'partially_delivered': 0,
                    'waiting': 0,
                }
            entry = customer_map[pid]
            entry['total_orders'] += 1

            # Delivery status is based on the final outgoing transfers only.
            outgoing_pickings = so.picking_ids.filtered(
                lambda p: p.picking_type_code == 'outgoing'
            )
            total_outgoing = len(outgoing_pickings)
            done_outgoing = len(outgoing_pickings.filtered(lambda p: p.state == 'done'))

            if total_outgoing == 0:
                delivery_status = 'waiting'
                entry['waiting'] += 1
            elif done_outgoing == total_outgoing:
                delivery_status = 'fully_delivered'
                entry['fully_delivered'] += 1
            elif done_outgoing > 0:
                delivery_status = 'partially_delivered'
                entry['partially_delivered'] += 1
            else:
                delivery_status = 'waiting'
                entry['waiting'] += 1

            # All transfers tied to this SO (Pick / Pack / Ship).
            all_pickings = so.picking_ids.filtered(
                lambda p: p.picking_type_code in ('internal', 'outgoing')
            )
            internal_pickings = all_pickings.filtered(
                lambda p: p.picking_type_code == 'internal'
            )
            done_internal = len(internal_pickings.filtered(lambda p: p.state == 'done'))

            entry['sale_orders'].append({
                'so_id': so.id,
                'so_name': so.name,
                'date_order': so.date_order.strftime('%Y-%m-%d') if so.date_order else '',
                'client_order_ref': so.client_order_ref or '',
                'amount_total': so.amount_total,
                'currency': so.currency_id.symbol or '',
                'state': so.state,
                'delivery_status': delivery_status,
                'picking_count': total_outgoing,
                'done_picking_count': done_outgoing,
                'pick_count': len(internal_pickings),
                'done_pick_count': done_internal,
                'product_types': product_types(so.order_line),
                'pickings': [],
            })

        # Fetch picking details for each SO (internal + outgoing).
        for customer in customer_map.values():
            for so_data in customer['sale_orders']:
                so = SO.browse(so_data['so_id'])
                pickings = so.picking_ids.filtered(
                    lambda p: p.picking_type_code in ('internal', 'outgoing')
                )
                # Sort: internal Pick steps first, then outgoing Ship; within each
                # group order by scheduled date so the chain reads top-to-bottom.
                ordered = pickings.sorted(
                    key=lambda p: (
                        0 if p.picking_type_code == 'internal' else 1,
                        p.scheduled_date or False,
                    )
                )
                for pick in ordered:
                    # Get attached documents
                    attachments = self.env['ir.attachment'].sudo().search([
                        ('res_model', '=', 'stock.picking'),
                        ('res_id', '=', pick.id),
                    ])

                    # Get stock moves
                    moves = []
                    for move in pick.move_ids:
                        moves.append({
                            'product_name': move.product_id.display_name,
                            'product_uom_qty': move.product_uom_qty,
                            'quantity': move.quantity,
                            'uom': move.product_uom.name,
                            'state': move.state,
                        })

                    picking_type_code = pick.picking_type_code
                    type_label = pick.picking_type_id.name or PICKING_TYPE_LABELS.get(
                        picking_type_code, picking_type_code or ''
                    )
                    kind = 'pick' if picking_type_code == 'internal' else 'delivery'

                    so_data['pickings'].append({
                        'picking_id': pick.id,
                        'picking_name': pick.name,
                        'picking_type_code': picking_type_code or '',
                        'picking_type_label': type_label,
                        'kind': kind,
                        'scheduled_date': pick.scheduled_date.strftime('%Y-%m-%d') if pick.scheduled_date else '',
                        'date_done': pick.date_done.strftime('%Y-%m-%d') if pick.date_done else '',
                        'state': pick.state,
                        'state_label': state_label(pick),
                        'origin': pick.origin or '',
                        'carrier_tracking_ref': pick.carrier_tracking_ref or '',
                        'moves': moves,
                        'documents': [{
                            'id': att.id,
                            'name': att.name,
                            'mimetype': att.mimetype or '',
                        } for att in attachments],
                    })

        result = sorted(customer_map.values(), key=lambda x: x['partner_name'])
        return result

    @api.model
    def get_outgoing_summary(self, subgroup=None):
        """Return summary stats for outgoing goods (deliveries + internal picks)."""
        check_dashboard_access(self.env, 'outgoing')
        SO = self.env['sale.order'].sudo()
        domain = [('state', 'in', ['sale', 'done'])]
        domain += segment_domain(subgroup, 'order_line.product_id.product_tmpl_id')
        orders = SO.search(domain)

        total = len(orders)
        fully_delivered = 0
        partially_delivered = 0
        waiting = 0
        total_picks = 0
        done_picks = 0

        for so in orders:
            pickings = so.picking_ids.filtered(
                lambda p: p.picking_type_code == 'outgoing'
            )
            done = len(pickings.filtered(lambda p: p.state == 'done'))
            if len(pickings) == 0 or done == 0:
                waiting += 1
            elif done == len(pickings):
                fully_delivered += 1
            else:
                partially_delivered += 1

            internal = so.picking_ids.filtered(
                lambda p: p.picking_type_code == 'internal'
            )
            total_picks += len(internal)
            done_picks += len(internal.filtered(lambda p: p.state == 'done'))

        return {
            'total_orders': total,
            'fully_delivered': fully_delivered,
            'partially_delivered': partially_delivered,
            'waiting': waiting,
            'customer_count': len(set(orders.mapped('partner_id.commercial_partner_id.id'))),
            'total_picks': total_picks,
            'done_picks': done_picks,
            'open_picks': total_picks - done_picks,
        }
