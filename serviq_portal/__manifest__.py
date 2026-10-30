# -*- coding: utf-8 -*-
{
    'name': 'Serviq Portaal',
    'version': '19.0.1.0.0',
    'summary': 'Portaal voor installateurs en distributeurs: installaties, '
               'interventies, planning en uitbreidbare flows',
    'description': """
Serviq Portaal
==============

Portal pages under /my/installations for installers and distributors
(matched through the commercial partner of the portal user):

* Installations: list and detail (components, serial numbers,
  interventions).
* Interventions: list filtered per intervention type, planning calendar
  and the intervention page (report / notes, logged hours, mark as done).
* Flow framework: front-end flows on the intervention page are records of
  ``serviq.portal.flow`` backed by a handler model inheriting
  ``serviq.portal.flow.handler``. Flows are optional modules
  (serviq_flow_*), can be enabled / disabled in Installaties >
  Configuratie > Flows and new ones can be added by any module. See
  README.md.
""",
    'category': 'Services',
    'author': 'Data Forge',
    'website': 'https://www.data-forge.be',
    'depends': [
        'serviq_installation',
        'portal',
        'website',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/portal_flow_views.xml',
        'views/portal_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'serviq_portal/static/src/css/portal.css',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
