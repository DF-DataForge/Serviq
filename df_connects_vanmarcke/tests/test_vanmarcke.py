# -*- coding: utf-8 -*-
from datetime import timedelta
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from odoo import fields
from odoo.tests import TransactionCase

from odoo.addons.df_connects.tests.common import FakeResponse

MODULE = 'odoo.addons.df_connects_vanmarcke.models.connection'
REQUEST = 'odoo.addons.df_connects.models.connection.requests.request'
TOKEN = MODULE + '.requests.post'
API = 'https://api.vanmarcke.com'


def prices(net, gross):
    return [{'priceType': 'LIST', 'value': gross, 'currencyIso': 'EUR',
             'formattedValue': '%s €' % gross},
            {'priceType': 'NET', 'value': net, 'currencyIso': 'EUR'},
            {'priceType': 'RECUPEL', 'value': 0.5, 'currencyIso': 'EUR'}]


# Shapes after the Products - v2 specification (ProductListWithPriceStock,
# ProductPricesStockBulkResponse, ProductStock, ProductList).
SEAT = {
    'productId': '087953', 'barcode': '', 'supplierBarcode': '3456330114691',
    'supplierReference': '510400',
    'descriptions': [
        {'languageCode': 'fr', 'type': 'short', 'value': 'Siège de douche'},
        {'languageCode': 'nl', 'type': 'long', 'value': 'Delabie - zitting'},
        {'languageCode': 'nl', 'type': 'short', 'value': 'Douchezitting'},
    ],
    'prices': prices(212.4, 361.85),
    'stock': {'stockAvailable': True},
}
SIPHON = {
    'productId': '120965', 'supplierBarcode': '123', 'barcode': None,
    'descriptions': [], 'prices': [{'priceType': 'LIST', 'value': 4.15,
                                     'currencyIso': 'EUR'}],
    'stock': {'stockAvailable': False},
}


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
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Douchezitting', 'barcode': '3456330114691'})
        for code in ('087953', '120965', '999999'):
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
        for target, fake in ((TOKEN, self._fake_token),
                             (REQUEST, self._fake_api)):
            patcher = patch(target, side_effect=fake)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch(MODULE + '.MIN_INTERVAL', 0)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _fake_token(self, url, data=None, auth=None, **kwargs):
        self.token_calls.append((url, data, auth, kwargs['headers']))
        return FakeResponse({'access_token': 'tok%s' % len(self.token_calls),
                             'expires_in': 3600, 'refresh_token': 'ref'})

    def _fake_api(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        path = urlsplit(url).path
        if path == '/v2/products/bulk/detail':
            return FakeResponse({'products': [SEAT, SIPHON]})
        if path == '/v2/products/bulk/pricesAndStock':
            return FakeResponse({'products': [
                {k: p[k] for k in ('productId', 'prices', 'stock')}
                for p in (SEAT, SIPHON)]})
        if path.endswith('/stock/0101'):
            level = 3 if '/087953/' in path else 0
            return FakeResponse({'stockLevel': level,
                                 'stockAvailable': bool(level)})
        if path == '/v2/products':
            offset = kwargs['params'].get('offset', 0)
            products = [dict(SEAT, prices=None, stock=None)] \
                if offset == 0 else []
            return FakeResponse({'products': products, 'nextUrl': None})
        if path == '/v1/stores':
            page = kwargs['params']['currentPage']
            stores = [[{'name': '0101', 'displayName': 'Van Marcke Gent'},
                       {'name': '0202', 'displayName': 'Kortrijk'}],
                      [{'name': '0303', 'displayName': 'Luik'}]][page]
            return FakeResponse({'stores': stores, 'pagination': {
                'currentPage': page, 'totalPages': 2}})
        return FakeResponse({'errors': [{'code': 'notFound'}]}, status=404)

    def _sync(self):
        self.connection.action_sync()
        self.assertEqual(self.connection.last_sync_state, 'ok',
                         self.connection.last_sync_message)

    def test_defaults(self):
        self.assertEqual(self.connection.base_url, API)
        self.assertEqual(self.connection.auth_type, 'none')
        self.assertEqual((self.connection.vm_country,
                          self.connection.vm_channel), ('be', 'b2b'))

    def test_sync(self):
        self._sync()
        # Token: password grant, client id / secret as basic auth.
        url, data, auth, headers = self.token_calls[0]
        self.assertEqual(url, API + '/v1/oauth/token')
        self.assertEqual(data, {'grant_type': 'password',
                                'username': 'API-APP1-P123456',
                                'password': 'pw'})
        self.assertEqual(auth, ('client', 'secret'))
        self.assertEqual(headers['x-api-key'], 'app-key')
        self.assertEqual(len(self.token_calls), 1, 'token cached')
        # One bulk call with details, prices and stock, then store stock.
        method, url, kwargs = self.calls[0]
        split = urlsplit(url)
        self.assertEqual((method, split.path),
                         ('POST', '/v2/products/bulk/detail'))
        self.assertEqual(parse_qs(split.query), {
            'catalogCountry': ['be'], 'channel': ['b2b'],
            'language': ['nl'], 'includePriceAndStock': ['true']})
        self.assertEqual(kwargs['json'], {
            'productIds': ['087953', '120965', '999999']})
        self.assertEqual(kwargs['headers']['x-api-key'], 'app-key')
        self.assertEqual(kwargs['headers']['Authorization'], 'Bearer tok1')
        self.assertEqual(urlsplit(self.calls[1][1]).path,
                         '/v2/products/087953/stock/0101')
        self.assertEqual(len(self.calls), 3)

        products = self.connection.supplier_product_ids
        self.assertEqual(len(products), 2, '999999 unknown at Van Marcke')
        seat = products.filtered(lambda p: p.supplier_code == '087953')
        self.assertEqual(seat.uuid, '3456330114691')
        self.assertEqual(seat.name, 'Douchezitting')
        self.assertEqual(seat.price, 212.4, 'net price')
        self.assertEqual(seat.product_id, self.product)
        self.assertTrue(seat.available)
        stock = {line.entity_id.name: (line.quantity, line.available)
                 for line in seat.stock_ids}
        self.assertEqual(stock, {'Centraal magazijn': (0, True),
                                 'Gent': (3, True)})
        self.assertEqual(seat.quantity_total, 3)
        siphon = products.filtered(lambda p: p.supplier_code == '120965')
        # Invalid EAN: the product number is the UUID.
        self.assertEqual(siphon.uuid, 'S%s-120965' % self.vm.id)
        self.assertEqual(siphon.price, 4.15, 'no net price: list price')
        self.assertFalse(siphon.available)

    def test_list_price(self):
        self.connection.vm_price_type = 'LIST'
        self._sync()
        seat = self.connection.supplier_product_ids.filtered(
            lambda p: p.supplier_code == '087953')
        self.assertEqual(seat.price, 361.85)

    def test_token_refresh(self):
        self._sync()
        self.assertEqual(self.connection.sudo().vm_access_token, 'tok1')
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
        with patch(REQUEST, side_effect=fake):
            self._sync()
        self.assertEqual(len(self.token_calls), 2)
        self.assertEqual(self.calls[0][2]['headers']['Authorization'],
                         'Bearer tok2')

    def test_client_credentials_prices_only(self):
        self.connection.write({
            'vm_grant_type': 'client_credentials', 'vm_scope': 'codes',
            'vm_product_codes': '087953\n087953, 120965',
            'vm_fetch_details': False})
        self.store.vm_store_stock = False
        self._sync()
        self.assertEqual(self.token_calls[0][1],
                         {'grant_type': 'client_credentials'})
        self.assertEqual(len(self.calls), 1)
        split = urlsplit(self.calls[0][1])
        self.assertEqual(split.path, '/v2/products/bulk/pricesAndStock')
        self.assertEqual(parse_qs(split.query), {'catalogCountry': ['be']})
        self.assertEqual(self.calls[0][2]['json'],
                         {'productIds': ['087953', '120965']})
        seat = self.connection.supplier_product_ids.filtered(
            lambda p: p.supplier_code == '087953')
        self.assertEqual(seat.uuid_source, 'code', 'no details, no EAN')
        self.assertTrue(seat.available)

    def test_catalog(self):
        self.connection.vm_scope = 'catalog'
        self.store.vm_store_stock = False
        self._sync()
        listing = [c for c in self.calls
                   if urlsplit(c[1]).path == '/v2/products']
        self.assertEqual(listing[0][2]['params'], {
            'catalogCountry': 'be', 'channel': 'b2b', 'language': 'nl',
            'excludeArchived': 'true', 'limit': 100, 'offset': 0})
        # Listing has the details, prices and stock come from the bulk call.
        self.assertEqual(urlsplit(self.calls[-1][1]).path,
                         '/v2/products/bulk/pricesAndStock')
        seat = self.connection.supplier_product_ids
        self.assertEqual(seat.uuid, '3456330114691')
        self.assertEqual(seat.price, 212.4)

    def test_fetch_stores(self):
        self.connection.action_vm_fetch_stores()
        entities = self.connection.entity_ids
        self.assertEqual(sorted(entities.mapped('code')),
                         ['0101', '0202', '0303'])
        self.assertEqual(self.store.name, 'Gent', 'existing name kept')
        self.assertFalse(entities.filtered(
            lambda e: e.code == '0202').vm_store_stock)

    def test_missing_credentials(self):
        self.connection.vm_client_secret = False
        self.connection.action_sync()
        self.assertEqual(self.connection.last_sync_state, 'error')
        self.assertIn('client secret', self.connection.last_sync_message)
        self.assertFalse(self.calls)
