# -*- coding: utf-8 -*-
from odoo import fields, models


class Installation(models.Model):
    _inherit = 'serviq.installation'

    replacement_ids = fields.One2many(
        'serviq.installation.replacement', 'installation_id',
        string='Vervangingen')
