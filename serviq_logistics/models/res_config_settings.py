from odoo import api, fields, models

SPARE_SUPPLIER_PARAM = 'serviq_logistics.spare_supplier_ids'


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Optional supplier filter of the Reserveonderdelen dashboard, kept in
    # the system parameter serviq_logistics.spare_supplier_ids (comma
    # separated partner ids; empty = every spare part).
    serviq_spare_supplier_ids = fields.Many2many(
        'res.partner', 'serviq_logistics_settings_spare_supplier_rel',
        'config_id', 'partner_id', string='Leveranciers reserveonderdelen',
        help='Beperk het dashboard Reserveonderdelen tot de reserveonderdelen van deze '
             'leveranciers: voorraad in hun eigendom (consignatie) of producten die zij '
             'leveren. Leeg = alle producten met een rol "Reserveonderdeel".')

    @api.model
    def get_values(self):
        res = super().get_values()
        value = self.env['ir.config_parameter'].sudo().get_param(SPARE_SUPPLIER_PARAM) or ''
        ids = [int(x) for x in value.replace(';', ',').split(',') if x.strip().isdigit()]
        partners = self.env['res.partner'].sudo().browse(ids).exists()
        res['serviq_spare_supplier_ids'] = [(6, 0, partners.ids)]
        return res

    def set_values(self):
        super().set_values()
        self.env['ir.config_parameter'].sudo().set_param(
            SPARE_SUPPLIER_PARAM,
            ','.join(str(i) for i in self.serviq_spare_supplier_ids.ids) or False)
