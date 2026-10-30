# -*- coding: utf-8 -*-
from odoo import fields, models


class InterventionType(models.Model):
    """Type of intervention on an installation. Configurable instead of a
    fixed selection, so new kinds of interventions (and the portal flows
    handling them) can be added without code changes."""
    _name = 'serviq.intervention.type'
    _description = 'Type interventie'
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    color = fields.Integer()
    group = fields.Selection([
        ('intervention', 'Interventies'),
        ('repair', 'Herstellingen'),
        ('replacement', 'Vervangingen'),
    ], string='Groep', default='intervention', required=True,
        help='Smart button on the installation the interventions of this '
             'type are counted under.')
    counts_as_service = fields.Boolean(
        string='Telt als service', default=True,
        help='A planned intervention of this type puts an active '
             'installation in service.')
    is_first_installation = fields.Boolean(
        string='Eerste installatie',
        help='Interventions of this type create or complete the '
             'installation.')
    is_commissioning = fields.Boolean(
        string='Inbedrijfstelling',
        help='Finishing an intervention of this type makes the installation '
             'active.')

    _code_uniq = models.Constraint(
        'unique(code)', 'De code van een interventietype moet uniek zijn.')
