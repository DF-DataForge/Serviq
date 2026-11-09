# -*- coding: utf-8 -*-
from odoo import _, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    serviq_employee_id = fields.Many2one(
        'hr.employee', string='Werknemer',
        compute='_compute_serviq_employee_id',
        help='Employee record of this contact (through its user or as work '
             'contact). Installers need one to log hours on interventions; '
             'it is created the first time they log hours in the portal.')

    def _compute_serviq_employee_id(self):
        Employee = self.env['hr.employee'].sudo()
        for partner in self:
            employee = Employee.browse()
            if isinstance(partner.id, int):
                if partner.user_ids:
                    employee = Employee.search(
                        [('user_id', 'in', partner.user_ids.ids)], limit=1)
                if not employee and 'work_contact_id' in Employee._fields:
                    employee = Employee.search(
                        [('work_contact_id', '=', partner.id)], limit=1)
            partner.serviq_employee_id = employee

    def _serviq_get_or_create_employee(self, company=None, origin=None):
        """The employee record of the contact, created when missing: no
        user, linked to the contact as work contact, job title 'Externe
        installateur'. Timesheets on interventions need one."""
        self.ensure_one()
        if self.serviq_employee_id:
            return self.serviq_employee_id
        Employee = self.env['hr.employee'].sudo()
        company = company or self.company_id or self.env.company
        vals = {
            'name': self.name,
            'company_id': company.id,
            'job_title': _('Externe installateur'),
        }
        if 'work_contact_id' in Employee._fields:
            vals['work_contact_id'] = self.id
        employee = Employee.create(vals)
        employee.message_post(body=_(
            'Werknemer aangemaakt voor installateur %(partner)s (%(origin)s).',
            partner=self.display_name,
            origin=origin or _('vanuit het contact')))
        return employee

    def action_serviq_create_employee(self):
        """Button 'Werknemer aanmaken' on the contact."""
        self.ensure_one()
        employee = self._serviq_get_or_create_employee()
        if not self.env.user.has_group('hr.group_hr_user'):
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'success',
                    'message': _('Werknemer %s aangemaakt.', employee.name),
                    'next': {'type': 'ir.actions.client',
                             'tag': 'soft_reload'},
                },
            }
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.employee',
            'res_id': employee.id,
            'views': [(False, 'form')],
            'target': 'current',
        }

    def serviq_get_installer_rights(self):
        """Adds what the portal lets the installer do to the rights popup
        of the hours overview."""
        rights = super().serviq_get_installer_rights()
        partner = self.sudo()
        commercial = partner.commercial_partner_id
        yes, no = _('Ja'), _('Nee')
        is_installer = bool(partner.serviq_is_installer
                            or commercial.serviq_is_installer)
        is_distributor = bool(partner.serviq_is_distributor
                              or commercial.serviq_is_distributor)
        users = (partner | partner.child_ids).with_context(
            active_test=False).user_ids.filtered('active')
        portal_users = users.filtered('share')
        has_portal = bool(users) and (is_installer or is_distributor)
        roles = [label for flag, label in (
            (is_installer, _('Installateur')),
            (is_distributor, _('Distributeur'))) if flag]
        employee = partner.serviq_employee_id
        rights['sections'].append({
            'title': _('Portaal'),
            'items': [
                {'label': _('Gebruikers'),
                 'value': ', '.join(users.mapped('login'))
                 or _('Geen login')},
                {'label': _('Portaaltoegang'),
                 'value': yes if has_portal else no},
                {'label': _('Rol in het portaal'),
                 'value': ', '.join(roles) or '-'},
                {'label': _('Installaties zien'),
                 'value': _('Waar het bedrijf installateur of distributeur '
                            'is') if has_portal else no},
                {'label': _('Interventies'),
                 'value': _('Toegewezen interventies bekijken, rapporteren '
                            'en afronden')
                 if has_portal and is_installer
                 else (_('Interventies van de eigen installaties bekijken')
                       if has_portal else no)},
                {'label': _('Planning van andere installateurs'),
                 'value': yes if has_portal and is_distributor else no},
                {'label': _('Uren en km loggen'),
                 'value': yes if has_portal else no},
                {'label': _('Werknemer'),
                 'value': employee.name if employee
                 else _('Wordt aangemaakt bij de eerste uurregistratie')},
                {'label': _('Interne gebruiker'),
                 'value': yes if users - portal_users else no},
            ],
        })
        flows = self.env['serviq.portal.flow'].sudo().search([])
        rights['sections'].append({
            'title': _('Flows in het portaal'),
            'items': [{
                'label': flow.name,
                'value': ', '.join(flow.intervention_type_ids.mapped('name'))
                or _('Alle types interventie'),
            } for flow in flows] if has_portal and flows else [{
                'label': _('Geen flows beschikbaar') if has_portal
                else _('Geen portaaltoegang'), 'value': ''}],
        })
        return rights
