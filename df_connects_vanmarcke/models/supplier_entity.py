# -*- coding: utf-8 -*-
from odoo import fields, models


class DfConnectsSupplierEntity(models.Model):
    _inherit = 'df.connects.supplier.entity'

    vm_store_stock = fields.Boolean(
        string='Winkelvoorraad ophalen',
        help='Van Marcke: fetch the stock of this store (code = store id) '
             'for every product. Costs one API call per product and store.')
