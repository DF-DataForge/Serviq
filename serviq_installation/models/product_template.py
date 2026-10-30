# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    serviq_category_id = fields.Many2one(
        'serviq.installation.category', string='Installatiecategorie',
        help='Segment of the product; installations of this product get '
             'this category.')
    serviq_role_id = fields.Many2one(
        'serviq.component.role', string='Componentrol',
        help='Role of the product inside an installation.')
    serviq_category_code = fields.Char(
        related='serviq_category_id.code', store=True,
        string='Code installatiecategorie')
    serviq_role_code = fields.Char(
        related='serviq_role_id.code', store=True, string='Code componentrol')
    serviq_is_installation_product = fields.Boolean(
        related='serviq_role_id.is_installation_product',
        string='Is installatieproduct')
