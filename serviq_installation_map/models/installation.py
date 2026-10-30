# -*- coding: utf-8 -*-
from odoo import _, api, fields, models

# OpenStreetMap tiles by default; another tile server (with its own
# attribution, e.g. a paid provider with an API key) can be set in the
# settings.
DEFAULT_TILE_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
DEFAULT_ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">' \
                      'OpenStreetMap</a> contributors'


class Installation(models.Model):
    _inherit = 'serviq.installation'

    site_partner_id = fields.Many2one(
        'res.partner', string='Locatie', tracking=True,
        compute='_compute_site_partner_id', store=True, readonly=False,
        help='Address where the installation is placed: the customer by '
             'default, or another address (site, delivery address) of the '
             'customer.')
    site_city = fields.Char(related='site_partner_id.city', string='Gemeente')
    latitude = fields.Float(
        string='Breedtegraad', digits=(10, 7),
        compute='_compute_coordinates', store=True, readonly=False)
    longitude = fields.Float(
        string='Lengtegraad', digits=(10, 7),
        compute='_compute_coordinates', store=True, readonly=False)
    has_location = fields.Boolean(
        string='Heeft locatie', compute='_compute_has_location', store=True)

    @api.depends('customer_id')
    def _compute_site_partner_id(self):
        for rec in self:
            if not rec.site_partner_id or rec.site_partner_id \
                    .commercial_partner_id != rec.customer_id \
                    .commercial_partner_id:
                rec.site_partner_id = rec.customer_id

    @api.depends('site_partner_id.partner_latitude',
                 'site_partner_id.partner_longitude')
    def _compute_coordinates(self):
        # The address of the location gives the coordinates; a position
        # set by hand on the map stays until the location changes.
        for rec in self:
            partner = rec.site_partner_id
            if partner.partner_latitude or partner.partner_longitude:
                rec.latitude = partner.partner_latitude
                rec.longitude = partner.partner_longitude
            elif not partner:
                rec.latitude = rec.longitude = 0.0

    @api.depends('latitude', 'longitude')
    def _compute_has_location(self):
        for rec in self:
            rec.has_location = bool(rec.latitude or rec.longitude)

    def action_geolocalize(self):
        """Look up the coordinates of the address of the location (base
        geolocalize: OpenStreetMap by default) and put the installations
        on the map."""
        partners = self.site_partner_id
        partners.with_context(force_geo_localize=True).geo_localize()
        found = self.filtered(
            lambda r: r.site_partner_id.partner_latitude
            or r.site_partner_id.partner_longitude)
        for rec in found:
            rec.write({'latitude': rec.site_partner_id.partner_latitude,
                       'longitude': rec.site_partner_id.partner_longitude})
        missing = self - found
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'warning' if missing else 'success',
                'title': _('Geolocalisatie'),
                'message': _(
                    '%(found)s installatie(s) op de kaart gezet, %(missing)s '
                    'adres(sen) niet gevonden.',
                    found=len(found), missing=len(missing))
                if missing else _('%s installatie(s) op de kaart gezet.',
                                  len(found)),
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }

    # ------------------------------------------------------------------
    # Map data
    # ------------------------------------------------------------------
    @api.model
    def get_map_tile_config(self):
        params = self.env['ir.config_parameter'].sudo()
        return {
            'url': params.get_param('serviq_installation_map.tile_url')
            or DEFAULT_TILE_URL,
            'attribution': params.get_param(
                'serviq_installation_map.tile_attribution')
            or DEFAULT_ATTRIBUTION,
            'maxZoom': 19,
        }

    @api.model
    def get_map_overview_data(self, domain=None):
        """Top-level installations with a location for the map (narrowed
        by `domain`): their status and base information, plus how many
        have no location yet."""
        states = dict(self._fields['state']._description_selection(self.env))
        domain = [('parent_line_id', '=', False)] + list(domain or [])
        installations = self.search(domain)
        located = installations.filtered('has_location')
        return {
            'installations': [{
                'id': rec.id,
                'code': rec.code or '',
                'product': rec.product_tmpl_id.name or rec.name or '',
                'category': rec.category_id.name or '',
                'customer': rec.customer_id.name or '',
                'location': rec.site_city or '',
                'latitude': rec.latitude,
                'longitude': rec.longitude,
                'state': rec.state or '',
                'stateLabel': states.get(rec.state, ''),
                'distributor': rec.distributor_id.name or '',
                'installer': rec.installer_id.name or '',
            } for rec in located],
            'missing': len(installations) - len(located),
            'missing_ids': (installations - located).ids,
            'states': [[key, label] for key, label in states.items()],
            'tiles': self.get_map_tile_config(),
        }
