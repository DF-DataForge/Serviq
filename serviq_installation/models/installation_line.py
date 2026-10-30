# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class InstallationLine(models.Model):
    _name = 'serviq.installation.line'
    _description = 'Installatiecomponent'
    _rec_name = 'product_tmpl_id'
    _order = 'installation_id, sequence, id'

    installation_id = fields.Many2one(
        'serviq.installation', string='Installatie', required=True,
        ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    product_tmpl_id = fields.Many2one(
        'product.template', string='Component', required=True,
        domain="[('type', '=', 'consu')]")
    product_qty = fields.Float('Hoeveelheid', default=1.0, required=True)
    product_uom = fields.Many2one(
        'uom.uom', 'Eenheid', related='product_tmpl_id.uom_id')
    product_variant_id = fields.Many2one(
        'product.product', string='Productvariant',
        related='product_tmpl_id.product_variant_id',
        help='Variant used to prefill the product when creating a new serial '
             'directly from the component line.')
    role_id = fields.Many2one(
        related='product_tmpl_id.serviq_role_id', string='Rol', store=True)
    lot_id = fields.Many2one('stock.lot', string='Lot/Serienummer', index=True)
    sub_installation_id = fields.Many2one(
        'serviq.installation', string='Subcomponenten', copy=False)
    distributor_id = fields.Many2one(
        related='installation_id.distributor_id', string='Distributeur')
    serial_photo = fields.Image(
        string='Foto serienummer', max_width=1920, max_height=1920,
        help='Photo of the serial number, captured by the installer in the '
             'portal when the serial was verified via picture.')
    serial_photo_filename = fields.Char(string='Bestandsnaam foto')
    rack_number = fields.Integer(
        string='Rack', help='Rack / group this component belongs to.')
    search_outside_stock = fields.Boolean(
        string='Zoek buiten distributeur-stock',
        help='Allow selecting and saving a serial that is not present in the '
             'distributor customer stock location. The product match and the '
             '"not already used / not on another installation" checks still '
             'apply.')
    note = fields.Char(string='Opmerking')

    @api.constrains('lot_id', 'installation_id', 'product_tmpl_id')
    def _check_lot_id(self):
        for rec in self.filtered('lot_id'):
            rec.installation_id._validate_lot_for_line(
                rec.lot_id, line=rec,
                expected_product_tmpl=rec.product_tmpl_id)

    def write(self, vals):
        res = super().write(vals)
        # The serial of a component holding a sub-installation is the
        # serial of that sub-installation.
        if 'lot_id' in vals \
                and not self.env.context.get('call_from_installation'):
            for line in self.filtered('sub_installation_id'):
                line.sub_installation_id.with_context(
                    call_from_line=True).lot_id = line.lot_id
        return res

    def action_download_serial_photo(self):
        """Return an act_url that downloads the serial-number photo."""
        self.ensure_one()
        filename = self.serial_photo_filename or (
            'serial_%s.png' % (self.lot_id.name or self.id))
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/serviq.installation.line/%d/serial_photo'
                   '?download=true&filename=%s' % (self.id, filename),
            'target': 'self',
        }

    def action_open_details(self):
        self.ensure_one()
        return {
            'name': _('Componentdetails'),
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'views': [(self.env.ref(
                'serviq_installation.installation_line_detail_form').id,
                'form')],
            'target': 'new',
            'res_id': self.id,
            'context': dict(self.env.context),
        }

    def action_open_sub_installation(self):
        self.ensure_one()
        if not self.sub_installation_id:
            raise UserError(_('Deze component heeft geen subcomponenten.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Subcomponenten'),
            'res_model': 'serviq.installation',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'res_id': self.sub_installation_id.id,
            'target': 'current',
        }
