# -*- coding: utf-8 -*-
{
    'name': 'Serviq Flow: inbedrijfstelling',
    'version': '19.0.1.0.0',
    'summary': 'Portaalflow: componenten aanvullen en de '
               'inbedrijfstelling afronden',
    'description': """
Flow "Inbedrijfstelling" for the Serviq portal.

On a commissioning intervention the installer completes the components of
the linked installation (serial number, note) and finishes the
commissioning. Finishing marks the intervention as done, after which the
core puts the installation in the "Actief" status.
""",
    'category': 'Services',
    'author': 'Data Forge',
    'website': 'https://www.data-forge.be',
    'depends': ['serviq_portal'],
    'data': [
        'views/flow_templates.xml',
        'data/flow_data.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
