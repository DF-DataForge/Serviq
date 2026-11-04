# -*- coding: utf-8 -*-
{
    'name': 'DF Connects: leverancierskoppelingen',
    'version': '19.0.1.0.0',
    'summary': 'Koppelingen met externe leveranciers via API: productgegevens, '
               'prijzen en beschikbare voorraad per entiteit',
    'description': """
Independent connector module: sets up API connections with external
suppliers and fetches their product data.

* One connection per supplier (and company): base URL, authentication
  (API key in a header or query parameter, bearer token, basic auth),
  endpoint, pagination (page number, offset, next link) and a field mapping
  that tells where every value sits in the supplier's JSON.
* Supplier products with a unique identifier (UUID): the EAN / GTIN when the
  supplier gives a valid one, otherwise the supplier product code (scoped to
  the supplier).
* Per supplier product: supplier product code, price (with currency) and
  available quantity, split over the entities of the supplier (warehouses,
  branches or subsidiaries) with the total.
* Supplier products are linked to Odoo products on EAN (barcode) or on the
  supplier product code of the vendor pricelist; optionally the vendor
  pricelist (product code and price) is updated on every sync.
* Synchronisation by hand or scheduled, per connection with its own
  interval; products the supplier no longer returns are archived.

Only depends on "product", so it can be used on any Odoo database, with or
without the Serviq modules. Supplier specific APIs can be added in a small
module by extending ``df.connects.connection`` (see README.md).
""",
    'category': 'Supply Chain',
    'author': 'Data Forge',
    'website': 'https://www.data-forge.be',
    'depends': ['product', 'mail'],
    'external_dependencies': {'python': ['requests']},
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
        'views/connection_views.xml',
        'views/supplier_product_views.xml',
        'views/product_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
