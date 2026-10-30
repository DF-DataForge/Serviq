# -*- coding: utf-8 -*-
{
    'name': 'Serviq Installaties',
    'version': '19.0.1.0.0',
    'summary': 'Installaties bij klanten: componenten, serienummers, '
               'interventies, planning en overzichtsdashboard',
    'description': """
Serviq Installaties
===================

Generic core of Serviq: an *installation* is a system placed at a customer
(battery system, heat pump, charger, ...), with its components and serial
numbers, its customer / distributor / installer and its interventions.

* Configurable installation categories (commissioning required, active after
  first installation, auto-create on delivery), component roles and
  intervention types - no customer-specific values in code.
* Components from the bill of materials, sub-installations, serial-number
  validation (optionally against the distributor's stock).
* Installations created automatically when a delivery is validated.
* Status follows the interventions (commissioning, service).
* Overview dashboard with counts per distributor / installer, planning
  calendar, slot picker and hours overview.
* Optional modules installable from the settings: logistic dashboards
  (serviq_logistics), the installer / distributor portal (serviq_portal) and
  its flows (serviq_flow_*).
""",
    'category': 'Services',
    'author': 'Data Forge',
    'website': 'https://www.data-forge.be',
    'depends': [
        'mail',
        'stock',
        'project',
        'hr_timesheet',
        'sale_stock',
        'purchase_stock',
        'mrp',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'data/intervention_type_data.xml',
        'data/ir_cron.xml',
        'views/installation_views.xml',
        'views/configuration_views.xml',
        'views/inherited_views.xml',
        'views/res_config_settings_views.xml',
        'wizard/sn_registration_wizard_views.xml',
        'views/menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'serviq_installation/static/src/css/installation_overview_dashboard.css',
            'serviq_installation/static/src/js/installation_overview_dashboard.js',
            'serviq_installation/static/src/xml/installation_overview_dashboard.xml',
            'serviq_installation/static/src/js/intervention_slot_picker.js',
            'serviq_installation/static/src/xml/intervention_slot_picker.xml',
            'serviq_installation/static/src/js/hours_overview.js',
            'serviq_installation/static/src/xml/hours_overview.xml',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
