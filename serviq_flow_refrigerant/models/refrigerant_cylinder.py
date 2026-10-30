# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Cylinder moves that bring refrigerant in / take it out of the cylinder.
MOVE_IN = ('purchase', 'transfer_in')
MOVE_OUT = ('return', 'destruction', 'transfer_out')


class RefrigerantCylinder(models.Model):
    """Refrigerant cylinder of a refrigeration company. Its balance
    (flesbalans) follows from its moves (purchase, return, hand-in for
    destruction or recycling, transfers) and from the logbook entries that
    charged an installation from it or recovered refrigerant into it, so
    every kg bought or taken back can be traced."""
    _name = 'serviq.refrigerant.cylinder'
    _inherit = ['mail.thread']
    _description = 'Koudemiddelfles'
    _order = 'name'

    name = fields.Char(string='Flesnummer', required=True, tracking=True)
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company, required=True)
    owner_id = fields.Many2one(
        'res.partner', string='Bedrijf', required=True, tracking=True,
        default=lambda self: self.env.company.partner_id,
        help='Refrigeration company keeping this cylinder.')
    refrigerant_id = fields.Many2one(
        'serviq.refrigerant', string='Koudemiddel', required=True,
        tracking=True)
    kind = fields.Selection([
        ('new', 'Nieuw koudemiddel'),
        ('recovery', 'Recuperatie'),
    ], string='Soort', required=True, default='new', tracking=True)
    capacity_kg = fields.Float(string='Capaciteit (kg)', digits=(16, 3))
    supplier_id = fields.Many2one('res.partner', string='Leverancier')
    active = fields.Boolean(default=True)
    move_ids = fields.One2many(
        'serviq.refrigerant.cylinder.move', 'cylinder_id',
        string='Bewegingen')
    log_ids = fields.One2many(
        'serviq.refrigerant.log', 'cylinder_id',
        string='Handelingen op installaties')
    balance_kg = fields.Float(
        string='Inhoud (kg)', digits=(16, 3), compute='_compute_balance',
        store=True)

    _name_uniq = models.Constraint(
        'unique(name, owner_id)', 'Dit flesnummer bestaat al voor dit bedrijf.')

    @api.depends('move_ids.quantity_kg', 'move_ids.move_type',
                 'log_ids.quantity_kg', 'log_ids.direction')
    def _compute_balance(self):
        for rec in self:
            balance = 0.0
            for move in rec.move_ids:
                balance += move.quantity_kg if move.move_type in MOVE_IN \
                    else -move.quantity_kg
            for log in rec.log_ids:
                # Charged into an installation: out of the cylinder;
                # recovered from an installation: into it.
                if log.direction == 'in':
                    balance -= log.quantity_kg
                elif log.direction == 'out':
                    balance += log.quantity_kg
            rec.balance_kg = round(balance, 3)

    def _check_balance(self):
        for rec in self:
            if rec.balance_kg < -0.0005:
                raise ValidationError(_(
                    'Fles %(cylinder)s zou op %(balance)s kg komen: er kan '
                    'niet meer koudemiddel uit dan erin zit.',
                    cylinder=rec.name, balance=rec.balance_kg))
            if rec.capacity_kg and rec.balance_kg > rec.capacity_kg + 0.0005:
                raise ValidationError(_(
                    'Fles %(cylinder)s zou op %(balance)s kg komen, meer dan '
                    'haar capaciteit van %(capacity)s kg.',
                    cylinder=rec.name, balance=rec.balance_kg,
                    capacity=rec.capacity_kg))


class RefrigerantCylinderMove(models.Model):
    _name = 'serviq.refrigerant.cylinder.move'
    _description = 'Beweging koudemiddelfles'
    _order = 'date desc, id desc'

    cylinder_id = fields.Many2one(
        'serviq.refrigerant.cylinder', string='Fles', required=True,
        ondelete='restrict', index=True)
    company_id = fields.Many2one(related='cylinder_id.company_id', store=True)
    refrigerant_id = fields.Many2one(
        related='cylinder_id.refrigerant_id', store=True)
    date = fields.Date(
        string='Datum', required=True, default=fields.Date.context_today)
    move_type = fields.Selection([
        ('purchase', 'Aankoop / ontvangst'),
        ('transfer_in', 'Overgepompt naar deze fles'),
        ('transfer_out', 'Overgepompt uit deze fles'),
        ('return', 'Retour leverancier'),
        ('destruction', 'Afgifte voor vernietiging / recyclage'),
    ], string='Beweging', required=True)
    quantity_kg = fields.Float(
        string='Hoeveelheid (kg)', digits=(16, 3), required=True)
    partner_id = fields.Many2one(
        'res.partner', string='Leverancier / afnemer')
    reference = fields.Char(string='Referentie',
                            help='Invoice, delivery note, waste slip, ...')
    note = fields.Char(string='Opmerking')

    @api.constrains('quantity_kg')
    def _check_quantity(self):
        if any(move.quantity_kg <= 0 for move in self):
            raise ValidationError(_(
                'De hoeveelheid van een beweging moet positief zijn.'))

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        moves.cylinder_id._check_balance()
        return moves

    def write(self, vals):
        cylinders = self.cylinder_id
        res = super().write(vals)
        (cylinders | self.cylinder_id)._check_balance()
        return res
