# -*- coding: utf-8 -*-
{
    'name': 'Serviq demo: Frisair Klimaattechniek',
    'version': '19.0.1.0.0',
    'summary': 'Demobedrijf: een Belgische airco-installateur met een '
               'fulfilmentmagazijn, serienummers en herstellingen',
    'description': """
Demo data for Serviq
====================

Installs a complete demo company, **Frisair Klimaattechniek BV**, a Belgian
HVAC / airco installer from Mechelen.

* Two warehouses: the own *Frisair Werkplaats* (workshop, spare parts
  shelf and two service vans) and the *Stoqflow Fulfilment* warehouse that
  stores the airco units (a plain Odoo warehouse: the Stoqflow integration
  is not used).
* Indoor and outdoor split units tracked by serial number, carried through
  on the receipts and deliveries.
* Mounting kits assembled in the workshop from parts (bill of materials)
  and moved to the Stoqflow warehouse; spare parts that never go to
  Stoqflow; installation packages bundling an outdoor unit, an indoor unit
  and a mounting kit.
* Installations at the customers with their serial numbers, commissioning
  and maintenance interventions.
* Repair orders on installed units, found by serial number: warranty and
  paid repairs, spare parts used, every stage and follow-up activities.
* A few weeks of history (purchases, sales, assembly, deliveries) plus open
  orders still waiting to be delivered or received at Stoqflow.

Do not install this on a production database: it changes the main company
and creates warehouses, products, partners and orders.
""",
    'category': 'Hidden',
    'author': 'Data Forge',
    'website': 'https://www.data-forge.be',
    'depends': [
        'serviq_installation',
        'serviq_logistics',
        'repair',
        'mrp',
        'sale_stock',
        'purchase_stock',
        'l10n_be',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
