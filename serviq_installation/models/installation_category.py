# -*- coding: utf-8 -*-
from odoo import fields, models


class InstallationCategory(models.Model):
    """Kind of installation (e.g. residential / industrial). Replaces the
    hardcoded battery types: what a category does in the flows is set
    here instead of in code."""
    _name = 'serviq.installation.category'
    _description = 'Installatiecategorie'
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(
        required=True,
        help='Technical key, used by the dashboards and the portal flows.')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    color = fields.Integer()
    requires_commissioning = fields.Boolean(
        string='Inbedrijfstelling vereist',
        help='Installations of this category go through a commissioning '
             'before they are active. Without it the status "Inbedrijfstelling '
             'gepland" does not apply.')
    active_after_first_installation = fields.Boolean(
        string='Actief na eerste installatie',
        help='An installation of this category created by a first '
             'installation is active right away.')
    auto_create_on_delivery = fields.Boolean(
        string='Aanmaken bij levering',
        help='Create an installation when a delivery of installation '
             'products of this category is validated.')
    wrapper_product_tmpl_id = fields.Many2one(
        'product.template', string='Installatieproduct',
        domain="[('type', '=', 'consu')]",
        help='Product of an installation created from a delivery; the '
             'delivered units become its components.')
    delivery_intervention_type_id = fields.Many2one(
        'serviq.intervention.type', string='Interventie na levering',
        help='Intervention planned for an installation created from a '
             'delivery (e.g. commissioning).')

    _code_uniq = models.Constraint(
        'unique(code)', 'De code van een installatiecategorie moet uniek zijn.')
