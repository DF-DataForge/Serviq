# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    serviq_fgas_certificate = fields.Char(
        string='F-gassencertificaat',
        help='Certificate number of the refrigeration technician (on a '
             'person) or of the certified company (on a company).')
    serviq_fgas_certificate_valid_until = fields.Date(
        string='Certificaat geldig tot')

    def _serviq_fgas_certificate_valid(self, day=None):
        """The partner has a certificate number that is not expired on
        `day` (today by default)."""
        self.ensure_one()
        day = day or fields.Date.context_today(self)
        return bool(self.serviq_fgas_certificate) and (
            not self.serviq_fgas_certificate_valid_until
            or self.serviq_fgas_certificate_valid_until >= day)
