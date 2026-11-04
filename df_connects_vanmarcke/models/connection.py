# -*- coding: utf-8 -*-
import logging
import re
import threading
import time
from datetime import timedelta

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.df_connects.models.tools import get_path, to_float, to_text

_logger = logging.getLogger(__name__)

API_URLS = {
    'production': 'https://api.vanmarcke.com',
    'test': 'https://api-test.vanmarcke.com',
}
PRODUCTS_PATH = '/v2/products'
STORES_PATH = '/v1/stores'
TOKEN_PATH = '/v1/oauth/token'
# Van Marcke allows 1 call every 20 ms (API Security Policies).
MIN_INTERVAL = 0.02
MAX_RETRIES = 3
CENTRAL_ENTITY = 'central'

_rate_lock = threading.Lock()
_last_call = {'time': 0.0}

# Defaults written on the connection when its type is set to Van Marcke.
# Paths with "|" try several field names: the response schemas are only
# published in the developer portal, check them with "Ruwe gegevens
# bewaren" and adjust where needed.
VANMARCKE_DEFAULTS = {
    'products_endpoint': PRODUCTS_PATH,
    'auth_type': 'none',
    'http_method': 'GET',
    'pagination': 'page',
    'page_param': 'page',
    'page_start': 0,
    'page_size_param': 'pageSize',
    'page_size': 50,
    'records_path': False,
    'extra_params': '{"country": "BE", "language": "nl"}',
    'map_code': 'productId|id',
    'map_ean': 'supplierBarcode|ean|gtin|barcode|eanCode',
    'map_name': 'descriptionShort|descriptionShortNl|commercialDescription|'
                'description|name',
    'map_price': 'netPrice|price.netPrice|prices.netPrice|netPrice.value|'
                 'price.value|price',
    'map_currency': 'currency|currencyIso|price.currency|netPrice.currency',
    'map_quantity': False,
    'map_stock_path': 'dfStock',
    'map_stock_entity': 'entity',
    'map_stock_entity_name': 'name',
    'map_stock_quantity': 'quantity',
}


