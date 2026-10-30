# -*- coding: utf-8 -*-
from odoo import _, fields, models


class InstallationReplacement(models.Model):
    """History of the components swapped on an installation (one record
    per swapped serial)."""
    _name = 'serviq.installation.replacement'
    _description = 'Vervanging van een component'
    _order = 'date desc, id desc'
    _rec_name = 'product_tmpl_id'

    installation_id = fields.Many2one(
        'serviq.installation', string='Installatie', required=True,
        ondelete='cascade', index=True)
    company_id = fields.Many2one(
        related='installation_id.company_id', store=True, string='Bedrijf')
    task_id = fields.Many2one(
        'project.task', string='Interventie', ondelete='set null',
        index=True)
    line_id = fields.Many2one(
        'serviq.installation.line', string='Componentlijn',
        ondelete='set null')
    product_tmpl_id = fields.Many2one(
        'product.template', string='Component', required=True)
    old_lot_id = fields.Many2one('stock.lot', string='Oud serienummer')
    new_lot_id = fields.Many2one('stock.lot', string='Nieuw serienummer')
    date = fields.Datetime(
        string='Datum', required=True, default=fields.Datetime.now)
    user_id = fields.Many2one(
        'res.users', string='Gebruiker', required=True,
        default=lambda self: self.env.user)
    note = fields.Char(string='Opmerking')

    def _summary(self):
        """'<component>: <old> -> <new>' for the chatter."""
        self.ensure_one()
        return _('%(component)s: %(old)s → %(new)s',
                 component=self.product_tmpl_id.display_name,
                 old=self.old_lot_id.name or '-',
                 new=self.new_lot_id.name or '-')
