# -*- coding: utf-8 -*-
from odoo import api, fields, models

# Kinds of time logged from the portal. Only the time on site moves the
# planning of the intervention.
TRAVEL_TIME_TYPES = ('travel', 'travel_back')


class AccountAnalyticLine(models.Model):
    """Time logged on an intervention from the portal: the ride there
    ('Heenrit'), the time on site and the ride back ('Terugrit'), each with
    its start and end, and the kilometres of the rides. The time on site
    sets the planning of the intervention."""
    _inherit = 'account.analytic.line'

    serviq_start = fields.Datetime(
        string='Van',
        help='Start of the logged time (departure to the customer, arrival '
             'or departure at the customer), as logged in the portal.')
    serviq_end = fields.Datetime(
        string='Tot',
        help='End of the logged time, as logged in the portal.')
    serviq_time_type = fields.Selection(
        [('travel', 'Heenrit'), ('intervention', 'Interventie'),
         ('travel_back', 'Terugrit')],
        string='Soort tijd',
        help='Ride there (departure to the customer -> arrival), time on '
             'site (arrival -> departure at the customer) or ride back '
             '(departure at the customer -> back), as logged in the portal. '
             'Only the time on site sets the planning of the intervention.')
    serviq_km = fields.Float(
        string='Km', digits=(16, 1),
        help='Kilometres driven for this ride, as logged in the portal.')

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines.filtered('serviq_start').task_id \
            ._serviq_sync_planning_from_timesheets()
        return lines

    def write(self, vals):
        tasks = self.task_id
        res = super().write(vals)
        if {'serviq_start', 'serviq_end', 'serviq_time_type',
                'task_id'} & set(vals):
            (tasks | self.task_id)._serviq_sync_planning_from_timesheets()
        return res

    def unlink(self):
        tasks = self.filtered('serviq_start').task_id
        res = super().unlink()
        tasks.exists()._serviq_sync_planning_from_timesheets()
        return res
