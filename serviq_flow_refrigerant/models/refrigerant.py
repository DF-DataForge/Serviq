# -*- coding: utf-8 -*-
from odoo import api, fields, models


class Refrigerant(models.Model):
    """Refrigerant (koudemiddel) with its global warming potential. The
    GWP turns a charge in kg into tonnes CO2-equivalent, which decides on
    the logbook and leak check obligations of the F-gas regulation."""
    _name = 'serviq.refrigerant'
    _description = 'Koudemiddel'
    _order = 'sequence, name'

    name = fields.Char(required=True, help='E.g. R32, R410A.')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    gwp = fields.Float(
        string='GWP', digits=(16, 0), required=True,
        help='Global warming potential (kg CO2-eq per kg). Check the values '
             'against the annexes of the F-gas regulation in force.')
    is_fluorinated = fields.Boolean(
        string='Gefluoreerd broeikasgas', default=True,
        help='F-gases fall under the logbook and leak check obligations; '
             'natural refrigerants (R290, R744, R717, ...) do not.')
    composition = fields.Char(
        string='Samenstelling', help='Components of a blend, e.g. R32/R125.')
    note = fields.Text(string='Opmerking')

    _name_uniq = models.Constraint(
        'unique(name)', 'Dit koudemiddel bestaat al.')

    @api.model
    def _co2_eq_tonnes(self, kg, gwp):
        return round((kg or 0.0) * (gwp or 0.0) / 1000.0, 3)
