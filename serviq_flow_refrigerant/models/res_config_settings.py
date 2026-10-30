# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    serviq_fgas_lead_days = fields.Integer(
        string='Dagen vooraf lekcontrole',
        config_parameter='serviq_flow_refrigerant.leak_check_lead_days',
        default=30,
        help='A leak check intervention is planned this many days before '
             'the next mandatory leak check.')
