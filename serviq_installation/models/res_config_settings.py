# -*- coding: utf-8 -*-
from odoo import fields, models


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
    serviq_check_distributor_stock = fields.Boolean(
        string='Serienummers controleren in distributeur-stock',
        config_parameter='serviq_installation.check_distributor_stock',
        help='A serial can only be used on an installation when it is in '
             'stock in the customer location of its distributor.')
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
