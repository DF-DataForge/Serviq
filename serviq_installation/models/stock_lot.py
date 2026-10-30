# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class StockLot(models.Model):
    _inherit = 'stock.lot'

    serviq_installation_id = fields.Many2one(
        'serviq.installation', string='Installatie', index=True, copy=False)
    serviq_sn_photo = fields.Image(
        string='Foto serienummer', max_width=1920, max_height=1920)

    @api.model
    def _serviq_distributor_lot_domain(self):
        """Extra domain restricting lots to serials that are valid for the
        distributor in context ('serviq_distributor'): not linked to an
        installation yet, in the distributor's customer stock location
        (unless 'serviq_outside_stock' is in context) and of the product
        template in context ('serviq_product_tmpl'), when given. Empty when
        no distributor is in context."""
        distributor_id = self.env.context.get('serviq_distributor')
        try:
            distributor_id = int(distributor_id or 0)
        except (TypeError, ValueError):
            distributor_id = 0
        if not distributor_id:
            return []
        domain = [('serviq_installation_id', '=', False)]
        if not self.env.context.get('serviq_outside_stock'):
            location = self.env['res.partner'].browse(
                distributor_id).property_stock_customer
            if not location:
                return [('id', 'in', [])]
            quants = self.env['stock.quant'].sudo().search([
                ('location_id', '=', location.id),
                ('quantity', '>', 0),
            ])
            domain += [('id', 'in', quants.lot_id.ids)]
        try:
            product_tmpl_id = int(
                self.env.context.get('serviq_product_tmpl') or 0)
        except (TypeError, ValueError):
            product_tmpl_id = 0
        if product_tmpl_id:
            domain += [('product_id.product_tmpl_id', '=', product_tmpl_id)]
        return domain

    @api.model
    def name_search(self, name='', domain=None, operator='ilike', limit=100):
        domain = list(domain or []) + self._serviq_distributor_lot_domain()
        return super().name_search(name, domain, operator, limit)

    @api.model_create_multi
    def create(self, vals_list):
        lots = super().create(vals_list)
        lots._serviq_place_in_distributor_stock()
        return lots

    def _serviq_place_in_distributor_stock(self):
        """When a serial is created directly from an installation component
        ('serviq_create_lot_in_stock' in context), make it available in the
        distributor's customer stock location so it passes the component
        validation."""
        if not self.env.context.get('serviq_create_lot_in_stock'):
            return
        try:
            distributor_id = int(
                self.env.context.get('serviq_distributor') or 0)
        except (TypeError, ValueError):
            return
        location = self.env['res.partner'].browse(
            distributor_id).property_stock_customer if distributor_id \
            else False
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
