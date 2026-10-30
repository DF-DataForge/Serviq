# -*- coding: utf-8 -*-
from odoo import fields, models


class InstallationCategory(models.Model):
    _inherit = 'serviq.installation.category'

    has_refrigerant = fields.Boolean(
        string='Koeltechnisch systeem',
        help='Installations of this category hold a refrigerant (cooling, '
             'heat pump, air conditioning): the refrigerant registration '
             'flow and the F-gas logbook apply to them.')
