# -*- coding: utf-8 -*-
"""Van Marcke connector, after the OpenAPI specifications of the Van Marcke
developer portal (Products - v2, Stores - v1, OAuth - v1)."""
import logging
import re
import threading
import time
from datetime import timedelta

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.df_connects.models.tools import normalize_ean, to_text

_logger = logging.getLogger(__name__)

API_URLS = {
    'production': 'https://api.vanmarcke.com',
    'test': 'https://api-test.vanmarcke.com',
}
PRODUCTS_PATH = '/v2/products'
STORES_PATH = '/v1/stores'
TOKEN_PATH = '/v1/oauth/token'
# Bulk endpoints take at most 50 product ids.
BULK_SIZE = 50
# Van Marcke allows 1 call every 20 ms (API Security Policies).
MIN_INTERVAL = 0.02
MAX_RETRIES = 3
CENTRAL_ENTITY = 'central'
STORES_PAGE_SIZE = 100

_rate_lock = threading.Lock()
_last_call = {'time': 0.0}

# Written on the connection when its type is Van Marcke: the catalog
# listing GET /v2/products pages with limit / offset and returns
# {"products": [...], "nextUrl": ...}.
VANMARCKE_DEFAULTS = {
    'products_endpoint': PRODUCTS_PATH,
    'auth_type': 'none',
    'http_method': 'GET',
    'pagination': 'offset',
    'offset_param': 'offset',
    'page_size_param': 'limit',
    'page_size': 100,
    'records_path': 'products',
    'map_code': 'productId',
    'map_ean': 'supplierBarcode',
}


