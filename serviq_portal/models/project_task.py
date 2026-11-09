# -*- coding: utf-8 -*-
from odoo import api, fields, models

from .account_analytic_line import TRAVEL_TIME_TYPES


class ProjectTask(models.Model):
    _inherit = 'project.task'

    serviq_km_total = fields.Float(
        string='Gereden km', digits=(16, 1),
        compute='_compute_serviq_km_total',
        help='Kilometres of the rides logged on this intervention.')

    @api.depends('timesheet_ids.serviq_km')
    def _compute_serviq_km_total(self):
        for task in self:
            task.serviq_km_total = sum(task.timesheet_ids.mapped('serviq_km'))

    def _serviq_timesheets_chronological(self):
        """Timesheets of the intervention in chronological order: ride
        there, time on site, ride back."""
        self.ensure_one()
        return self.timesheet_ids.sorted(
            lambda line: (line.date, line.serviq_start or line.create_date,
                          line.id))

    def _serviq_sync_planning_from_timesheets(self):
        """Align the planning of the intervention with the time on site
        logged on it: planned start = arrival of the first registration,
        end = departure of the last one. The rides there and back do not
        count; tasks without timed registrations keep their planning.
        Without a planned start field (no Planning / Field Service) the
        arrival becomes the deadline, like the slot picker does."""
        Line = self.env['account.analytic.line'].sudo()
        has_begin = 'planned_date_begin' in self._fields
        for task in self.sudo():
            lines = Line.search([
                ('task_id', '=', task.id),
                ('serviq_start', '!=', False),
                ('serviq_end', '!=', False),
                ('serviq_time_type', 'not in', list(TRAVEL_TIME_TYPES)),
            ])
            if not lines:
                continue
            begin = min(lines.mapped('serviq_start'))
            end = max(lines.mapped('serviq_end'))
            if has_begin:
                vals = {'planned_date_begin': begin, 'date_deadline': end}
            else:
                vals = {'date_deadline': begin}
            if any(task[fname] != value for fname, value in vals.items()):
                task.write(vals)
