# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

BASE_HANDLER = 'serviq.portal.flow.handler'


class PortalFlow(models.Model):
    """A front-end flow on the intervention page of the portal (first
    installation, commissioning, replacement, ...). Each flow comes with
    its own module that adds this record, a handler model (the logic) and
    a QWeb template (its section on the page). Archiving the record
    disables the flow."""
    _name = 'serviq.portal.flow'
    _description = 'Portaalflow'
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(
        required=True,
        help='Technical key of the flow, used in the URL of its form '
             '(/my/installations/intervention/<id>/flow/<code>).')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(
        string='Actief', default=True,
        help='Disabled flows are not shown in the portal.')
    description = fields.Text(string='Omschrijving', translate=True)
    intervention_type_ids = fields.Many2many(
        'serviq.intervention.type', 'serviq_portal_flow_intervention_type_rel',
        'flow_id', 'type_id', string='Types interventie',
        help='The flow is shown on interventions of these types; on every '
             'intervention when empty.')
    installation_category_ids = fields.Many2many(
        'serviq.installation.category',
        'serviq_portal_flow_installation_category_rel',
        'flow_id', 'category_id', string='Installatiecategorieën',
        help='Optional: only show the flow for installations of these '
             'categories.')
    handler_model = fields.Char(
        string='Handler', required=True, default=BASE_HANDLER,
        help='Technical name of the AbstractModel implementing the flow '
             '(inherits serviq.portal.flow.handler).')
    template = fields.Char(
        string='Template', required=True,
        help='XML id of the QWeb template rendering the section of the flow '
             'on the intervention page.')
    button_label = fields.Char(
        string='Knoptekst', translate=True,
        help='Label of the button leading to the flow in the list of '
             'interventions.')
    icon = fields.Char(
        default='fa-cogs', help='Font Awesome icon, e.g. fa-exchange.')
    module = fields.Char(
        string='Module', readonly=True,
        help='Module that provides the flow (informative).')

    _code_uniq = models.Constraint(
        'unique(code)', 'De code van een flow moet uniek zijn.')

    @api.constrains('handler_model')
    def _check_handler_model(self):
        for flow in self:
            if not flow._is_valid_handler(flow.handler_model):
                raise ValidationError(_(
                    'Model "%s" bestaat niet of is geen handler van een '
                    'portaalflow (serviq.portal.flow.handler).',
                    flow.handler_model))

    @api.model
    def _is_valid_handler(self, model_name):
        if not model_name or model_name not in self.env:
            return False
        if model_name == BASE_HANDLER:
            return True
        Model = self.env[model_name]
        return all(hasattr(Model, method) for method in (
            '_flow_applies', '_flow_values', '_flow_submit'))

    def _get_handler(self):
        """The handler of the flow (sudo), the base handler when its model
        is gone."""
        self.ensure_one()
        name = self.handler_model if self._is_valid_handler(
            self.handler_model) else BASE_HANDLER
        return self.env[name].sudo()

    def _has_template(self):
        self.ensure_one()
        return bool(self.template and self.env.ref(
            self.template, raise_if_not_found=False))

    @api.model
    def _get_applicable_flows(self, task):
        """Active flows to show on the page of intervention `task`, in
        sequence order."""
        flows = self.sudo().search([])
        return flows.filtered(
            lambda flow: flow._has_template()
            and flow._get_handler()._flow_applies(task, flow))
