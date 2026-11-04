# -*- coding: utf-8 -*-
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged

from .common import FakeResponse

REQUEST = 'odoo.addons.df_connects.models.connection.requests.request'

PAGE_1 = {
    'data': [
        {'sku': 'A-1', 'ean': '5410013108009', 'name': 'Warmtepomp 8 kW',
         'price': '1.234,50', 'currency': 'EUR',
         'stock': [{'warehouse': 'BE', 'warehouse_name': 'Gent',
                    'quantity': 4},
                   {'warehouse': 'NL', 'warehouse_name': 'Breda',
                    'quantity': 6}]},
        {'sku': 'B-2', 'ean': 'invalid', 'name': 'Montagekit',
         'price': 25, 'stock': {'BE': 10}},
    ],
}
PAGE_2 = {
    'data': [
        {'sku': 'C-3', 'ean': '', 'name': 'Filter', 'price': 7.5,
         'quantity': 3},
        {'name': 'Zonder code'},
    ],
}


class TestSync(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.supplier = cls.env['res.partner'].create({'name': 'Leverancier'})
        cls.connection = cls.env['df.connects.connection'].create({
            'name': 'Test',
            'partner_id': cls.supplier.id,
            'base_url': 'https://api.example.com/v1/',
            'products_endpoint': '/products',
            'auth_type': 'bearer',
            'api_key': 'secret',
            'pagination': 'page',
            'page_size': 2,
            'map_currency': 'currency',
            'map_stock_entity_name': 'warehouse_name',
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Warmtepomp', 'barcode': '5410013108009'})
        cls.product_kit = cls.env['product.product'].create({
            'name': 'Kit'})
        cls.env['product.supplierinfo'].create({
            'partner_id': cls.supplier.id,
            'product_tmpl_id': cls.product_kit.product_tmpl_id.id,
            'product_code': 'B-2',
            'price': 20,
        })

    def _fake(self, pages):
        calls = []

        def fake_request(method, url, **kwargs):
            calls.append((method, url, kwargs))
            page = kwargs['params'].get('page', 1)
            return FakeResponse(pages[page - 1] if page <= len(pages)
                                else {'data': []})
        return fake_request, calls

    def test_sync(self):
        fake, calls = self._fake([PAGE_1, PAGE_2])
        with patch(REQUEST, side_effect=fake):
            self.connection.action_sync()
        self.assertEqual(self.connection.last_sync_state, 'ok',
                         self.connection.last_sync_message)
        # Page 2 has 2 records (= page size), so page 3 is read and empty.
        self.assertEqual(len(calls), 3)
        method, url, kwargs = calls[0]
        self.assertEqual(url, 'https://api.example.com/v1/products')
        self.assertEqual(kwargs['headers']['Authorization'], 'Bearer secret')
        self.assertEqual(kwargs['params'], {'limit': 2, 'page': 1})

        products = self.connection.supplier_product_ids
        self.assertEqual(len(products), 3)
        a1 = products.filtered(lambda p: p.supplier_code == 'A-1')
        # Valid EAN: it is the UUID.
        self.assertEqual(a1.uuid, '5410013108009')
        self.assertEqual(a1.uuid_source, 'ean')
        self.assertEqual(a1.price, 1234.5)
        self.assertEqual(a1.quantity_total, 10)
        self.assertEqual(a1.entity_count, 2)
        self.assertEqual(sorted(a1.stock_ids.mapped('entity_id.name')),
                         ['Breda', 'Gent'])
        self.assertEqual(a1.product_id, self.product)
        # Invalid EAN: the supplier code is the UUID.
        b2 = products.filtered(lambda p: p.supplier_code == 'B-2')
        self.assertEqual(b2.uuid, 'S%s-B-2' % self.supplier.id)
        self.assertEqual(b2.uuid_source, 'code')
        self.assertFalse(b2.ean)
        self.assertEqual(b2.quantity_total, 10)
        self.assertEqual(b2.product_id, self.product_kit)
        # Only a total quantity: default entity named after the supplier.
        c3 = products.filtered(lambda p: p.supplier_code == 'C-3')
        self.assertEqual(c3.quantity_total, 3)
        self.assertEqual(c3.stock_ids.entity_id.name, 'Leverancier')
        self.assertEqual(self.connection.entity_count, 3)
        log = self.connection.log_ids
        self.assertEqual((log.count_read, log.count_created,
                          log.count_skipped), (4, 3, 1))
        # Quantity on the Odoo product, summed over entities.
        self.assertEqual(self.product.df_supplier_qty, 10)
        self.assertEqual(self.product.product_tmpl_id.df_supplier_qty, 10)

        # Second run: A-1 changes, B-2 disappears, NL stock gone.
        page = {'data': [
            {'sku': 'A-1', 'ean': '5410013108009', 'name': 'Warmtepomp 8 kW',
             'price': 1200, 'stock': [{'warehouse': 'BE', 'quantity': 1}]},
            {'sku': 'C-3', 'name': 'Filter', 'price': 7.5, 'quantity': 0},
        ]}
        fake, calls = self._fake([page])
        with patch(REQUEST, side_effect=fake):
            self.connection.action_sync()
        self.assertEqual(a1.price, 1200)
        self.assertEqual(a1.quantity_total, 1)
        self.assertEqual(len(a1.stock_ids), 2, 'NL line kept with 0')
        self.assertFalse(b2.active)
        self.assertEqual(b2.quantity_total, 0)
        last_log = self.env['df.connects.sync.log'].search(
            [('connection_id', '=', self.connection.id)], limit=1)
        self.assertEqual(last_log.count_updated, 2)
        self.assertEqual(last_log.count_archived, 1)

    def test_update_supplierinfo(self):
        self.connection.update_supplierinfo = True
        fake, _calls = self._fake([PAGE_1, PAGE_2])
        with patch(REQUEST, side_effect=fake):
            self.connection.action_sync()
        info = self.env['product.supplierinfo'].search([
            ('partner_id', '=', self.supplier.id)])
        self.assertEqual(len(info), 2)
        kit = info.filtered(lambda i: i.product_code == 'B-2')
        self.assertEqual(kit.price, 25)
        heat_pump = info - kit
        self.assertEqual(heat_pump.product_tmpl_id,
                         self.product.product_tmpl_id)
        self.assertEqual((heat_pump.product_code, heat_pump.price),
                         ('A-1', 1234.5))

    def test_same_ean_two_suppliers(self):
        """The EAN identifies the article over suppliers."""
        other = self.connection.copy({
            'name': 'Andere',
            'partner_id': self.env['res.partner'].create(
                {'name': 'Andere leverancier'}).id,
            'api_key': 'secret'})
        fake, _calls = self._fake([PAGE_1, PAGE_2])
        with patch(REQUEST, side_effect=fake):
            (self.connection | other).action_sync()
        offers = self.env['df.connects.supplier.product'].search([
            ('uuid', '=', '5410013108009')])
        self.assertEqual(len(offers), 2)
        self.assertEqual(self.product.df_supplier_qty, 20)

    def test_error_is_logged(self):
        with patch(REQUEST, return_value=FakeResponse(
                {'error': 'nope'}, status=401)):
            self.connection.action_sync()
        self.assertEqual(self.connection.last_sync_state, 'error')
        self.assertIn('401', self.connection.last_sync_message)
        self.assertFalse(self.connection.supplier_product_ids)

    def test_next_link_and_api_key(self):
        self.connection.write({
            'pagination': 'next_link', 'next_link_path': 'links.next',
            'auth_type': 'api_key_query', 'api_key_name': 'key',
            'records_path': 'items'})
        responses = {
            'https://api.example.com/v1/products': {
                'items': [{'sku': 'X'}],
                'links': {'next': '/v1/products?cursor=2'}},
            'https://api.example.com/v1/products?cursor=2': {
                'items': [{'sku': 'Y'}], 'links': {'next': None}},
        }
        urls = []

        def fake(method, url, **kwargs):
            urls.append(url)
            self.assertEqual(kwargs['params']['key'], 'secret')
            return FakeResponse(responses[url])
        with patch(REQUEST, side_effect=fake):
            self.connection.action_sync()
        self.assertEqual(len(urls), 2)
        self.assertEqual(
            sorted(self.connection.supplier_product_ids.mapped(
                'supplier_code')), ['X', 'Y'])

    def test_cron(self):
        self.connection.write({'auto_sync': True, 'next_sync': False,
                               'sync_interval_type': 'hours'})
        fake, _calls = self._fake([PAGE_1])
        with patch(REQUEST, side_effect=fake):
            self.env['df.connects.connection']._cron_sync()
        self.assertEqual(self.connection.last_sync_state, 'ok')
        self.assertTrue(self.connection.next_sync)
        # Not due any more: the cron leaves it alone.
        with patch(REQUEST, side_effect=AssertionError('not due')):
            self.env['df.connects.connection']._cron_sync()
