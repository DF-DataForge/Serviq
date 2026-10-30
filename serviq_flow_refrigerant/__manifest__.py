# -*- coding: utf-8 -*-
{
    'name': 'Serviq Flow: koudemiddelregistratie (F-gassen)',
    'version': '19.0.1.0.0',
    'summary': 'Registratie van koeltechnische systemen en hun '
               'koudemiddellogboek volgens de F-gassenverordening',
    'description': """
Flow "Koudemiddelregistratie" for the Serviq portal, with the F-gas
logbook in the backend.

* Refrigeration system data on the installation: refrigerant (with GWP),
  nominal charge in kg and tonnes CO2-equivalent, hermetically sealed,
  fixed leak detection system, date in service.
* Obligations computed from the charge in CO2-eq: logbook from 5 t (10 t
  for hermetically sealed systems), leak check every 12 / 6 / 3 months
  from 5 / 50 / 500 t, halved frequency with a fixed leak detection system,
  warning when the mandatory leak detection is missing from 500 t.
* Logbook per installation: charge, addition, recovery, leak check
  (result, location, follow-up), repair, maintenance, failure /
  alarm, decommissioning; origin of added refrigerant (new, recycled,
  reclaimed, with name and address of the facility); certified technician
  and company with their certificate numbers. Entries cannot be changed by
  users nor deleted within 5 years.
* Cylinder balance (flesbalans) of the refrigeration company: purchases,
  returns, hand-ins for destruction or recycling and transfers, together
  with the charges and recoveries of the logbook.
* Leak check interventions planned automatically before they are due;
  logbook as PDF, also from the portal for an inspection on site.

Installations count as refrigeration systems when their category is marked
"Koeltechnisch systeem" or a refrigerant is set. The GWP values shipped are
those of the IPCC AR4 as used in the F-gas regulation; check them against
the regulation in force.
""",
    'category': 'Services',
    'author': 'Data Forge',
    'website': 'https://www.data-forge.be',
    'depends': ['serviq_portal'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/refrigerant_data.xml',
        'data/intervention_type_data.xml',
        'data/ir_cron.xml',
        'views/refrigerant_views.xml',
        'report/refrigerant_logbook_report.xml',
        'views/flow_templates.xml',
        'data/flow_data.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
