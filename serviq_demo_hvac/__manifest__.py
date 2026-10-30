# -*- coding: utf-8 -*-
{
    'name': 'Serviq demo: Frisair Klimaattechniek',
    'version': '19.0.1.0.0',
    'summary': 'Demobedrijf: een Belgische airco-installateur met '
               'installaties, serienummers, interventies en herstellingen',
    'description': """
Demo data for Serviq
====================

Installs a complete demo company, **Frisair Klimaattechniek BV**, a Belgian
HVAC / airco installer from Mechelen. The demo is about the installation
flows only; the logistics behind them (purchasing, assembly, fulfilment)
are left out and the stock starts from an opening inventory.

* One warehouse, *Frisair Werkplaats*, with a spare parts shelf and two
  service vans.
* Indoor and outdoor split units tracked by serial number; mounting kits
  with their bill of materials; spare parts; installation packages bundling
  an outdoor unit, an indoor unit and a mounting kit.
* Packages sold and delivered with their serial numbers, the installations
  at the customers with their commissioning, maintenance and repair
  interventions, in every status.
* Repair orders on installed units, found by serial number: warranty and
  paid repairs, spare parts used from the shelf or a van, every stage and
  follow-up activities.
* Sold packages still to be installed and a quotation.

Do not install this on a production database: it changes the main company
and creates a warehouse, products, partners and orders.
""",
    'category': 'Hidden',
    'author': 'Data Forge',
    'website': 'https://www.data-forge.be',
    'depends': [
        'serviq_installation',
        'repair',
        'sale_stock',
        'l10n_be',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