def _number_or_none(value):
    """Quantity from a JSON value: numbers and numeric strings only."""
    if value is None or isinstance(value, (dict, list, bool)):
        return None
    return to_float(value, None)


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
        help='Call /bulk/detail for the EAN and description, besides '
             '/bulk/pricesAndStock for price and stock.')
    vm_bulk_size = fields.Integer(string='Producten per bulkoproep',
                                  default=50)
    vm_ids_key = fields.Char(
        string='Sleutel productnummers in body', default='productIds',
        help='Key of the list of product numbers in the body of the bulk '
             'calls.')
    vm_records_path = fields.Char(
        string='Pad lijst in bulkantwoord',
        help='Path of the list of products in the bulk responses. Empty: '
             'the response itself, or the first list in it.')
    vm_map_product_id = fields.Char(
        string='Veld productnummer in antwoord', default='productId|id')
    vm_map_central_stock = fields.Char(
        string='Veld voorraad centraal magazijn',
        default='stock.quantity|stock.availableQuantity|stockQuantity|'
                'availableQuantity|centralStock|stock')
    vm_central_name = fields.Char(string='Naam centraal magazijn',
                                  default='Centraal magazijn')
    vm_map_store_stock = fields.Char(
        string='Veld voorraad winkel',
        default='quantity|availableQuantity|stock.quantity|stockQuantity|'
                'stock')
    vm_map_store_id = fields.Char(string='Veld winkelnummer',
                                  default='storeId|id|code')
    vm_map_store_name = fields.Char(string='Veld winkelnaam',
                                    default='name|displayName|description')

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
        if 'vm_environment' in vals or 'vm_grant_type' in vals \
                or 'vm_client_id' in vals or 'username' in vals:
            # Other credentials: the cached token no longer applies.
            vals = dict(vals, vm_access_token=False, vm_refresh_token=False,
                        vm_token_expires=False)
        return super().write(vals)

    # ------------------------------------------------------------------------
    # Authentication
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
                except (TypeError, ValueError):
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

    # ------------------------------------------------------------------------
    # Fetching
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

    def _vm_extract_list(self, payload, path=None):
        """List of records in a response: at ``path``, the response itself,
        or the first list of objects in it."""
        path = path if path is not None else self.vm_records_path
        if path:
            payload = get_path(payload, path)
        if isinstance(payload, list):
            return [r for r in payload if isinstance(r, dict)]
        if isinstance(payload, dict):
            for value in payload.values():
                if isinstance(value, list) and value \
                        and isinstance(value[0], dict):
                    return value
            return [payload]
        return []

    def _vm_bulk(self, endpoint, codes):
        """POST a bulk endpoint for ``codes``; returns {code: record}."""
        payload = self._request(
            self._get_url('%s/bulk/%s' % (PRODUCTS_PATH, endpoint)),
            body={self.vm_ids_key or 'productIds': codes}, method='POST')
        result = {}
        for record in self._vm_extract_list(payload):
            code = to_text(get_path(record, self.vm_map_product_id))
            if code:
                result[code] = record
        return result

    def _vm_store_stock(self, code, store):
        try:
            payload = self._request(self._get_url('%s/%s/stock/%s' % (
                PRODUCTS_PATH, code, store.code)), method='GET')
        except UserError as e:
            if '404' in str(e.args[0] if e.args else e):
                return 0.0
            raise
        record = self._vm_extract_list(payload)[:1]
        qty = _number_or_none(get_path(record[0], self.vm_map_store_stock)) \
            if record else None
        return qty or 0.0

    def _vm_listing_chunks(self):
        """Chunks of {code: listing record}: from the catalog listing, or
        from the product numbers of the scope."""
        size = max(1, min(self.vm_bulk_size or 50, 50))
        if self.vm_scope == 'catalog':
            chunk = {}
            for record in self._fetch_records_rest_json():
                code = to_text(get_path(record, self.vm_map_product_id))
                if not code:
                    continue
                chunk[code] = record
                if len(chunk) >= size:
                    yield chunk
                    chunk = {}
            if chunk:
                yield chunk
            return
        codes = self._vm_product_codes()
        for start in range(0, len(codes), size):
            yield {code: {} for code in codes[start:start + size]}

    def _fetch_records_vanmarcke(self):
        """Merged record per product: listing, details and prices and stock,
        with the stock per entity in "dfStock" (central warehouse and the
        stores with "Winkelvoorraad ophalen")."""
        self.ensure_one()
        stores = self.env['df.connects.supplier.entity'].search([
            ('connection_id', '=', self.id), ('vm_store_stock', '=', True),
            ('code', '!=', CENTRAL_ENTITY)])
        for chunk in self._vm_listing_chunks():
            codes = list(chunk)
            details = self._vm_bulk('detail', codes) \
                if self.vm_fetch_details else {}
            prices = self._vm_bulk('pricesAndStock', codes)
            for code in codes:
                if code not in details and code not in prices \
                        and not chunk[code]:
                    # Unknown at Van Marcke: not returned, so archived.
                    continue
                record = dict(chunk[code])
                record.update(details.get(code, {}))
                price_stock = prices.get(code, {})
                record.update(price_stock)
                record.setdefault('productId', code)
                stock = []
                central = _number_or_none(
                    get_path(price_stock, self.vm_map_central_stock))
                if central is not None:
                    stock.append({'entity': CENTRAL_ENTITY,
                                  'name': self.vm_central_name or False,
                                  'quantity': central})
                for store in stores:
                    stock.append({'entity': store.code, 'name': store.name,
                                  'quantity': self._vm_store_stock(
                                      code, store)})
                record['dfStock'] = stock
                yield record

    # ------------------------------------------------------------------------
    # Stores
    # ------------------------------------------------------------------------
    def action_vm_fetch_stores(self):
        """Create an entity per Van Marcke store (Stores API), to choose the
        stores whose stock is fetched."""
        self.ensure_one()
        if self.connector_type != 'vanmarcke':
            raise UserError(_('Enkel voor een koppeling met Van Marcke.'))
        payload = self._request(self._get_url(STORES_PATH), method='GET')
        Entity = self.env['df.connects.supplier.entity'].with_context(
            active_test=False)
        existing = {e.code: e for e in Entity.search(
            [('connection_id', '=', self.id)])}
        created = 0
        for record in self._vm_extract_list(payload, path=''):
            code = to_text(get_path(record, self.vm_map_store_id))
            if not code:
                continue
            name = to_text(get_path(record, self.vm_map_store_name)) or code
            entity = existing.get(code)
            if entity:
                if entity.name in (entity.code, False):
                    entity.name = name
            else:
                existing[code] = Entity.create({
                    'connection_id': self.id, 'code': code, 'name': name})
                created += 1
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

