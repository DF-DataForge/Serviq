# -*- coding: utf-8 -*-
{
    'name': 'Serviq Flow: vervanging',
    'version': '19.0.1.0.0',
    'summary': 'Portaalflow: componenten van een installatie vervangen, '
               'met historiek van de vervangingen',
    'description': """
Flow "Vervanging" for the Serviq portal.

On a replacement intervention the installer picks a component of the
installation (role "Vervangbaar", or any component with a serial number
when it has no role) and enters the serial number of the new part. The
serial is validated like on the installation (product, not used elsewhere,
distributor stock), swapped on the component and registered in the
replacement history (tab "Vervangingen" on the installation).
""",
    'category': 'Services',
    'author': 'Data Forge',
    'website': 'https://www.data-forge.be',
    'depends': ['serviq_portal'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/installation_replacement_views.xml',
        'views/flow_templates.xml',
        'data/flow_data.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
