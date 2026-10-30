# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    serviq_map_tile_url = fields.Char(
        string='Kaarttegels (URL)',
        config_parameter='serviq_installation_map.tile_url',
        help='Tile server of the maps, e.g. '
             'https://tile.openstreetmap.org/{z}/{x}/{y}.png (default). '
             'Use a provider of your own (with its API key) for heavy use.')
    serviq_map_tile_attribution = fields.Char(
        string='Bronvermelding kaart',
        config_parameter='serviq_installation_map.tile_attribution',
        help='Attribution required by the tile provider (HTML).')
