# -*- coding: utf-8 -*-
from odoo import api, fields, models


class DfConnectsSupplierEntity(models.Model):
    """Entity of a supplier holding stock: a warehouse, branch or subsidiary
    of the supplier's company. Created automatically from the codes the API
    returns; the name can be changed afterwards."""
    _name = 'df.connects.supplier.entity'
    _description = 'Entiteit leverancier'
    _order = 'connection_id, sequence, name'

    connection_id = fields.Many2one(
        'df.connects.connection', string='Koppeling', required=True,
        ondelete='cascade', index=True)
    partner_id = fields.Many2one(related='connection_id.partner_id',
                                 store=True, string='Leverancier')
    company_id = fields.Many2one(related='connection_id.company_id',
                                 store=True, string='Bedrijf')
    code = fields.Char(string='Code', required=True,
                       help='Code of the entity in the API of the supplier.')
    name = fields.Char(string='Naam', required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    stock_ids = fields.One2many('df.connects.supplier.stock', 'entity_id',
                                string='Voorraad')
    quantity_total = fields.Float(
        string='Beschikbaar', compute='_compute_quantity_total',
        digits='Product Unit')

    _code_uniq = models.Constraint(
        'unique(connection_id, code)',
        'Deze code bestaat al voor deze koppeling.')

    @api.depends('stock_ids.quantity')
    def _compute_quantity_total(self):
        data = self.env['df.connects.supplier.stock']._read_group(
            [('entity_id', 'in', self.ids)], ['entity_id'],
            ['quantity:sum'])
        totals = {entity.id: qty for entity, qty in data}
        for rec in self:
            rec.quantity_total = totals.get(rec.id, 0.0)


class DfConnectsSupplierStock(models.Model):
    """Available quantity of a supplier product in one entity."""
    _name = 'df.connects.supplier.stock'
    _description = 'Voorraad leverancier per entiteit'
    _order = 'supplier_product_id, entity_sequence, entity_id'

    supplier_product_id = fields.Many2one(
        'df.connects.supplier.product', string='Leveranciersproduct',
        required=True, ondelete='cascade', index=True)
    entity_id = fields.Many2one(
        'df.connects.supplier.entity', string='Entiteit', required=True,
        ondelete='cascade', index=True)
    entity_sequence = fields.Integer(related='entity_id.sequence',
                                     store=True)
    connection_id = fields.Many2one(
        related='supplier_product_id.connection_id', store=True)
    company_id = fields.Many2one(related='supplier_product_id.company_id',
                                 store=True)
    product_id = fields.Many2one(related='supplier_product_id.product_id',
                                 store=True, string='Product')
    quantity = fields.Float(string='Beschikbaar', digits='Product Unit')

    _entity_uniq = models.Constraint(
        'unique(supplier_product_id, entity_id)',
        'Een leveranciersproduct heeft één voorraadlijn per entiteit.')


class DfConnectsSyncLog(models.Model):
    """One synchronisation run of a connection."""
    _name = 'df.connects.sync.log'
    _description = 'Synchronisatie leverancierskoppeling'
    _order = 'date desc, id desc'
    _rec_name = 'date'

    connection_id = fields.Many2one(
        'df.connects.connection', string='Koppeling', required=True,
        ondelete='cascade', index=True)
    company_id = fields.Many2one(related='connection_id.company_id',
                                 store=True)
    date = fields.Datetime(string='Datum', required=True,
                           default=fields.Datetime.now)
    duration = fields.Float(string='Duur (s)', digits=(16, 1))
    state = fields.Selection([('ok', 'Geslaagd'), ('error', 'Fout')],
                             string='Resultaat', required=True)
    message = fields.Text(string='Melding')
    count_read = fields.Integer(string='Gelezen')
    count_created = fields.Integer(string='Nieuw')
    count_updated = fields.Integer(string='Bijgewerkt')
    count_archived = fields.Integer(string='Gearchiveerd')
    count_skipped = fields.Integer(string='Overgeslagen')
