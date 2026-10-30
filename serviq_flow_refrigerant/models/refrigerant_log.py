# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta
from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

# Entry types that put refrigerant in the installation / take it out.
IN_TYPES = ('initial_charge', 'addition')
OUT_TYPES = ('recovery', 'decommissioning')
# Records must be kept this long (F-gas regulation: at least 5 years).
RETENTION_YEARS = 5


class RefrigerantLog(models.Model):
    """One line of the refrigerant logbook of an installation: a charge,
    addition or recovery of refrigerant, a leak check, a repair, a
    maintenance or a failure, with the certified technician and company
    that did it. The data is a record of what happened: it is copied at
    the time of the entry and cannot be changed or deleted afterwards
    (only corrected by a new entry)."""
    _name = 'serviq.refrigerant.log'
    _inherit = ['mail.thread']
    _description = 'Koudemiddellogboek'
    _order = 'date desc, id desc'

    installation_id = fields.Many2one(
        'serviq.installation', string='Installatie', required=True,
        ondelete='restrict', index=True)
    company_id = fields.Many2one(
        related='installation_id.company_id', store=True)
    task_id = fields.Many2one(
        'project.task', string='Interventie', ondelete='set null', index=True)
    date = fields.Date(
        string='Datum', required=True, default=fields.Date.context_today)
    entry_type = fields.Selection([
        ('initial_charge', 'Eerste vulling'),
        ('addition', 'Bijvulling'),
        ('recovery', 'Terugwinning'),
        ('leak_check', 'Lekcontrole'),
        ('repair', 'Herstelling'),
        ('maintenance', 'Onderhoud'),
        ('failure', 'Storing / alarm'),
        ('decommissioning', 'Ontmanteling'),
    ], string='Handeling', required=True)
    direction = fields.Selection([
        ('in', 'Toegevoegd'),
        ('out', 'Teruggewonnen'),
        ('none', 'Geen koudemiddel'),
    ], compute='_compute_direction', store=True, string='Richting')
    refrigerant_id = fields.Many2one(
        'serviq.refrigerant', string='Koudemiddel', required=True)
    quantity_kg = fields.Float(string='Hoeveelheid (kg)', digits=(16, 3))
    co2_eq = fields.Float(
        string='Hoeveelheid (ton CO2-eq)', digits=(16, 3),
        compute='_compute_co2_eq', store=True)
    origin = fields.Selection([
        ('new', 'Nieuw'),
        ('recycled', 'Gerecycleerd'),
        ('reclaimed', 'Geregenereerd'),
    ], string='Herkomst koudemiddel',
        help='For refrigerant added: new, recycled or reclaimed.')
    facility_name = fields.Char(string='Recyclage-/regeneratie-installatie')
    facility_address = fields.Char(string='Adres installatie')
    cylinder_id = fields.Many2one(
        'serviq.refrigerant.cylinder', string='Fles',
        help='Cylinder the refrigerant came from (added) or went into '
             '(recovered); keeps the cylinder balance.')
    leak_result = fields.Selection([
        ('no_leak', 'Geen lek vastgesteld'),
        ('leak', 'Lek vastgesteld'),
        ('leak_repaired', 'Lek vastgesteld en hersteld'),
    ], string='Resultaat lekcontrole')
    leak_location = fields.Char(string='Plaats van het lek')
    follow_up_date = fields.Date(
        string='Opvolgcontrole',
        help='Check that the repair of a leak is effective.')
    description = fields.Text(string='Omschrijving')
    technician_id = fields.Many2one(
        'res.partner', string='Technicus', ondelete='restrict')
    technician_name = fields.Char(string='Naam technicus', required=True)
    technician_certificate = fields.Char(
        string='Certificaat technicus', required=True)
    contractor_id = fields.Many2one(
        'res.partner', string='Bedrijf', ondelete='restrict')
    contractor_name = fields.Char(string='Naam bedrijf', required=True)
    contractor_certificate = fields.Char(
        string='Certificaat bedrijf', required=True)
    user_id = fields.Many2one(
        'res.users', string='Geregistreerd door', readonly=True,
        default=lambda self: self.env.user)

    @api.depends('entry_type')
    def _compute_direction(self):
        for rec in self:
            rec.direction = 'in' if rec.entry_type in IN_TYPES else \
                'out' if rec.entry_type in OUT_TYPES else 'none'

    @api.depends('quantity_kg', 'refrigerant_id.gwp')
    def _compute_co2_eq(self):
        Refrigerant = self.env['serviq.refrigerant']
        for rec in self:
            rec.co2_eq = Refrigerant._co2_eq_tonnes(
                rec.quantity_kg, rec.refrigerant_id.gwp)

    @api.onchange('installation_id')
    def _onchange_installation_id(self):
        if self.installation_id.refrigerant_id:
            self.refrigerant_id = self.installation_id.refrigerant_id

    @api.onchange('technician_id')
    def _onchange_technician_id(self):
        technician = self.technician_id
        if technician:
            self.technician_name = technician.name
            self.technician_certificate = technician.serviq_fgas_certificate
            company = technician.commercial_partner_id
            if company != technician and not self.contractor_id:
                self.contractor_id = company

    @api.onchange('contractor_id')
    def _onchange_contractor_id(self):
        if self.contractor_id:
            self.contractor_name = self.contractor_id.name
            self.contractor_certificate = \
                self.contractor_id.serviq_fgas_certificate

    @api.constrains('entry_type', 'quantity_kg', 'origin', 'facility_name',
                    'facility_address', 'leak_result', 'date')
    def _check_entry(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.date > today:
                raise ValidationError(_(
                    'Een handeling kan niet in de toekomst geregistreerd '
                    'worden.'))
            if rec.quantity_kg < 0:
                raise ValidationError(_(
                    'De hoeveelheid koudemiddel kan niet negatief zijn.'))
            if rec.direction != 'none' and not rec.quantity_kg:
                raise ValidationError(_(
                    'Geef de hoeveelheid koudemiddel op die werd '
                    '%s.', _('toegevoegd') if rec.direction == 'in'
                    else _('teruggewonnen')))
            if rec.direction == 'in' and not rec.origin:
                raise ValidationError(_(
                    'Geef de herkomst op van het toegevoegde koudemiddel '
                    '(nieuw, gerecycleerd of geregenereerd).'))
            if rec.origin in ('recycled', 'reclaimed') \
                    and not (rec.facility_name and rec.facility_address):
                raise ValidationError(_(
                    'Bij gerecycleerd of geregenereerd koudemiddel zijn de '
                    'naam en het adres van de recyclage- of '
                    'regeneratie-installatie verplicht.'))
            if rec.entry_type == 'leak_check' and not rec.leak_result:
                raise ValidationError(_(
                    'Geef het resultaat van de lekcontrole op.'))

    @api.constrains('refrigerant_id', 'installation_id', 'cylinder_id')
    def _check_refrigerant(self):
        for rec in self:
            system = rec.installation_id.refrigerant_id
            if system and rec.refrigerant_id != system:
                raise ValidationError(_(
                    'Installatie %(installation)s bevat %(system)s, geen '
                    '%(refrigerant)s.',
                    installation=rec.installation_id.display_name,
                    system=system.name, refrigerant=rec.refrigerant_id.name))
            if rec.cylinder_id \
                    and rec.cylinder_id.refrigerant_id != rec.refrigerant_id:
                raise ValidationError(_(
                    'Fles %(cylinder)s bevat %(cyl)s, geen %(refrigerant)s.',
                    cylinder=rec.cylinder_id.name,
                    cyl=rec.cylinder_id.refrigerant_id.name,
                    refrigerant=rec.refrigerant_id.name))

    def _summary(self):
        self.ensure_one()
        types = dict(self._fields['entry_type']._description_selection(
            self.env))
        parts = [types.get(self.entry_type) or '']
        if self.direction != 'none':
            parts.append('%s kg %s (%s t CO2-eq)' % (
                self.quantity_kg, self.refrigerant_id.name, self.co2_eq))
        if self.leak_result:
            parts.append(dict(self._fields['leak_result']
                              ._description_selection(self.env))
                         [self.leak_result])
        return ' - '.join(p for p in parts if p)

    @api.model_create_multi
    def create(self, vals_list):
        logs = super().create(vals_list)
        for log in logs:
            body = Markup('%s: <b>%s</b><br/>%s: %s (%s)') % (
                _('Koudemiddellogboek'), log._summary(),
                _('Technicus'), log.technician_name,
                log.technician_certificate)
            log.installation_id.message_post(body=body)
            if log.task_id:
                log.task_id.message_post(body=body)
        logs.cylinder_id._check_balance()
        return logs

    def write(self, vals):
        # The logbook is a record of what happened: only managers correct
        # it, and the change is traced in the chatter of the entry.
        technical = all(key.startswith(('message_', 'activity_'))
                        for key in vals)
        if not technical and not self.env.su and not self.env.user.has_group(
                'serviq_installation.group_installation_manager'):
            raise UserError(_(
                'Een registratie in het koudemiddellogboek kan niet '
                'gewijzigd worden. Registreer een nieuwe handeling om ze te '
                'corrigeren.'))
        cylinders = self.cylinder_id
        res = super().write(vals)
        (cylinders | self.cylinder_id)._check_balance()
        return res

    @api.ondelete(at_uninstall=False)
    def _unlink_except_retention(self):
        limit = fields.Date.context_today(self) - relativedelta(
            years=RETENTION_YEARS)
        if any(log.date > limit for log in self):
            raise UserError(_(
                'Registraties in het koudemiddellogboek moeten minstens '
                '%s jaar bewaard worden.', RETENTION_YEARS))
