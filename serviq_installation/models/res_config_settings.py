# -*- coding: utf-8 -*-
from odoo import fields, models

from .installation import SN_VALIDATION_MODES


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Optional modules: ticking one installs it, unticking uninstalls it.
    module_serviq_installation_map = fields.Boolean(
        string='Kaart van de installaties')
    module_serviq_logistics = fields.Boolean(
        string='Logistieke dashboards')
    module_serviq_portal = fields.Boolean(
        string='Portaal installateurs en distributeurs')
    module_serviq_flow_first_installation = fields.Boolean(
        string='Flow: eerste installatie')
    module_serviq_flow_commissioning = fields.Boolean(
        string='Flow: inbedrijfstelling')
    module_serviq_flow_replacement = fields.Boolean(
        string='Flow: vervanging van componenten')
    module_serviq_flow_refrigerant = fields.Boolean(
        string='Flow: koudemiddelregistratie (F-gassen)')

    serviq_intervention_project_id = fields.Many2one(
        'project.project', string='Project interventies',
        config_parameter='serviq_installation.intervention_project_id',
        help='Project new interventions are created in. Empty: the field '
             'service project when Field Service is installed.')
    group_serviq_distributor = fields.Boolean(
        string='Werken met distributeurs',
        implied_group='serviq_installation.group_serviq_distributor',
        help='Installations are sold through distributors: distributor on '
             'the installations and interventions, distributor role in the '
             'portal, serial numbers from the stock of the distributor.')
    serviq_sn_validation = fields.Selection(
        SN_VALIDATION_MODES, string='Validatie serienummers',
        config_parameter='serviq_installation.sn_validation',
        default='none', required=True,
        help='Where a serial must be in stock to be used on an '
             'installation: anywhere (no validation), in a customer '
             'location (delivered), or in the customer location of the '
             'distributor of the installation.')
    serviq_distributor_locations = fields.Boolean(
        string='Klantlocatie per distributeur',
        config_parameter='serviq_installation.distributor_locations',
        help='Give every distributor (and its contacts) its own customer '
             'stock location.')
    serviq_service_lead_days = fields.Integer(
        string='Dagen vooraf in service',
        config_parameter='serviq_installation.service_lead_days',
        default=14,
        help='An installation goes in service this many days before a '
             'planned intervention.')
