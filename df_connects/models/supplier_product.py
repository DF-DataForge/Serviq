# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class DfConnectsSupplierProduct(models.Model):
    """Product as offered by a supplier, fetched through its connection.

    ``uuid`` identifies the product: the EAN / GTIN when the supplier gives
    a valid one, otherwise the supplier product code prefixed with the
    supplier ("S<partner id>-<code>"). The same EAN coming from two
    suppliers thus gives the same UUID, so the offers of all suppliers of an
    article can be compared."""
    _name = 'df.connects.supplier.product'
    _description = 'Leveranciersproduct'
    _order = 'connection_id, name, id'
    _rec_names_search = ['name', 'uuid', 'ean', 'supplier_code']

    connection_id = fields.Many2one(
        'df.connects.connection', string='Koppeling', required=True,
        ondelete='cascade', index=True)
    partner_id = fields.Many2one(related='connection_id.partner_id',
                                 store=True, string='Leverancier', index=True)
    company_id = fields.Many2one(related='connection_id.company_id',
                                 store=True, string='Bedrijf')
    active = fields.Boolean(default=True)

    uuid = fields.Char(
        string='UUID', required=True, index=True, readonly=True,
        help='EAN when available, otherwise the supplier product code '
             'prefixed with the supplier.')
    uuid_source = fields.Selection(
        [('ean', 'EAN'), ('code', 'Leveranciersproductcode')],
        string='Bron UUID', readonly=True)
    ean = fields.Char(string='EAN', index=True, readonly=True)
    supplier_code = fields.Char(string='Leveranciersproductcode', index=True,
                                readonly=True)
    name = fields.Char(string='Omschrijving', readonly=True)
    price = fields.Monetary(string='Prijs', readonly=True,
                            currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='Munt',
                                  readonly=True)
    stock_ids = fields.One2many(
        'df.connects.supplier.stock', 'supplier_product_id',
        string='Voorraad per entiteit', readonly=True)
    quantity_total = fields.Float(
        string='Beschikbaar', compute='_compute_quantity_total', store=True,
        digits='Product Unit',
        help='Available quantity over all entities of the supplier.')
    entity_count = fields.Integer(
        string='# entiteiten met voorraad',
        compute='_compute_quantity_total', store=True)
    product_id = fields.Many2one(
        'product.product', string='Product', index=True,
        help='Odoo product this supplier product is linked to. Filled '
             'automatically on EAN or supplier product code, can be set '
             'by hand.')
    product_tmpl_id = fields.Many2one(related='product_id.product_tmpl_id',
                                      store=True, string='Productsjabloon')
    last_seen = fields.Datetime(
        string='Laatst ontvangen', readonly=True,
        help='Last sync in which the supplier returned this product.')
    raw_data = fields.Text(string='Ruwe gegevens', readonly=True)

    _uuid_uniq = models.Constraint(
        'unique(connection_id, uuid)',
        'Dit product bestaat al voor deze koppeling.')

    @api.depends('stock_ids.quantity')
    def _compute_quantity_total(self):
        for rec in self:
            quantities = rec.stock_ids.mapped('quantity')
            rec.quantity_total = sum(quantities)
            rec.entity_count = len([q for q in quantities if q > 0])

    @api.depends('name', 'supplier_code')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '[%s] %s' % (rec.supplier_code, rec.name) \
                if rec.supplier_code and rec.name != rec.supplier_code \
                else (rec.name or rec.uuid)

    def _set_stock(self, quantities):
        """Set the stock per entity from {entity: qty}. Entities no longer
        returned keep their line with quantity 0."""
        self.ensure_one()
        lines = {line.entity_id: line for line in self.stock_ids}
        Stock = self.env['df.connects.supplier.stock']
        to_create = []
        for entity, qty in quantities.items():
            line = lines.pop(entity, None)
            if line:
                if line.quantity != qty:
                    line.quantity = qty
            else:
                to_create.append({'supplier_product_id': self.id,
                                  'entity_id': entity.id, 'quantity': qty})
        if to_create:
            Stock.create(to_create)
        stale = Stock.union(*lines.values()).filtered('quantity')
        if stale:
            stale.write({'quantity': 0.0})

    def _find_product(self):
        """Odoo product matching this supplier product: same barcode as the
        EAN, otherwise the supplier product code in the vendor pricelist of
        the supplier."""
        self.ensure_one()
        Product = self.env['product.product']
        company_domain = [('company_id', 'in', [False, self.company_id.id])]
        if self.ean:
            barcodes = [self.ean]
            # Barcode stored as UPC-A (12 digits) or as GTIN-14.
            if len(self.ean) == 13 and self.ean.startswith('0'):
                barcodes.append(self.ean[1:])
            barcodes.append(self.ean.zfill(14))
            product = Product.search(
                [('barcode', 'in', barcodes)] + company_domain, limit=1)
            if product:
                return product
        if self.supplier_code:
            info = self.env['product.supplierinfo'].search([
                ('partner_id', '=', self.partner_id.id),
                ('product_code', '=', self.supplier_code),
                ('company_id', 'in', [False, self.company_id.id]),
            ], limit=1)
            if info:
                return info.product_id or \
                    info.product_tmpl_id.product_variant_ids[:1]
        return Product

    def _update_supplierinfo(self):
        """Write the supplier product code and price into the vendor
        pricelist of the linked product, creating the line when needed."""
        self.ensure_one()
        product = self.product_id
        if not product:
            return
        SupplierInfo = self.env['product.supplierinfo']
        infos = SupplierInfo.search([
            ('partner_id', '=', self.partner_id.id),
            ('product_tmpl_id', '=', product.product_tmpl_id.id),
            ('product_id', 'in', [False, product.id]),
            ('company_id', 'in', [False, self.company_id.id]),
            ('min_qty', '<=', 1),
        ], order='product_id, min_qty desc')
        # Prefer the line on the variant, then the one on the template.
        info = infos.filtered(lambda i: i.product_id == product)[:1] \
            or infos[:1]
        vals = {
            'product_code': self.supplier_code or False,
            'price': self.price,
            'currency_id': self.currency_id.id,
        }
        if info:
            changed = {k: v for k, v in vals.items()
                       if (info[k].id if k == 'currency_id' else info[k]) != v}
            if changed:
                info.write(changed)
        else:
            vals.update({
                'partner_id': self.partner_id.id,
                'product_tmpl_id': product.product_tmpl_id.id,
                'product_id': product.id
                if product.product_tmpl_id.product_variant_count > 1
                else False,
                'company_id': self.company_id.id,
                'min_qty': 0.0,
            })
            SupplierInfo.create(vals)

    def action_link_product(self):
        """Look for a matching Odoo product again."""
        for rec in self:
            product = rec._find_product()
            if product:
                rec.product_id = product
                if rec.connection_id.update_supplierinfo:
                    rec._update_supplierinfo()
        return True

    def action_open_product(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'product.product',
            'res_id': self.product_id.id,
            'view_mode': 'form',
            'name': _('Product'),
        }
