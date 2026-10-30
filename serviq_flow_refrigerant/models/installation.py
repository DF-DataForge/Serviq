# -*- coding: utf-8 -*-
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models

# Thresholds of the F-gas regulation, in tonnes CO2-equivalent.
LOGBOOK_THRESHOLD = 5.0
HERMETIC_THRESHOLD = 10.0
# (lower bound in t CO2-eq, months between leak checks, months with a
# fixed leak detection system), from the highest bound down.
LEAK_CHECK_INTERVALS = (
    (500.0, 3, 6),
    (50.0, 6, 12),
    (LOGBOOK_THRESHOLD, 12, 24),
)
DETECTION_MANDATORY_THRESHOLD = 500.0


class Installation(models.Model):
    _inherit = 'serviq.installation'

    has_refrigerant = fields.Boolean(
        string='Koeltechnisch systeem', compute='_compute_has_refrigerant',
        store=True)
    refrigerant_id = fields.Many2one(
        'serviq.refrigerant', string='Koudemiddel', tracking=True)
    refrigerant_charge_kg = fields.Float(
        string='Nominale inhoud (kg)', digits=(16, 3), tracking=True,
        help='Nominal refrigerant charge of the installation.')
    refrigerant_gwp = fields.Float(
        related='refrigerant_id.gwp', string='GWP')
    refrigerant_co2_eq = fields.Float(
        string='Inhoud (ton CO2-eq)', digits=(16, 3),
        compute='_compute_refrigerant_obligations', store=True)
    refrigerant_hermetic = fields.Boolean(
        string='Hermetisch gesloten', tracking=True,
        help='Hermetically sealed systems only need a logbook and leak '
             'checks from 10 t CO2-eq (when labelled as such).')
    refrigerant_leak_detection = fields.Boolean(
        string='Vast lekdetectiesysteem', tracking=True,
        help='A fixed leak detection system halves the frequency of the '
             'leak checks; it is mandatory from 500 t CO2-eq.')
    refrigerant_commissioning_date = fields.Date(
        string='Datum ingebruikname', tracking=True)
    fgas_logbook_required = fields.Boolean(
        string='Logboekplichtig', compute='_compute_refrigerant_obligations',
        store=True)
    fgas_leak_check_months = fields.Integer(
        string='Lekcontrole elke (maanden)',
        compute='_compute_refrigerant_obligations', store=True)
    fgas_detection_missing = fields.Boolean(
        string='Lekdetectie verplicht maar ontbreekt',
        compute='_compute_refrigerant_obligations', store=True)
    refrigerant_log_ids = fields.One2many(
        'serviq.refrigerant.log', 'installation_id',
        string='Koudemiddellogboek')
    refrigerant_log_count = fields.Integer(
        compute='_compute_refrigerant_log_stats')
    refrigerant_added_kg = fields.Float(
        string='Totaal bijgevuld (kg)', digits=(16, 3),
        compute='_compute_refrigerant_log_stats')
    refrigerant_recovered_kg = fields.Float(
        string='Totaal teruggewonnen (kg)', digits=(16, 3),
        compute='_compute_refrigerant_log_stats')
    fgas_last_leak_check = fields.Date(
        string='Laatste lekcontrole', compute='_compute_fgas_leak_check',
        store=True)
    fgas_next_leak_check = fields.Date(
        string='Volgende lekcontrole', compute='_compute_fgas_leak_check',
        store=True)
    fgas_check_state = fields.Selection([
        ('not_required', 'Niet verplicht'),
        ('ok', 'In orde'),
        ('due', 'Binnenkort'),
        ('overdue', 'Te laat'),
        ('unknown', 'Gegevens onvolledig'),
    ], string='Lekcontrole', compute='_compute_fgas_check_state')

    @api.depends('category_id.has_refrigerant', 'refrigerant_id')
    def _compute_has_refrigerant(self):
        for rec in self:
            rec.has_refrigerant = bool(
                rec.category_id.has_refrigerant or rec.refrigerant_id)

    @api.depends('refrigerant_id.gwp', 'refrigerant_id.is_fluorinated',
                 'refrigerant_charge_kg', 'refrigerant_hermetic',
                 'refrigerant_leak_detection')
    def _compute_refrigerant_obligations(self):
        Refrigerant = self.env['serviq.refrigerant']
        for rec in self:
            co2 = Refrigerant._co2_eq_tonnes(
                rec.refrigerant_charge_kg, rec.refrigerant_id.gwp)
            rec.refrigerant_co2_eq = co2
            threshold = HERMETIC_THRESHOLD if rec.refrigerant_hermetic \
                else LOGBOOK_THRESHOLD
            required = rec.refrigerant_id.is_fluorinated and co2 >= threshold
            rec.fgas_logbook_required = required
            months = 0
            if required:
                for bound, plain, detected in LEAK_CHECK_INTERVALS:
                    if co2 >= bound:
                        months = detected if rec.refrigerant_leak_detection \
                            else plain
                        break
            rec.fgas_leak_check_months = months
            rec.fgas_detection_missing = bool(
                required and co2 >= DETECTION_MANDATORY_THRESHOLD
                and not rec.refrigerant_leak_detection)

    @api.depends('refrigerant_log_ids.quantity_kg',
                 'refrigerant_log_ids.direction')
    def _compute_refrigerant_log_stats(self):
        for rec in self:
            logs = rec.refrigerant_log_ids
            rec.refrigerant_log_count = len(logs)
            rec.refrigerant_added_kg = sum(
                logs.filtered(lambda l: l.direction == 'in')
                .mapped('quantity_kg'))
            rec.refrigerant_recovered_kg = sum(
                logs.filtered(lambda l: l.direction == 'out')
                .mapped('quantity_kg'))

    @api.depends('refrigerant_log_ids.date', 'refrigerant_log_ids.entry_type',
                 'refrigerant_commissioning_date', 'fgas_leak_check_months')
    def _compute_fgas_leak_check(self):
        for rec in self:
            checks = rec.refrigerant_log_ids.filtered(
                lambda l: l.entry_type == 'leak_check')
            last = max(checks.mapped('date')) if checks else False
            rec.fgas_last_leak_check = last
            start = last or rec.refrigerant_commissioning_date
            rec.fgas_next_leak_check = start + relativedelta(
                months=rec.fgas_leak_check_months) \
                if start and rec.fgas_leak_check_months else False

    @api.depends('fgas_logbook_required', 'fgas_next_leak_check')
    def _compute_fgas_check_state(self):
        today = fields.Date.context_today(self)
        soon = today + timedelta(days=self._fgas_lead_days())
        for rec in self:
            if not rec.has_refrigerant or not rec.refrigerant_id \
                    or not rec.refrigerant_charge_kg:
                rec.fgas_check_state = 'unknown' if rec.has_refrigerant \
                    else 'not_required'
            elif not rec.fgas_logbook_required:
                rec.fgas_check_state = 'not_required'
            elif not rec.fgas_next_leak_check:
                rec.fgas_check_state = 'unknown'
            elif rec.fgas_next_leak_check < today:
                rec.fgas_check_state = 'overdue'
            elif rec.fgas_next_leak_check <= soon:
                rec.fgas_check_state = 'due'
            else:
                rec.fgas_check_state = 'ok'

    @api.model
    def _fgas_lead_days(self):
        return int(self.env['ir.config_parameter'].sudo().get_param(
            'serviq_flow_refrigerant.leak_check_lead_days') or 30)

    def action_open_refrigerant_logs(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Koudemiddellogboek'),
            'res_model': 'serviq.refrigerant.log',
            'view_mode': 'list,form',
            'domain': [('installation_id', '=', self.id)],
            'context': {'default_installation_id': self.id},
        }

    def action_print_refrigerant_logbook(self):
        return self.env.ref(
            'serviq_flow_refrigerant.action_report_refrigerant_logbook') \
            .report_action(self)

    # ------------------------------------------------------------------
    # Leak checks: plan the intervention ahead
    # ------------------------------------------------------------------
    @api.model
    def _cron_plan_leak_checks(self):
        """Daily: plan a leak check intervention for every installation
        whose next leak check comes within the lead time and that has no
        open leak check yet."""
        itype = self.env.ref(
            'serviq_flow_refrigerant.intervention_type_leak_check',
            raise_if_not_found=False)
        if not itype or not itype.active:
            return
        horizon = fields.Date.context_today(self) + timedelta(
            days=self._fgas_lead_days())
        Task = self.env['project.task'].sudo()
        for rec in self.sudo().search([
                ('fgas_logbook_required', '=', True),
                ('fgas_next_leak_check', '!=', False),
                ('fgas_next_leak_check', '<=', horizon),
                ('state', '!=', 'out_of_service')]):
            if Task.search_count([
                    ('serviq_installation_id', '=', rec.id),
                    ('serviq_intervention_type_id', '=', itype.id),
                    ('state', 'not in', ['1_done', '1_canceled'])], limit=1):
                continue
            project = rec._intervention_project()
            if not project:
                continue
            Task.create({
                'name': _('%(type)s - %(installation)s', type=itype.name,
                          installation=rec.name),
                'project_id': project.id,
                'partner_id': rec.customer_id.id,
                'serviq_installation_id': rec.id,
                'serviq_intervention_type_id': itype.id,
                'serviq_installer_id': rec.installer_id.id,
                'date_deadline': fields.Datetime.to_datetime(
                    rec.fgas_next_leak_check),
            })
