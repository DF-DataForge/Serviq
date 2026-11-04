# -*- coding: utf-8 -*-
import json
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests import TransactionCase

from odoo.addons.df_connects.tests.common import FakeResponse

MODULE = 'odoo.addons.df_connects_vanmarcke.models.connection'
REQUEST = 'odoo.addons.df_connects.models.connection.requests.request'
TOKEN = MODULE + '.requests.post'
API = 'https://api.vanmarcke.com'

DETAILS = {'products': [
    {'productId': '20017648', 'supplierBarcode': '3456330114691',
     'descriptionShort': 'Delabie douchezitting wit'},
    {'productId': '20017649', 'supplierBarcode': '',
     'descriptionShort': 'Sifon 32 mm'},
]}
PRICES = [
    {'productId': '20017648', 'netPrice': 212.4, 'currency': 'EUR',
     'stock': {'quantity': 7}},
    {'productId': '20017649', 'netPrice': '4,15', 'stock': {'quantity': 0}},
]


class TestVanMarcke(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vm = cls.env['res.partner'].create({'name': 'Van Marcke',
                                                'is_company': True})
        cls.connection = cls.env['df.connects.connection'].create({
            'name': 'Van Marcke',
            'partner_id': cls.vm.id,
            'connector_type': 'vanmarcke',
            'vm_client_id': 'client',
            'vm_client_secret': 'secret',
            'api_key': 'app-key',
            'username': 'API-APP1-P123456',
            'password': 'pw',
            'vm_scope': 'supplierinfo',
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Douchezitting', 'barcode': '3456330114691'})
        for code in ('20017648', '20017649', '99999999'):
            cls.env['product.supplierinfo'].create({
                'partner_id': cls.vm.id,
                'product_tmpl_id': cls.product.product_tmpl_id.id,
                'product_code': code,
            })
        cls.store = cls.env['df.connects.supplier.entity'].create({
            'connection_id': cls.connection.id, 'code': '0101',
            'name': 'Gent', 'vm_store_stock': True})

    def setUp(self):
        super().setUp()
        self.calls = []
        self.token_calls = []

    def _fake_token(self, url, data=None, auth=None, **kwargs):
        self.token_calls.append((url, data, auth, kwargs['headers']))
        return FakeResponse({'access_token': 'tok%s' % len(self.token_calls),
                             'expires_in': 3600, 'refresh_token': 'ref'})

    def _fake_api(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if url.endswith('/bulk/detail'):
            return FakeResponse(DETAILS)
        if url.endswith('/bulk/pricesAndStock'):
            return FakeResponse(PRICES)
        if '/stock/0101' in url:
            qty = 3 if '/20017648/' in url else 1
            return FakeResponse({'storeId': '0101', 'quantity': qty})
        if url == API + '/v1/stores':
            return FakeResponse({'stores': [
                {'storeId': '0101', 'name': 'Van Marcke Gent'},
                {'storeId': '0202', 'name': 'Van Marcke Kortrijk'}]})
        return FakeResponse({'errors': [{'code': 'notFound'}]}, status=404)

    def _sync(self):
        with patch(TOKEN, side_effect=self._fake_token), \
                patch(REQUEST, side_effect=self._fake_api), \
                patch(MODULE + '.MIN_INTERVAL', 0):
            self.connection.action_sync()
        self.assertEqual(self.connection.last_sync_state, 'ok',
                         self.connection.last_sync_message)

    def test_defaults(self):
        self.assertEqual(self.connection.base_url, API)
        self.assertEqual(self.connection.auth_type, 'none')
        self.assertEqual(self.connection.map_stock_path, 'dfStock')

    def test_sync(self):
        self._sync()
        # Token: password grant, client id / secret as basic auth.
        url, data, auth, headers = self.token_calls[0]
        self.assertEqual(url, API + '/v1/oauth/token')
        self.assertEqual(data, {'grant_type': 'password',
                                'username': 'API-APP1-P123456',
                                'password': 'pw'})
        self.assertEqual(auth, ('client', 'secret'))
        self.assertEqual(len(self.token_calls), 1, 'token cached')
        # Bulk calls with all product numbers, then store stock per product.
        method, url, kwargs = self.calls[0]
        self.assertEqual((method, url),
                         ('POST', API + '/v2/products/bulk/detail'))
        self.assertEqual(kwargs['json'], {
            'productIds': ['20017648', '20017649', '99999999']})
        self.assertEqual(kwargs['headers']['x-api-key'], 'app-key')
        self.assertEqual(kwargs['headers']['Authorization'], 'Bearer tok1')
        self.assertEqual(kwargs['params'], {'country': 'BE', 'language': 'nl'})
        self.assertEqual(self.calls[1][1],
                         API + '/v2/products/bulk/pricesAndStock')
        self.assertEqual(len(self.calls), 4)

        products = self.connection.supplier_product_ids
        self.assertEqual(len(products), 2, '99999999 unknown at Van Marcke')
        seat = products.filtered(lambda p: p.supplier_code == '20017648')
        self.assertEqual(seat.uuid, '3456330114691')
        self.assertEqual(seat.name, 'Delabie douchezitting wit')
        self.assertEqual(seat.price, 212.4)
        self.assertEqual(seat.product_id, self.product)
        self.assertEqual(seat.quantity_total, 10)
        stock = {line.entity_id.name: line.quantity for line in seat.stock_ids}
        self.assertEqual(stock, {'Centraal magazijn': 7, 'Gent': 3})
        siphon = products.filtered(lambda p: p.supplier_code == '20017649')
        self.assertEqual(siphon.uuid, 'S%s-20017649' % self.vm.id)
        self.assertEqual(siphon.price, 4.15)
        self.assertEqual(siphon.quantity_total, 1)

    def test_token_reuse_and_refresh(self):
        self._sync()
        self.assertEqual(self.connection.sudo().vm_access_token, 'tok1')
        # Expired: refreshed with the refresh token.
        self.connection.sudo().vm_token_expires = \
            fields.Datetime.now() - timedelta(minutes=1)
        self._sync()
        self.assertEqual(self.token_calls[1][1],
                         {'grant_type': 'refresh_token',
                          'refresh_token': 'ref'})

    def test_401_gets_new_token(self):
        answers = [FakeResponse({'errors': [{'code': 'expired'}]},
                                status=401)]

        def fake(method, url, **kwargs):
            if answers:
                return answers.pop()
            return self._fake_api(method, url, **kwargs)
        with patch(TOKEN, side_effect=self._fake_token), \
                patch(REQUEST, side_effect=fake), \
                patch(MODULE + '.MIN_INTERVAL', 0):
            self.connection.action_sync()
        self.assertEqual(self.connection.last_sync_state, 'ok',
                         self.connection.last_sync_message)
        self.assertEqual(len(self.token_calls), 2)
        self.assertEqual(self.calls[0][2]['headers']['Authorization'],
                         'Bearer tok2')

    def test_client_credentials_and_codes(self):
        self.connection.write({
            'vm_grant_type': 'client_credentials', 'vm_scope': 'codes',
            'vm_product_codes': '20017648\n20017648, 20017649',
            'vm_fetch_details': False})
        self.store.vm_store_stock = False
        self._sync()
        self.assertEqual(self.token_calls[0][1],
                         {'grant_type': 'client_credentials'})
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0][2]['json'],
                         {'productIds': ['20017648', '20017649']})
        seat = self.connection.supplier_product_ids.filtered(
            lambda p: p.supplier_code == '20017648')
        # Without details no EAN: the product number is the UUID.
        self.assertEqual(seat.uuid_source, 'code')
        self.assertEqual(seat.quantity_total, 7)

    def test_fetch_stores(self):
        with patch(TOKEN, side_effect=self._fake_token), \
                patch(REQUEST, side_effect=self._fake_api), \
                patch(MODULE + '.MIN_INTERVAL', 0):
            self.connection.action_vm_fetch_stores()
        entities = self.connection.entity_ids
        self.assertEqual(sorted(entities.mapped('code')), ['0101', '0202'])
        self.assertEqual(self.store.name, 'Gent', 'existing name kept')
        self.assertFalse(entities.filtered(
            lambda e: e.code == '0202').vm_store_stock)

    def test_missing_credentials(self):
        self.connection.vm_client_secret = False
        with patch(REQUEST, side_effect=AssertionError('no call')):
            self.connection.action_sync()
        self.assertEqual(self.connection.last_sync_state, 'error')
        self.assertIn('client secret', self.connection.last_sync_message)
