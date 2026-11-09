"""'Voorraadstroom': the operations of every warehouse laid out as a flow
(receipt -> putaway -> stock -> picking -> packing -> delivery, and the
returns back to stock, directly or through repair), with the live counters
of each operation type.

Everything is derived from the standard warehouse configuration (the
operation types set on the warehouse, the return type of its delivery
types, the locations of the repair type); nothing refers to a specific
warehouse, location or operation type."""
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .dashboard_access import check_dashboard_access, has_dashboard_access

# Fallback for return operation types that are not set as the return type
# of a delivery type: recognised by name or sequence code (nl / en / fr).
RETURN_PATTERN = re.compile(r'retour|return', re.IGNORECASE)

# Optional: on Odoo 19 the Inventory app opens this dashboard instead of
# its overview (Voorraad > Configuratie > Instellingen). The original action
# of the Inventory root menu is kept here to restore it.
FLOW_LANDING_PARAM = 'serviq_logistics.flow_landing'
FLOW_LANDING_BACKUP_PARAM = 'serviq_logistics.flow_landing_backup'


def _wh_type(warehouse, fname):
    """Operation type `fname` of the warehouse, or an empty recordset when
    the field does not exist (e.g. repair_type_id without Repairs)."""
    if fname in warehouse._fields:
        return warehouse[fname]
    return warehouse.env['stock.picking.type']


def _count(record, fname):
    return (record[fname] or 0) if fname in record._fields else 0


def _child_of(location, parent):
    """Is `location` the location `parent` or one of its children?"""
    return bool(location and parent and location.parent_path
                and parent.parent_path
                and location.parent_path.startswith(parent.parent_path))


