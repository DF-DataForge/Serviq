from odoo import models, api

from .labels import product_types, segment_domain, state_label
from .dashboard_access import check_dashboard_access


class IncomingGoodsDashboard(models.AbstractModel):
    _name = 'serviq.logistics.incoming'
    _description = 'Logistiek: inkomende goederen'

    @api.model
    def get_incoming_data(self, search_term=None, subgroup=None):
        """Return POs grouped by supplier with reception status and picking details."""
        check_dashboard_access(self.env, 'incoming')
        PO = self.env['purchase.order'].sudo()

        domain = [('state', 'in', ['purchase', 'done'])]
        domain += segment_domain(subgroup, 'order_line.product_id.product_tmpl_id')
        if search_term:
            domain += [
                '|', '|',
                ('name', 'ilike', search_term),
                ('partner_id.name', 'ilike', search_term),
                ('origin', 'ilike', search_term),
            ]

        orders = PO.search(domain, order='partner_id, date_order desc')

        # Group by commercial partner (company, not subcontact)
        supplier_map = {}
        for po in orders:
            partner = po.partner_id.commercial_partner_id
            pid = partner.id
            if pid not in supplier_map:
                supplier_map[pid] = {
                    'partner_id': pid,
                    'partner_name': partner.display_name,
                    'purchase_orders': [],
                    'total_orders': 0,
                    'fully_received': 0,
                    'partially_received': 0,
                    'waiting': 0,
                }
            entry = supplier_map[pid]
            entry['total_orders'] += 1

            # Determine reception status
            pickings = po.picking_ids.filtered(
                lambda p: p.picking_type_code == 'incoming'
            )
            total_pickings = len(pickings)
            done_pickings = len(pickings.filtered(lambda p: p.state == 'done'))

            if total_pickings == 0:
                reception_status = 'waiting'
                entry['waiting'] += 1
            elif done_pickings == total_pickings:
                reception_status = 'fully_received'
                entry['fully_received'] += 1
            elif done_pickings > 0:
                reception_status = 'partially_received'
                entry['partially_received'] += 1
            else:
                reception_status = 'waiting'
                entry['waiting'] += 1

            entry['purchase_orders'].append({
                'po_id': po.id,
                'po_name': po.name,
                'date_order': po.date_order.strftime('%Y-%m-%d') if po.date_order else '',
                'date_planned': po.date_planned.strftime('%Y-%m-%d') if po.date_planned else '',
                'origin': po.origin or '',
                'amount_total': po.amount_total,
                'currency': po.currency_id.symbol or '',
                'state': po.state,
                'reception_status': reception_status,
                'picking_count': total_pickings,
                'done_picking_count': done_pickings,
                'product_types': product_types(po.order_line),
                'pickings': [],
            })

        # Now fetch picking details for each PO
        for supplier in supplier_map.values():
            for po_data in supplier['purchase_orders']:
                po = PO.browse(po_data['po_id'])
                pickings = po.picking_ids.filtered(
                    lambda p: p.picking_type_code == 'incoming'
                )
                for pick in pickings.sorted('scheduled_date'):
                    # Get attached documents
                    attachments = self.env['ir.attachment'].sudo().search([
                        ('res_model', '=', 'stock.picking'),
                        ('res_id', '=', pick.id),
                    ])

                    po_data['pickings'].append({
                        'picking_id': pick.id,
                        'picking_name': pick.name,
                        'scheduled_date': pick.scheduled_date.strftime('%Y-%m-%d') if pick.scheduled_date else '',
                        'date_done': pick.date_done.strftime('%Y-%m-%d') if pick.date_done else '',
                        'state': pick.state,
                        'state_label': state_label(pick),
                        'origin': pick.origin or '',
                        'carrier_tracking_ref': pick.carrier_tracking_ref or '',
                        'move_count': len(pick.move_ids),
                        'documents': [{
                            'id': att.id,
                            'name': att.name,
                            'mimetype': att.mimetype or '',
                        } for att in attachments],
                    })

        result = sorted(supplier_map.values(), key=lambda x: x['partner_name'])
        return result

    @api.model
    def get_incoming_summary(self, subgroup=None):
        """Return summary stats for incoming goods."""
        check_dashboard_access(self.env, 'incoming')
        PO = self.env['purchase.order'].sudo()
        domain = [('state', 'in', ['purchase', 'done'])]
        domain += segment_domain(subgroup, 'order_line.product_id.product_tmpl_id')
        orders = PO.search(domain)

        total = len(orders)
        fully_received = 0
        partially_received = 0
        waiting = 0

        for po in orders:
            pickings = po.picking_ids.filtered(
                lambda p: p.picking_type_code == 'incoming'
            )
            done = len(pickings.filtered(lambda p: p.state == 'done'))
            if len(pickings) == 0 or done == 0:
                waiting += 1
            elif done == len(pickings):
                fully_received += 1
            else:
                partially_received += 1

        return {
            'total_orders': total,
            'fully_received': fully_received,
            'partially_received': partially_received,
            'waiting': waiting,
            'supplier_count': len(set(orders.mapped('partner_id.commercial_partner_id.id'))),
        }
