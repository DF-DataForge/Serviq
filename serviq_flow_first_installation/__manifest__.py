# -*- coding: utf-8 -*-
{
    'name': 'Serviq Flow: eerste installatie',
    'version': '19.0.1.0.0',
    'summary': 'Portaalflow: installatie registreren bij de eerste '
               'installatie (product en serienummer)',
    'description': """
Flow "Eerste installatie" for the Serviq portal.

On an intervention of type "Eerste installatie" without installation the
installer chooses the installation product (component role "Installatieproduct")
and its serial number among the serials in the customer stock of the
distributor. The installation is created with the components of the bill of
materials and linked to the intervention; it is active right away when its
category is "Actief na eerste installatie", else "Installatie bezig".
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