class DfConnectsConnection(models.Model):
    _inherit = 'df.connects.connection'

    connector_type = fields.Selection(
        selection_add=[('vanmarcke', 'Van Marcke')],
        ondelete={'vanmarcke': 'set default'})

    vm_environment = fields.Selection(
        [('production', 'Productie'), ('test', 'Test')],
        string='Omgeving Van Marcke', default='production')
    vm_grant_type = fields.Selection([
        ('password', 'Service user (nettoprijzen klant)'),
        ('client_credentials', 'Client credentials (algemene prijzen)'),
    ], string='Aanmelden als', default='password',
        help='Service user: OAuth "Resource Owner Password" grant with the '
             'service user of your customer number, the API returns your '
             'net prices. Client credentials: no customer, generic '
             'responses without customer prices.')
    vm_client_id = fields.Char(
        string='Client ID', groups='df_connects.group_df_connects_manager',
        help='Client id received from Van Marcke after the application '
             'registration.')
    vm_client_secret = fields.Char(
        string='Client secret',
        groups='df_connects.group_df_connects_manager')
    vm_token_url = fields.Char(
        string='Token-URL',
        help='Empty: <API>/v1/oauth/token of the chosen environment.')
    vm_access_token = fields.Char(groups='base.group_system', copy=False)
    vm_refresh_token = fields.Char(groups='base.group_system', copy=False)
    vm_token_expires = fields.Datetime(string='Token geldig tot',
                                       copy=False, readonly=True)

    vm_country = fields.Selection(
        [('be', 'België'), ('fr', 'Frankrijk'), ('lu', 'Luxemburg')],
        string='Catalogusland', default='be')
    vm_channel = fields.Selection(
        [('b2b', 'B2B'), ('b2c', 'B2C'), ('diy', 'DIY')],
        string='Kanaal', default='b2b')
    vm_language = fields.Selection(
        [('nl', 'Nederlands'), ('fr', 'Frans'), ('de', 'Duits'),
         ('en', 'Engels')], string='Taal', default='nl')
    vm_price_type = fields.Selection(
        [('NET', 'Nettoprijs'), ('LIST', 'Brutoprijs (lijstprijs)')],
        string='Prijs', default='NET',
        help='Price type taken from the price list of the product. When it '
             'is missing (e.g. no net price with client credentials) the '
             'other one is used.')
    vm_scope = fields.Selection([
        ('supplierinfo', 'Producten uit de leveranciersprijslijst'),
        ('codes', 'Lijst van productnummers'),
        ('catalog', 'Volledige catalogus'),
    ], string='Op te halen producten', default='supplierinfo',
        help='Vendor pricelist: the Van Marcke product numbers in the vendor '
             'pricelist (product code) of Van Marcke and the products '
             'fetched before. List: the product numbers below. Catalog: '
             'every product of the listing (many API calls, mind the daily '
             'quota).')
    vm_product_codes = fields.Text(
        string='Productnummers',
        help='Van Marcke product numbers, separated by spaces, commas or '
             'new lines.')
    vm_fetch_details = fields.Boolean(
        string='Productdetails ophalen', default=True,
        help='Fetch the EAN and description with the price and stock '
             '(/bulk/detail with price and stock, one call per 50 products). '
             'Without: only /bulk/pricesAndStock, faster but without EAN, '
             'so the product number is the UUID.')
    vm_exclude_archived = fields.Boolean(
        string='Gearchiveerde producten overslaan', default=True,
        help='Full catalog: skip the products with status "archived".')
    vm_central_name = fields.Char(string='Naam centraal magazijn',
                                  default='Centraal magazijn')

    @api.onchange('connector_type', 'vm_environment')
    def _onchange_vanmarcke(self):
        if self.connector_type != 'vanmarcke':
            return
        self.base_url = API_URLS[self.vm_environment or 'production']
        if self.products_endpoint != PRODUCTS_PATH:
            self.update(VANMARCKE_DEFAULTS)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('connector_type') == 'vanmarcke':
                for key, value in VANMARCKE_DEFAULTS.items():
                    vals.setdefault(key, value)
                vals.setdefault('base_url', API_URLS[
                    vals.get('vm_environment') or 'production'])
        return super().create(vals_list)

    def write(self, vals):
        if {'vm_environment', 'vm_grant_type', 'vm_client_id',
                'username'} & set(vals):
            # Other credentials: the cached token no longer applies.
            vals = dict(vals, vm_access_token=False, vm_refresh_token=False,
                        vm_token_expires=False)
        return super().write(vals)

    # ------------------------------------------------------------------------
    # Authentication (OAuth - v1)
    # ------------------------------------------------------------------------
    def _vm_api_url(self, path=''):
        self.ensure_one()
        return API_URLS[self.vm_environment or 'production'] + path

    def _get_url(self, path):
        if self.connector_type != 'vanmarcke':
            return super()._get_url(path)
        path = (path or '').strip()
        if path.startswith(('http://', 'https://')):
            return path
        return self._vm_api_url('/' + path.lstrip('/'))

    def _vm_get_token(self, force=False):
        """Valid OAuth access token: the cached one, a refreshed one, or a
        new one with the grant type of the connection."""
        self.ensure_one()
        conn = self.sudo()
        now = fields.Datetime.now()
        if not force and conn.vm_access_token and conn.vm_token_expires \
                and conn.vm_token_expires > now + timedelta(seconds=60):
            return conn.vm_access_token
        if not conn.vm_client_id or not conn.vm_client_secret:
            raise UserError(_('Vul de client ID en het client secret van '
                              'Van Marcke in.'))
        token_data = None
        if conn.vm_refresh_token:
            # Refresh tokens are valid for 365 days.
            token_data = conn._vm_token_request({
                'grant_type': 'refresh_token',
                'refresh_token': conn.vm_refresh_token,
            }, raise_error=False)
        if not token_data:
            if conn.vm_grant_type == 'password':
                if not conn.username or not conn.password:
                    raise UserError(_(
                        'Vul de gebruikersnaam en het wachtwoord van de '
                        'service user van Van Marcke in.'))
                data = {'grant_type': 'password',
                        'username': conn.username,
                        'password': conn.password}
            else:
                data = {'grant_type': 'client_credentials'}
            token_data = conn._vm_token_request(data)
        expires_in = int(token_data.get('expires_in') or 3600)
        conn.write({
            'vm_access_token': token_data['access_token'],
            # A refresh without a new refresh token keeps the old one.
            'vm_refresh_token': token_data.get('refresh_token') or (
                conn.vm_refresh_token
                if token_data['_grant_type'] == 'refresh_token' else False),
            'vm_token_expires': now + timedelta(seconds=expires_in),
        })
        return token_data['access_token']

    def _vm_token_request(self, data, raise_error=True):
        """POST to the token endpoint with client id / secret as basic
        authentication. Returns the decoded token response, or None when
        it failed and ``raise_error`` is False."""
        url = self.vm_token_url or self._vm_api_url(TOKEN_PATH)
        headers = {'Accept': 'application/json'}
        if self.api_key:
            headers['x-api-key'] = self.api_key
        try:
            response = requests.post(
                url, data=data, headers=headers, timeout=self.timeout,
                auth=(self.vm_client_id, self.vm_client_secret),
                verify=self.verify_ssl)
        except requests.exceptions.RequestException as e:
            if not raise_error:
                return None
            raise UserError(_('Geen verbinding met %(url)s: %(error)s',
                              url=url, error=e))
        token_data = None
        if response.status_code < 400:
            try:
                token_data = response.json()
            except ValueError:
                token_data = None
        if token_data and token_data.get('access_token'):
            token_data['_grant_type'] = data['grant_type']
            return token_data
        if not raise_error:
            return None
        raise UserError(_(
            'Aanmelden bij Van Marcke mislukt (%(status)s): %(body)s',
            status=response.status_code, body=(response.text or '')[:500]))

    def _get_request_auth(self):
        if self.connector_type != 'vanmarcke':
            return super()._get_request_auth()
        self.ensure_one()
        conn = self.sudo()
        if not conn.api_key:
            raise UserError(_(
                'Vul de Application Key van Van Marcke in (API-sleutel): ze '
                'wordt als header "x-api-key" meegestuurd.'))
        # auth_type is "none" for Van Marcke: the base only adds the extra
        # headers and parameters.
        headers, params, _auth = super()._get_request_auth()
        headers['x-api-key'] = conn.api_key
        headers['Authorization'] = 'Bearer %s' % self._vm_get_token()
        return headers, params, None

    def _send_request(self, method, url, kwargs):
        if self.connector_type != 'vanmarcke':
            return super()._send_request(method, url, kwargs)
        refreshed = False
        for attempt in range(MAX_RETRIES + 1):
            self._vm_wait_rate_limit()
            response = super()._send_request(method, url, kwargs)
            if response.status_code == 401 and not refreshed:
                # Token expired or revoked: get a new one and retry once.
                refreshed = True
                kwargs['headers']['Authorization'] = \
                    'Bearer %s' % self._vm_get_token(force=True)
                continue
            if response.status_code == 429 and attempt < MAX_RETRIES:
                try:
                    delay = float(response.headers.get('Retry-After') or 0)
                except (TypeError, ValueError, AttributeError):
                    delay = 0
                time.sleep(min(delay or 2 ** attempt, 30))
                continue
            return response
        return response

    @staticmethod
    def _vm_wait_rate_limit():
        with _rate_lock:
            wait = _last_call['time'] + MIN_INTERVAL - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            _last_call['time'] = time.monotonic()

    def _vm_params(self, *names):
        """Query parameters of the Products / Stores API."""
        values = {'catalogCountry': self.vm_country or 'be',
                  'channel': self.vm_channel or 'b2b',
                  'language': self.vm_language or 'nl'}
        return {name: values[name] for name in names}

    # ------------------------------------------------------------------------
    # Fetching (Products - v2)
    # ------------------------------------------------------------------------
    def _vm_product_codes(self):
        """Van Marcke product numbers to fetch for the scopes "supplierinfo"
        and "codes", without duplicates, in order."""
        self.ensure_one()
        if self.vm_scope == 'codes':
            codes = re.split(r'[\s,;]+', self.vm_product_codes or '')
        else:
            infos = self.env['product.supplierinfo'].sudo().search([
                ('partner_id', 'child_of',
                 self.partner_id.commercial_partner_id.id),
                ('product_code', '!=', False),
                ('company_id', 'in', [False, self.company_id.id]),
            ])
            known = self.env['df.connects.supplier.product'].search([
                ('connection_id', '=', self.id),
                ('supplier_code', '!=', False),
            ])
            codes = infos.mapped('product_code') + \
                known.mapped('supplier_code')
        return list(dict.fromkeys(c.strip() for c in codes if c and c.strip()))

    def _vm_bulk(self, endpoint, codes, params):
        """POST /v2/products/bulk/<endpoint> for ``codes`` (at most 50);
        returns {product id: product}."""
        url = self._get_url('%s/bulk/%s' % (PRODUCTS_PATH, endpoint))
        query = '&'.join('%s=%s' % item for item in params.items())
        payload = self._request('%s?%s' % (url, query) if query else url,
                                body={'productIds': codes}, method='POST')
        products = payload.get('products') if isinstance(payload, dict) \
            else None
        return {to_text(p.get('productId')): p for p in products or []
                if isinstance(p, dict) and p.get('productId')}

    def _vm_store_stock(self, code, store):
        """GET /v2/products/{productId}/stock/{storeId}: {stockLevel,
        stockAvailable}, or None when Van Marcke does not know it."""
        url = self._get_url('%s/%s/stock/%s?catalogCountry=%s' % (
            PRODUCTS_PATH, code, store.code, self.vm_country or 'be'))
        try:
            return self._request(url, method='GET')
        except UserError as e:
            if ' 404 ' in str(e.args[0] if e.args else e):
                return None
            raise

    def _vm_chunks(self):
        """Chunks of {product id: product from the listing or {}}."""
        if self.vm_scope == 'catalog':
            chunk = {}
            for product in self._fetch_records_rest_json():
                code = to_text(product.get('productId')) \
                    if isinstance(product, dict) else False
                if not code:
                    continue
                chunk[code] = product
                if len(chunk) >= BULK_SIZE:
                    yield chunk
                    chunk = {}
            if chunk:
                yield chunk
            return
        codes = self._vm_product_codes()
        for start in range(0, len(codes), BULK_SIZE):
            yield {code: {} for code in codes[start:start + BULK_SIZE]}

    def _fetch_records_vanmarcke(self):
        """Product per product id, with its prices and stock, and the stock
        of the stores marked "Winkelvoorraad ophalen" in "vmStoreStock"."""
        self.ensure_one()
        stores = self.env['df.connects.supplier.entity'].search([
            ('connection_id', '=', self.id), ('vm_store_stock', '=', True),
            ('code', '!=', CENTRAL_ENTITY)])
        catalog = self.vm_scope == 'catalog'
        for chunk in self._vm_chunks():
            codes = list(chunk)
            if self.vm_fetch_details and not catalog:
                # One call for details, prices and stock.
                products = self._vm_bulk('detail', codes, dict(
                    self._vm_params('catalogCountry', 'channel', 'language'),
                    includePriceAndStock='true'))
            else:
                # The catalog listing already has the details.
                products = self._vm_bulk(
                    'pricesAndStock', codes,
                    self._vm_params('catalogCountry'))
            for code in codes:
                if code not in products and not chunk[code]:
                    # Unknown at Van Marcke: not returned, so archived.
                    continue
                product = dict(chunk[code])
                product.update(products.get(code, {}))
                product['productId'] = code
                product['vmStoreStock'] = [
                    (store, self._vm_store_stock(code, store))
                    for store in stores]
                yield product

    def _fetch_records_rest_json(self):
        if self.connector_type != 'vanmarcke':
            return super()._fetch_records_rest_json()
        return self._vm_fetch_listing()

    def _vm_fetch_listing(self):
        """Catalog listing GET /v2/products, page by page with limit /
        offset (the base pagination), with the catalog parameters."""
        params = self._vm_params('catalogCountry', 'channel', 'language')
        if self.vm_exclude_archived:
            params['excludeArchived'] = 'true'
        conn = self.with_context(df_connects_vm_listing_params=params)
        return super(DfConnectsConnection, conn)._fetch_records_rest_json()

    def _request(self, url, params=None, body=None, method=None):
        extra = self.env.context.get('df_connects_vm_listing_params')
        if self.connector_type == 'vanmarcke' and extra and method is None:
            params = dict(extra, **(params or {}))
        return super()._request(url, params=params, body=body, method=method)

    def _parse_record_vanmarcke(self, product):
        """Parse a product of the Products API v2: productId, EAN from
        supplierBarcode (or barcode), description in the language of the
        connection, net or list price, central stock (availability only)
        and store stock (stockLevel)."""
        ean = False
        for key in ('supplierBarcode', 'barcode'):
            ean = normalize_ean(product.get(key))
            if ean:
                break
        price, currency = self._vm_price(product.get('prices') or [])
        stock = []
        central = product.get('stock')
        if isinstance(central, dict) and 'stockAvailable' in central:
            # The central warehouse only tells whether there is stock.
            stock.append((CENTRAL_ENTITY, self.vm_central_name or False, 0.0,
                          bool(central.get('stockAvailable'))))
        for store, store_stock in product.get('vmStoreStock') or []:
            store_stock = store_stock if isinstance(store_stock, dict) else {}
            level = store_stock.get('stockLevel')
            qty = float(level) if isinstance(level, (int, float)) else 0.0
            available = store_stock.get('stockAvailable')
            stock.append((store.code, store.name, qty,
                          bool(available) if available is not None
                          else qty > 0))
        return {
            'ean': ean,
            'code': to_text(product.get('productId')),
            'name': self._vm_description(product.get('descriptions') or []),
            'price': price,
            'currency': currency,
            'stock': stock,
        }

    def _vm_price(self, prices):
        """(value, currency) of the configured price type, or of the other
        one when it is missing."""
        by_type = {p.get('priceType'): p for p in prices
                   if isinstance(p, dict) and p.get('value') is not None}
        wanted = self.vm_price_type or 'NET'
        other = 'LIST' if wanted == 'NET' else 'NET'
        price = by_type.get(wanted) or by_type.get(other)
        if not price:
            return 0.0, False
        return float(price['value']), to_text(price.get('currencyIso'))

    def _vm_description(self, descriptions):
        """Description in the language of the connection, preferring the
        short one."""
        language = self.vm_language or 'nl'
        candidates = [d for d in descriptions
                      if isinstance(d, dict) and d.get('value')]
        in_language = [d for d in candidates
                       if (d.get('languageCode') or '').lower() == language]
        for group in (in_language, candidates):
            if not group:
                continue
            short = [d for d in group
                     if 'short' in (d.get('type') or '').lower()]
            return to_text((short or group)[0]['value'])
        return False

    # ------------------------------------------------------------------------
    # Stores (Stores - v1)
    # ------------------------------------------------------------------------
    def action_vm_fetch_stores(self):
        """Create an entity per Van Marcke store, to choose the stores whose
        stock is fetched. GET /v1/stores pages with currentPage (from 0)
        and pageSize; the store id is "name", its label "displayName"."""
        self.ensure_one()
        if self.connector_type != 'vanmarcke':
            raise UserError(_('Enkel voor een koppeling met Van Marcke.'))
        Entity = self.env['df.connects.supplier.entity'].with_context(
            active_test=False)
        existing = {e.code: e for e in Entity.search(
            [('connection_id', '=', self.id)])}
        created = 0
        page = 0
        while True:
            payload = self._request(self._get_url(STORES_PATH), params=dict(
                self._vm_params('catalogCountry'),
                pageSize=STORES_PAGE_SIZE, currentPage=page), method='GET')
            stores = payload.get('stores') if isinstance(payload, dict) \
                else None
            for store in stores or []:
                code = to_text(store.get('name'))
                if not code:
                    continue
                name = to_text(store.get('displayName')) or code
                entity = existing.get(code)
                if entity:
                    if entity.name == entity.code:
                        entity.name = name
                else:
                    existing[code] = Entity.create({
                        'connection_id': self.id, 'code': code,
                        'name': name})
                    created += 1
            pagination = (payload.get('pagination') or {}) \
                if isinstance(payload, dict) else {}
            page += 1
            if not stores or page >= (pagination.get('totalPages') or 1) \
                    or page >= 100:
                break
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Winkels Van Marcke'),
                'message': _('%(created)s nieuwe winkel(s), %(total)s in '
                             'totaal. Vink "Winkelvoorraad ophalen" aan bij '
                             'de winkels waarvan je de voorraad wil.',
                             created=created, total=len(existing)),
                'type': 'success',
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }
