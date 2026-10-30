# -*- coding: utf-8 -*-
from odoo import fields, models


class ComponentRole(models.Model):
    """Role of a product inside an installation (battery, inverter, pump,
    ...). Replaces the hardcoded product types: the roles, their order and
    labels are data."""
    _name = 'serviq.component.role'
    _description = 'Componentrol'
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    is_installation_product = fields.Boolean(
        string='Installatieproduct',
        help='Products with this role are complete installations (the '
             'product of an installation); their components follow from the '
             'bill of materials.')
    is_spare_part = fields.Boolean(string='Reserveonderdeel')
    is_replaceable = fields.Boolean(
        string='Vervangbaar',
        help='Components with this role can be swapped in a replacement '
             'intervention.')

    _code_uniq = models.Constraint(
        'unique(code)', 'De code van een componentrol moet uniek zijn.')
