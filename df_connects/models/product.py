# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    df_supplier_product_ids = fields.One2many(
        'df.connects.supplier.product', 'product_id',
        string='Leveranciersproducten (API)',
        groups='df_connects.group_df_connects_user')
    df_supplier_qty = fields.Float(
        string='Beschikbaar bij leveranciers',
        compute='_compute_df_supplier_qty', digits='Product Unit',
        groups='df_connects.group_df_connects_user',
        help='Quantity available at the suppliers, over all their '
             'entities, as last fetched through their connections.')

    @api.depends('df_supplier_product_ids.quantity_total')
    def _compute_df_supplier_qty(self):
        for rec in self:
            rec.df_supplier_qty = sum(
                rec.df_supplier_product_ids.mapped('quantity_total'))

    def action_view_df_supplier_products(self):
        return self.product_tmpl_id.action_view_df_supplier_products()


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    df_supplier_product_ids = fields.One2many(
        'df.connects.supplier.product', 'product_tmpl_id',
        string='Leveranciersproducten (API)',
        groups='df_connects.group_df_connects_user')
    df_supplier_qty = fields.Float(
        string='Beschikbaar bij leveranciers',
        compute='_compute_df_supplier_qty', digits='Product Unit',
        groups='df_connects.group_df_connects_user')
    df_supplier_product_count = fields.Integer(
        compute='_compute_df_supplier_qty',
        groups='df_connects.group_df_connects_user')

    @api.depends('df_supplier_product_ids.quantity_total')
    def _compute_df_supplier_qty(self):
        for rec in self:
            rec.df_supplier_qty = sum(
                rec.df_supplier_product_ids.mapped('quantity_total'))
            rec.df_supplier_product_count = len(rec.df_supplier_product_ids)

    def action_view_df_supplier_products(self):
        action = self.env['ir.actions.act_window']._for_xml_id(
            'df_connects.supplier_product_action')
        action['domain'] = [('product_tmpl_id', 'in', self.ids)]
        action['context'] = {'search_default_group_by_partner': 0}
        return action
