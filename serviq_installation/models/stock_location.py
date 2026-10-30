# -*- coding: utf-8 -*-
from odoo import fields, models


class StockLocation(models.Model):
    _inherit = 'stock.location'

    serviq_partner_id = fields.Many2one(
        'res.partner', string='Partner', index=True,
        help='Partner this customer-specific location belongs to.')
    serviq_is_spare_parts_location = fields.Boolean(
        string='Locatie reserveonderdelen',
        help='Identifies this location as a spare parts storage location.')
