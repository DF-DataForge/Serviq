# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class StockLot(models.Model):
    _inherit = 'stock.lot'

    serviq_installation_id = fields.Many2one(
        'serviq.installation', string='Installatie', index=True, copy=False)
    serviq_sn_photo = fields.Image(
        string='Foto serienummer', max_width=1920, max_height=1920)

    @api.model
    def _serviq_component_lot_domain(self):
        """Extra domain restricting lots to serials that are valid on an
        installation component, used when the component fields put
        'serviq_product_tmpl' in context: not linked to an installation
        yet, of that product template and, with the serial-number
        validation (settings, see serviq.installation
        _serviq_sn_validation), in stock in a customer location
        ('customer') or in the customer location of the distributor in
        context, 'serviq_distributor' ('distributor'), unless
        'serviq_outside_stock' is in context. Empty outside the component
        fields and without validation."""
        context = self.env.context
        if 'serviq_product_tmpl' not in context:
            return []
        mode = self.env['serviq.installation']._serviq_sn_validation()
        if mode == 'none':
            return []
        domain = [('serviq_installation_id', '=', False)]
        stock_domain = None
        if mode == 'customer':
            stock_domain = [('location_id.usage', '=', 'customer')]
        elif mode == 'distributor':
            location = self._serviq_context_distributor() \
                .property_stock_customer
            if location:
                stock_domain = [('location_id', '=', location.id)]
        if stock_domain and not context.get('serviq_outside_stock'):
            quants = self.env['stock.quant'].sudo().search(
                stock_domain + [('quantity', '>', 0)])
            domain += [('id', 'in', quants.lot_id.ids)]
        try:
            product_tmpl_id = int(context.get('serviq_product_tmpl') or 0)
        except (TypeError, ValueError):
            product_tmpl_id = 0
        if product_tmpl_id:
            domain += [('product_id.product_tmpl_id', '=', product_tmpl_id)]
        return domain

    @api.model
    def _serviq_context_distributor(self):
        """Distributor in context ('serviq_distributor'), when working with
        distributors."""
        Partner = self.env['res.partner']
        try:
            distributor_id = int(
                self.env.context.get('serviq_distributor') or 0)
        except (TypeError, ValueError):
            distributor_id = 0
        if not distributor_id or not Partner._serviq_distributors_enabled():
            return Partner.browse()
        return Partner.browse(distributor_id)

    @api.model
    def name_search(self, name='', domain=None, operator='ilike', limit=100):
        domain = list(domain or []) + self._serviq_component_lot_domain()
        return super().name_search(name, domain, operator, limit)

    @api.model_create_multi
    def create(self, vals_list):
        lots = super().create(vals_list)
        lots._serviq_place_in_validated_stock()
        return lots

    def _serviq_place_in_validated_stock(self):
        """When a serial is created directly from an installation component
        ('serviq_create_lot_in_stock' in context), make it available where
        the serial-number validation looks for it, so it passes the
        component validation: the customer location (Partners/Customers)
        with validation on customer, the customer location of the
        distributor in context with validation on distributor."""
        if not self.env.context.get('serviq_create_lot_in_stock'):
            return
        mode = self.env['serviq.installation']._serviq_sn_validation()
        if mode == 'customer':
            location = self.env.ref('stock.stock_location_customers',
                                    raise_if_not_found=False)
        elif mode == 'distributor':
            location = self._serviq_context_distributor() \
                .property_stock_customer
        else:
            location = False
        if not location:
            return
        Quant = self.env['stock.quant'].sudo()
        for lot in self.filtered('product_id'):
            if Quant.search_count([('lot_id', '=', lot.id),
                                   ('location_id', '=', location.id),
                                   ('quantity', '>', 0)], limit=1):
                continue
            Quant._update_available_quantity(
                lot.product_id, location, 1.0, lot_id=lot)

    def action_view_serviq_installation(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'target': 'current',
            'name': _('Installatie'),
            'views': [[False, 'form']],
            'res_model': 'serviq.installation',
            'res_id': self.serviq_installation_id.id,
        }
