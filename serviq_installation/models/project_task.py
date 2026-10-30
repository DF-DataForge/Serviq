# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

import pytz

from odoo import _, api, fields, models


class ProjectTask(models.Model):
    _inherit = 'project.task'

    serviq_installation_id = fields.Many2one(
        'serviq.installation', string='Installatie', index=True,
        tracking=True)
    serviq_intervention_type_id = fields.Many2one(
        'serviq.intervention.type', string='Type interventie', index=True,
        tracking=True)
    serviq_intervention_type_code = fields.Char(
        related='serviq_intervention_type_id.code',
        string='Code type interventie')
    serviq_installer_id = fields.Many2one(
        'res.partner', string='Installateur', index=True, tracking=True,
        domain=[('serviq_is_installer', '=', True)])
    serviq_distributor_id = fields.Many2one(
        'res.partner', string='Distributeur', index=True,
        domain=[('serviq_is_distributor', '=', True)],
        compute='_compute_serviq_distributor_id', store=True,
        readonly=False,
        help='Filled in from the installation; can be changed on the task.')

    SERVIQ_SERVICE_FIELDS = (
        'planned_date_begin', 'date_deadline', 'serviq_intervention_type_id',
        'serviq_installation_id', 'stage_id', 'state', 'date_end',
        'fsm_done', 'active',
    )
    SERVIQ_DEFAULT_SLOT_HOURS = 2.0

    @api.depends('serviq_installation_id')
    def _compute_serviq_distributor_id(self):
        # Only re-filled when the installation of the task changes, so a
        # distributor chosen by hand survives later edits.
        for task in self:
            task.serviq_distributor_id = \
                task.serviq_installation_id.distributor_id \
                or task.serviq_distributor_id

    @api.onchange('serviq_installation_id')
    def _onchange_serviq_installation_id(self):
        installation = self.serviq_installation_id
        if installation.customer_id and not self.partner_id:
            self.partner_id = installation.customer_id
        if installation.installer_id and not self.serviq_installer_id:
            self.serviq_installer_id = installation.installer_id

    @api.model
    def _serviq_intervention_domain(self):
        """Tasks that are interventions: linked to an installation or
        typed as an intervention (a first installation has no installation
        yet)."""
        return ['|', ('serviq_installation_id', '!=', False),
                ('serviq_intervention_type_id', '!=', False)]

    @api.model
    def _serviq_plan_field(self):
        """Field holding the planned start of an intervention: the planned
        date of Planning / Field Service when installed, else the
        deadline."""
        return 'planned_date_begin' if 'planned_date_begin' in self._fields \
            else 'date_deadline'

    def _serviq_is_finished(self):
        """The intervention is completed: 'Mark as done' (field service), a
        done state or a folded (closing) stage."""
        self.ensure_one()
        if 'fsm_done' in self._fields and self.fsm_done:
            return True
        if self.state == '1_done':
            return True
        return bool(self.stage_id.fold)

    # ------------------------------------------------------------------
    # Status of the installation follows its interventions
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        tasks = super().create(vals_list)
        tasks.serviq_installation_id._sync_service_state()
        return tasks

    def write(self, vals):
        installations = self.serviq_installation_id
        res = super().write(vals)
        if set(self.SERVIQ_SERVICE_FIELDS) & set(vals):
            (installations | self.serviq_installation_id) \
                ._sync_service_state()
        return res

    def unlink(self):
        installations = self.serviq_installation_id
        res = super().unlink()
        installations.exists()._sync_service_state()
        return res

    # ------------------------------------------------------------------
    # Planning from the calendar ('Inplannen via kalender')
    # ------------------------------------------------------------------
    def action_serviq_plan_in_calendar(self):
        """Open the planning calendar to pick the slot of this
        intervention."""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'serviq_installation.intervention_slot_picker',
            'name': _('Inplannen: %s', self.name),
            'params': {'task_id': self.id},
        }

    def _serviq_planned_hours(self):
        """Duration of the intervention: its current planned duration, else
        its allocated time, else two hours."""
        self.ensure_one()
        begin = self['planned_date_begin'] \
            if 'planned_date_begin' in self._fields else False
        if begin and self.date_deadline and self.date_deadline > begin:
            return (self.date_deadline - begin).total_seconds() / 3600
        return self.allocated_hours or self.SERVIQ_DEFAULT_SLOT_HOURS

    def serviq_get_slot_picker_info(self):
        self.ensure_one()
        start = self[self._serviq_plan_field()]
        return {
            'id': self.id,
            'name': self.name,
            'partner': self.partner_id.name or '',
            'hours': self._serviq_planned_hours(),
            'installer_id': self.serviq_installer_id.id or False,
            'anchor': fields.Date.to_string(
                fields.Datetime.context_timestamp(self, start).date()
                if start else fields.Date.context_today(self)),
        }

    def serviq_set_planned_slot(self, start):
        """Plan the intervention from `start` ('YYYY-MM-DD HH:MM' in the
        user's timezone) for its duration. Without a planned start field
        (no Planning / Field Service) the start becomes the deadline."""
        self.ensure_one()
        tz = pytz.timezone(self.env.user.tz or 'UTC')
        local = tz.localize(datetime.strptime(start, '%Y-%m-%d %H:%M'))
        begin = local.astimezone(pytz.utc).replace(tzinfo=None)
        if 'planned_date_begin' in self._fields:
            hours = self._serviq_planned_hours()
            self.write({
                'planned_date_begin': begin,
                'date_deadline': begin + timedelta(hours=hours),
            })
        else:
            self.write({'date_deadline': begin})
        return True