class StockFlow(models.AbstractModel):
    _name = 'serviq.logistics.flow'
    _description = 'Logistiek: voorraadstroom per magazijn'

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------
    @api.model
    def get_flow_data(self):
        """One entry per warehouse the user can see, in warehouse order:
        the active warehouses and every warehouse that still has active
        operation types, archived or not (like the inventory overview).

        A user without access to this dashboard (e.g. when it is the
        landing page of the Inventory app) gets `fallback`: the standard
        inventory overview, opened instead."""
        if not has_dashboard_access(self.env, 'flow'):
            fallback = False
            if self.env.user.has_group('stock.group_stock_user'):
                fallback = self.env['ir.actions.actions']._for_xml_id(
                    'stock.stock_picking_type_action')
            return {'access': False, 'fallback': fallback, 'warehouses': []}
        types = self.env['stock.picking.type'].search([
            ('active', '=', True), ('warehouse_id', '!=', False)])
        warehouses = self.env['stock.warehouse'].with_context(active_test=False).search(
            ['|', ('active', '=', True), ('id', 'in', types.warehouse_id.ids)],
            order='sequence, id')
        return {
            'access': True,
            'fallback': False,
            'warehouses': [self._warehouse_flow(wh) for wh in warehouses],
        }

    @api.model
    def _flow_step(self, picking_type, label):
        """A card of the flow for an active operation type (else None)."""
        picking_type = picking_type.sudo()
        if not picking_type or not picking_type.active:
            return None
        if picking_type.code == 'repair_operation':
            return {
                'type_id': picking_type.id,
                'label': label,
                'name': picking_type.name,
                'kind': 'repair',
                'main': _count(picking_type, 'count_repair_ready'),
                'main_label': _('te verwerken'),
                'stats': [
                    {'label': _('In reparatie'), 'filter': 'under_repair',
                     'value': _count(picking_type, 'count_repair_under_repair')},
                    {'label': _('Te laat'), 'filter': 'late',
                     'value': _count(picking_type, 'count_repair_late')},
                ],
            }
        main_label = {
            'incoming': _('te ontvangen'),
            'outgoing': _('te leveren'),
        }.get(picking_type.code, _('te verwerken'))
        return {
            'type_id': picking_type.id,
            'label': label,
            'name': picking_type.name,
            'kind': 'picking',
            'main': _count(picking_type, 'count_picking_ready'),
            'main_label': main_label,
            'stats': [
                {'label': _('Wachten'), 'filter': 'waiting',
                 'value': _count(picking_type, 'count_picking_waiting')},
                {'label': _('Te laat'), 'filter': 'late',
                 'value': _count(picking_type, 'count_picking_late')},
                {'label': _('Backorders'), 'filter': 'backorders',
                 'value': _count(picking_type, 'count_picking_backorders')},
            ],
        }

    @api.model
    def _warehouse_flow(self, warehouse):
        """The flow of one warehouse: forward steps, stock, return steps and
        every other active operation type."""
        wh = warehouse.sudo()
        used = self.env['stock.picking.type'].sudo()

        def step(picking_type, label):
            nonlocal used
            data = self._flow_step(picking_type, label)
            if data:
                used |= picking_type
            return data

        # Forward: receipt -> putaway (storage, else internal transfers) ->
        # stock -> picking -> packing -> delivery. A step only shows when
        # the warehouse has that operation type (1/2/3-step routes).
        putaway = step(_wh_type(wh, 'store_type_id'), _('Wegzetten')) \
            or step(_wh_type(wh, 'int_type_id'), _('Interne overdrachten'))
        receipt = step(_wh_type(wh, 'in_type_id'), _('Ontvangsten'))
        inbound = [s for s in (receipt, putaway) if s]
        outbound = [s for s in (
            step(_wh_type(wh, 'pick_type_id'), _('Picking')),
            step(_wh_type(wh, 'pack_type_id'), _('Verpakken')),
            step(_wh_type(wh, 'out_type_id'), _('Leveringen')),
        ) if s]

        types = self.env['stock.picking.type'].sudo().search([
            ('warehouse_id', '=', wh.id), ('active', '=', True)])
        stock = wh.lot_stock_id

        # Returns: the return type of the warehouse's outgoing operation
        # types when it is a dedicated type (not the receipt), plus types
        # named as returns.
        outgoing = types.filtered(lambda t: t.code == 'outgoing')
        return_types = outgoing.return_picking_type_id.filtered(
            lambda t: t.active and t.warehouse_id == wh) \
            if 'return_picking_type_id' in types._fields \
            else self.env['stock.picking.type']
        return_types |= types.filtered(
            lambda t: t.code != 'repair_operation'
            and (RETURN_PATTERN.search(t.name or '')
                 or RETURN_PATTERN.search(t.sequence_code or '')))
        return_types -= used
        returns = [step(t, _('Retours')) for t in return_types]

        # Repair (Repairs app), and the internal operation that brings the
        # repaired goods back to stock: an internal type whose source is
        # where the repair type puts repaired goods, outside the stock.
        repair_type = _wh_type(wh, 'repair_type_id')
        repair = step(repair_type, _('Reparaties'))
        repair_putaway = None
        repaired_loc = repair_type.default_location_dest_id \
            if repair and 'default_location_dest_id' in repair_type._fields else False
        if repaired_loc and not _child_of(repaired_loc, stock):
            candidates = (types - used).filtered(
                lambda t: t.code == 'internal' and t.default_location_src_id
                and _child_of(t.default_location_src_id, repaired_loc))
            if candidates:
                repair_putaway = step(candidates[:1], _('Wegzetten reparaties'))

        others = [step(t, t.name) for t in types - used]

        products = 0
        if stock:
            groups = self.env['stock.quant'].sudo()._read_group(
                [('location_id', 'child_of', stock.id), ('quantity', '>', 0)],
                [], ['product_id:count_distinct'])
            products = groups[0][0] if groups else 0
        return {
            'id': wh.id,
            'name': wh.name,
            'inbound': inbound,
            'stock': {
                'location': stock.complete_name or '',
                'products': products,
            },
            'outbound': outbound,
            'returns': [r for r in returns if r],
            'repair': repair,
            'repair_putaway': repair_putaway,
            # Where a direct return is put away: the warehouse's putaway step.
            'direct_return_to': putaway['label'] if putaway else _('Voorraad'),
            'others': [o for o in others if o],
        }

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    # Domains matching the counters of the operation types
    # (stock.picking.type._compute_picking_count and repair's
    # _compute_count_repair), so a card opens the operations it counts.
    @api.model
    def _picking_domain(self, filter_name):
        open_states = ('assigned', 'waiting', 'confirmed')
        now = fields.Datetime.now()
        return {
            'ready': [('state', '=', 'assigned')],
            'waiting': [('state', 'in', ('confirmed', 'waiting'))],
            'late': [('state', 'in', open_states),
                     '|', ('scheduled_date', '<', now),
                     ('has_deadline_issue', '=', True)],
            'backorders': [('backorder_id', '!=', False),
                           ('state', 'in', open_states)],
        }.get(filter_name, [])

    @api.model
    def _repair_domain(self, filter_name):
        today = fields.Date.today()
        return {
            'ready': [('state', '=', 'confirmed'),
                      ('is_parts_available', '=', True)],
            'under_repair': [('state', '=', 'under_repair')],
            'late': [('state', '=', 'confirmed'),
                     '|', ('schedule_date', '<', today),
                     ('is_parts_late', '=', True)],
        }.get(filter_name, [])

    @api.model
    def open_flow_step(self, type_id, filter_name='ready'):
        """Action behind a card or a counter: exactly the operations it
        counts (ready by default, or the waiting / late / backorder ones),
        or all operations of the type for 'all'. The filter is part of the
        action's domain, so a default search filter cannot widen it."""
        check_dashboard_access(self.env, 'flow')
        picking_type = self.env['stock.picking.type'].browse(int(type_id)).exists()
        if not picking_type:
            raise UserError(_('Deze bewerkingssoort bestaat niet meer.'))
        labels = {
            'ready': _('te verwerken'), 'waiting': _('wachten'),
            'late': _('te laat'), 'backorders': _('backorders'),
            'under_repair': _('in reparatie'),
        }
        if picking_type.code == 'repair_operation':
            action = self.env['ir.actions.actions']._for_xml_id(
                'repair.action_repair_order_tree')
            action['domain'] = [('picking_type_id', '=', picking_type.id)] \
                + self._repair_domain(filter_name)
            action['context'] = {'default_picking_type_id': picking_type.id}
        else:
            action = picking_type.get_stock_picking_action_picking_type()
            action['domain'] = [('picking_type_id', '=', picking_type.id)] \
                + self._picking_domain(filter_name)
            # Drop the default search filters of the original action: the
            # domain above is the filter.
            context = dict(action.get('context') or {})
            for key in list(context):
                if key.startswith('search_default_'):
                    context.pop(key)
            action['context'] = context
        action['display_name'] = '%s: %s' % (
            picking_type.display_name, labels[filter_name]) \
            if filter_name in labels else picking_type.display_name
        return action

    @api.model
    def open_flow_stock(self, warehouse_id):
        """Action behind the stock card: the stock of the warehouse."""
        check_dashboard_access(self.env, 'flow')
        warehouse = self.env['stock.warehouse'].with_context(
            active_test=False).browse(int(warehouse_id)).exists()
        if not warehouse:
            raise UserError(_('Dit magazijn bestaat niet meer.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Voorraad %s', warehouse.name or ''),
            'res_model': 'stock.quant',
            'views': [(False, 'list')],
            'domain': [('location_id', 'child_of', warehouse.lot_stock_id.id),
                       ('quantity', '>', 0)],
        }

    # ------------------------------------------------------------------
    # Optional landing page of the Inventory app
    # ------------------------------------------------------------------
    @api.model
    def _apply_flow_landing(self, enable):
        """Make the Inventory app open the Voorraadstroom (enable) or put
        back the action it had before (disable). The previous action of
        the Inventory root menu is kept in a system parameter."""
        menu = self.env.ref('stock.menu_stock_root', raise_if_not_found=False)
        flow_action = self.env.ref('serviq_logistics.action_stock_flow',
                                   raise_if_not_found=False)
        if not menu or not flow_action:
            return
        menu = menu.sudo()
        icp = self.env['ir.config_parameter'].sudo()
        current = menu.action
        is_flow = bool(current) and current._name == flow_action._name \
            and current.id == flow_action.id
        if enable:
            if not is_flow:
                icp.set_param(FLOW_LANDING_BACKUP_PARAM,
                              '%s,%d' % (current._name, current.id) if current else False)
                menu.write({'action': '%s,%d' % (flow_action._name, flow_action.id)})
            return
        if not is_flow:
            return
        backup = icp.get_param(FLOW_LANDING_BACKUP_PARAM) or ''
        restore = False
        model, _sep, res_id = backup.partition(',')
        if model in self.env and res_id.isdigit() \
                and self.env[model].sudo().browse(int(res_id)).exists():
            restore = backup
        menu.write({'action': restore})
        icp.set_param(FLOW_LANDING_BACKUP_PARAM, False)
