# -*- coding: utf-8 -*-
import json
import logging
from urllib.parse import urljoin

import requests
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models, modules
from odoo.exceptions import UserError, ValidationError

from .tools import get_path, normalize_ean, to_float, to_text

_logger = logging.getLogger(__name__)

# Code of the entity used when the supplier only gives one total quantity.
DEFAULT_ENTITY = 'default'


class DfConnectsConnection(models.Model):
    """API connection with an external supplier.

    The generic connector ("rest_json") reads any JSON REST API through the
    endpoint, pagination and field mapping set on the connection. A supplier
    specific connector adds a value to ``connector_type`` and implements
    ``_fetch_records_<type>`` (and, when the mapping is not enough,
    ``_parse_record_<type>``); see README.md."""
    _name = 'df.connects.connection'
    _inherit = ['mail.thread']
    _description = 'Leverancierskoppeling'
    _order = 'sequence, name'

    name = fields.Char(string='Naam', required=True, tracking=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True, tracking=True)
    partner_id = fields.Many2one(
        'res.partner', string='Leverancier', required=True, tracking=True,
        index=True, help='Supplier the products are fetched from.')
    company_id = fields.Many2one(
        'res.company', string='Bedrijf', required=True,
        default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one(
        'res.currency', string='Munt', required=True,
        default=lambda self: self.env.company.currency_id,
        help='Currency of the prices when the API does not give one.')
    connector_type = fields.Selection([
        ('rest_json', 'REST / JSON (generiek)'),
    ], string='Type koppeling', required=True, default='rest_json',
        tracking=True)

    # --- Request -----------------------------------------------------------
    base_url = fields.Char(
        string='Basis-URL', tracking=True,
        help='Root URL of the API, e.g. https://api.supplier.com/v1')
    products_endpoint = fields.Char(
        string='Endpoint producten', default='/products',
        help='Path of the product list, relative to the base URL (or a '
             'full URL).')
    http_method = fields.Selection(
        [('GET', 'GET'), ('POST', 'POST')], string='HTTP-methode',
        default='GET', required=True)
    request_body = fields.Text(
        string='Body (JSON)',
        help='JSON body sent with a POST request. The pagination parameters '
             'are added to it.')
    extra_params = fields.Text(
        string='Extra parameters (JSON)',
        help='Extra query parameters, as a JSON object, e.g. '
             '{"lang": "nl", "fields": "all"}')
    extra_headers = fields.Text(
        string='Extra headers (JSON)',
        help='Extra HTTP headers, as a JSON object, e.g. '
             '{"Accept-Language": "nl-BE"}')
    timeout = fields.Integer(string='Timeout (s)', default=30)
    verify_ssl = fields.Boolean(string='SSL-certificaat controleren',
                                default=True)

    # --- Authentication ------------------------------------------------------
    auth_type = fields.Selection([
        ('none', 'Geen'),
        ('api_key_header', 'API-sleutel in header'),
        ('api_key_query', 'API-sleutel als parameter'),
        ('bearer', 'Bearer-token'),
        ('basic', 'Gebruikersnaam en wachtwoord (basic)'),
    ], string='Authenticatie', required=True, default='api_key_header')
    api_key_name = fields.Char(
        string='Naam header / parameter', default='X-API-Key',
        help='Name of the header or query parameter holding the API key.')
    api_key = fields.Char(string='API-sleutel / token',
                          groups='df_connects.group_df_connects_manager')
    username = fields.Char(string='Gebruikersnaam',
                           groups='df_connects.group_df_connects_manager')
    password = fields.Char(string='Wachtwoord',
                           groups='df_connects.group_df_connects_manager')

    # --- Pagination ----------------------------------------------------------
    pagination = fields.Selection([
        ('none', 'Geen (alles in één antwoord)'),
        ('page', 'Paginanummer'),
        ('offset', 'Offset'),
        ('next_link', 'Link naar volgende pagina'),
    ], string='Paginering', required=True, default='none')
    page_param = fields.Char(string='Parameter pagina', default='page')
    page_start = fields.Integer(string='Eerste pagina', default=1)
    offset_param = fields.Char(string='Parameter offset', default='offset')
    page_size_param = fields.Char(string='Parameter paginagrootte',
                                  default='limit')
    page_size = fields.Integer(string='Paginagrootte', default=100)
    next_link_path = fields.Char(
        string='Pad volgende link', default='next',
        help='Path in the JSON response of the URL of the next page, e.g. '
             '"links.next". Empty or null: last page.')
    max_pages = fields.Integer(
        string='Maximum pagina\'s', default=1000,
        help='Safety limit on the number of pages read in one sync.')

    # --- Field mapping -------------------------------------------------------
    records_path = fields.Char(
        string='Pad productlijst', default='data',
        help='Path of the list of products in the JSON response, e.g. '
             '"data" or "result.items". Empty: the response itself is the '
             'list.')
    map_ean = fields.Char(string='Veld EAN', default='ean')
    map_code = fields.Char(string='Veld leveranciersproductcode',
                           default='sku', required=True)
    map_name = fields.Char(string='Veld omschrijving', default='name')
    map_price = fields.Char(string='Veld prijs', default='price')
    map_currency = fields.Char(
        string='Veld munt',
        help='Path of the ISO currency code (EUR, USD, ...). Empty: the '
             'currency of the connection.')
    map_quantity = fields.Char(
        string='Veld totale hoeveelheid', default='quantity',
        help='Path of one total available quantity. Used when no stock per '
             'entity is found.')
    map_stock_path = fields.Char(
        string='Pad voorraad per entiteit', default='stock',
        help='Path of the stock per entity: a list of objects '
             '([{"warehouse": "BE", "qty": 4}, ...]) or an object with one '
             'quantity per entity ({"BE": 4, "NL": 10}).')
    map_stock_entity = fields.Char(
        string='Veld code entiteit', default='warehouse',
        help='Field of the entity code in each element of the stock list.')
    map_stock_entity_name = fields.Char(
        string='Veld naam entiteit',
        help='Field of the entity name in each element of the stock list. '
             'Empty: the code is used as name.')
    map_stock_quantity = fields.Char(
        string='Veld hoeveelheid entiteit', default='quantity',
        help='Field of the available quantity in each element of the stock '
             'list.')

    # --- Options -------------------------------------------------------------
    link_products = fields.Boolean(
        string='Koppelen aan producten', default=True,
        help='Link supplier products to Odoo products with the same barcode '
             '(EAN) or with the supplier product code in the vendor '
             'pricelist.')
    update_supplierinfo = fields.Boolean(
        string='Leveranciersprijslijst bijwerken',
        help='Write the supplier product code and price into the vendor '
             'pricelist of linked products.')
    archive_missing = fields.Boolean(
        string='Ontbrekende producten archiveren', default=True,
        help='Archive supplier products the API no longer returns after a '
             'complete sync.')
    store_raw_data = fields.Boolean(
        string='Ruwe gegevens bewaren',
        help='Keep the JSON of each product as received, to check the '
             'mapping.')

    # --- Schedule ------------------------------------------------------------
    auto_sync = fields.Boolean(string='Automatisch synchroniseren',
                               tracking=True)
    sync_interval_number = fields.Integer(string='Elke', default=1)
    sync_interval_type = fields.Selection([
        ('hours', 'uur'), ('days', 'dagen'), ('weeks', 'weken'),
    ], string='Eenheid interval', default='days', required=True)
    next_sync = fields.Datetime(string='Volgende synchronisatie')
    last_sync = fields.Datetime(string='Laatste synchronisatie',
                                readonly=True)
    last_sync_state = fields.Selection(
        [('ok', 'Geslaagd'), ('error', 'Fout')],
        string='Resultaat laatste synchronisatie', readonly=True)
    last_sync_message = fields.Text(string='Melding', readonly=True)

    supplier_product_ids = fields.One2many(
        'df.connects.supplier.product', 'connection_id',
        string='Leveranciersproducten')
    supplier_product_count = fields.Integer(
        compute='_compute_counts', string='# producten')
    entity_ids = fields.One2many(
        'df.connects.supplier.entity', 'connection_id', string='Entiteiten')
    entity_count = fields.Integer(compute='_compute_counts',
                                  string='# entiteiten')
    log_ids = fields.One2many('df.connects.sync.log', 'connection_id',
                              string='Historiek')

    @api.depends('supplier_product_ids', 'entity_ids')
    def _compute_counts(self):
        product_data = self.env['df.connects.supplier.product']._read_group(
            [('connection_id', 'in', self.ids)], ['connection_id'],
            ['__count'])
        products = {conn.id: count for conn, count in product_data}
        entity_data = self.env['df.connects.supplier.entity']._read_group(
            [('connection_id', 'in', self.ids)], ['connection_id'],
            ['__count'])
        entities = {conn.id: count for conn, count in entity_data}
        for rec in self:
            rec.supplier_product_count = products.get(rec.id, 0)
            rec.entity_count = entities.get(rec.id, 0)

    @api.constrains('request_body', 'extra_params', 'extra_headers')
    def _check_json_fields(self):
        for rec in self:
            for fname in ('request_body', 'extra_params', 'extra_headers'):
                value = rec[fname]
                if not value or not value.strip():
                    continue
                try:
                    parsed = json.loads(value)
                except ValueError as e:
                    raise ValidationError(_(
                        '"%(field)s" is geen geldige JSON: %(error)s',
                        field=rec._fields[fname].string, error=e))
                if fname != 'request_body' and not isinstance(parsed, dict):
                    raise ValidationError(_(
                        '"%(field)s" moet een JSON-object zijn.',
                        field=rec._fields[fname].string))

    @api.constrains('page_size', 'max_pages', 'timeout',
                    'sync_interval_number')
    def _check_positive(self):
        for rec in self:
            if rec.page_size <= 0 or rec.max_pages <= 0 or rec.timeout <= 0:
                raise ValidationError(_(
                    'Paginagrootte, maximum pagina\'s en timeout moeten '
                    'groter dan 0 zijn.'))
            if rec.auto_sync and rec.sync_interval_number <= 0:
                raise ValidationError(_(
                    'Het interval van de synchronisatie moet groter dan 0 '
                    'zijn.'))

    # ------------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------------
    def action_test_connection(self):
        """Fetch the first page and report what was found, without storing
        anything."""
        self.ensure_one()
        records = []
        for raw in self._fetch_records():
            records.append(raw)
            if len(records) >= 5:
                break
        if not records:
            message = _('Verbinding geslaagd, maar er werden geen producten '
                        'gevonden. Controleer het pad van de productlijst.')
            kind = 'warning'
        else:
            parsed = [self._parse_record(raw) for raw in records]
            sample = parsed[0]
            message = _(
                'Verbinding geslaagd. Eerste product: code %(code)s, EAN '
                '%(ean)s, prijs %(price)s, hoeveelheid %(qty)s '
                '(%(entities)s entiteit(en)). Velden: %(keys)s',
                code=sample['code'] or '-', ean=sample['ean'] or '-',
                price=sample['price'],
                qty=sum(line[2] for line in sample['stock']),
                entities=len(sample['stock']),
                keys=', '.join(sorted(records[0])[:30])
                if isinstance(records[0], dict) else '-')
            kind = 'success'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Test %s', self.name),
                'message': message,
                'type': kind,
                'sticky': True,
            },
        }

    def action_sync(self):
        # Users may start a sync: it runs as superuser, as the cron does.
        self.check_access('read')
        for rec in self:
            rec.sudo()._sync_safe()
        if len(self) == 1:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Synchronisatie %s', self.name),
                    'message': self.last_sync_message,
                    'type': 'success' if self.last_sync_state == 'ok'
                    else 'danger',
                    'sticky': self.last_sync_state != 'ok',
                    'next': {'type': 'ir.actions.client',
                             'tag': 'soft_reload'},
                },
            }
        return True

    def action_view_supplier_products(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'df_connects.supplier_product_action')
        action['domain'] = [('connection_id', '=', self.id)]
        action['context'] = {'default_connection_id': self.id}
        return action

    def action_view_entities(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'df_connects.supplier_entity_action')
        action['domain'] = [('connection_id', '=', self.id)]
        action['context'] = {'default_connection_id': self.id}
        return action

    @api.model
    def _cron_sync(self):
        """Sync every connection with automatic sync that is due."""
        now = fields.Datetime.now()
        connections = self.search([
            ('auto_sync', '=', True),
            '|', ('next_sync', '=', False), ('next_sync', '<=', now),
        ])
        for index, connection in enumerate(connections, 1):
            connection._sync_safe()
            # Commit per connection so one slow or failing supplier does not
            # roll back the others (not in tests).
            if not modules.module.current_test:
                self.env['ir.cron']._commit_progress(
                    1, remaining=len(connections) - index)

    def _compute_next_sync(self, start):
        self.ensure_one()
        number = max(self.sync_interval_number, 1)
        return start + relativedelta(**{self.sync_interval_type: number})

    # ------------------------------------------------------------------------
    # Synchronisation
    # ------------------------------------------------------------------------
    def _sync_safe(self):
        """Sync and log the result; an error is logged on the connection
        instead of being raised, so the cron goes on with the next one."""
        self.ensure_one()
        start = fields.Datetime.now()
        try:
            with self.env.cr.savepoint():
                stats = self._sync()
        except Exception as e:  # noqa: BLE001 - logged for the user
            _logger.warning('DF Connects: sync of %s failed', self.name,
                            exc_info=True)
            message = str(e.args[0]) if isinstance(e, UserError) and e.args \
                else '%s: %s' % (type(e).__name__, e)
            self._log_sync(start, 'error', message)
            return False
        message = _(
            '%(read)s producten gelezen: %(created)s nieuw, %(updated)s '
            'bijgewerkt, %(archived)s gearchiveerd, %(skipped)s overgeslagen.',
            **stats)
        if stats.get('warnings'):
            message += '\n' + '\n'.join(stats['warnings'][:20])
        self._log_sync(start, 'ok', message, stats)
        return True

    def _log_sync(self, start, state, message, stats=None):
        stats = stats or {}
        vals = {'last_sync': start, 'last_sync_state': state,
                'last_sync_message': message}
        if self.auto_sync:
            vals['next_sync'] = self._compute_next_sync(start)
        self.write(vals)
        self.env['df.connects.sync.log'].create({
            'connection_id': self.id,
            'date': start,
            'duration': (fields.Datetime.now() - start).total_seconds(),
            'state': state,
            'message': message,
            'count_read': stats.get('read', 0),
            'count_created': stats.get('created', 0),
            'count_updated': stats.get('updated', 0),
            'count_archived': stats.get('archived', 0),
            'count_skipped': stats.get('skipped', 0),
        })

    def _sync(self):
        """Fetch all products of the supplier and store them. Returns the
        statistics of the run."""
        self.ensure_one()
        SupplierProduct = self.env['df.connects.supplier.product'] \
            .with_context(active_test=False)
        existing = {sp.uuid: sp for sp in SupplierProduct.search(
            [('connection_id', '=', self.id)])}
        entities = {e.code: e for e in self.env['df.connects.supplier.entity']
                    .with_context(active_test=False)
                    .search([('connection_id', '=', self.id)])}
        stats = {'read': 0, 'created': 0, 'updated': 0, 'archived': 0,
                 'skipped': 0, 'warnings': []}
        seen = set()
        now = fields.Datetime.now()
        currencies = {}
        for raw in self._fetch_records():
            stats['read'] += 1
            data = self._parse_record(raw)
            if not data['code'] and not data['ean']:
                stats['skipped'] += 1
                if len(stats['warnings']) < 20:
                    stats['warnings'].append(_(
                        'Product zonder code en EAN overgeslagen (#%s).',
                        stats['read']))
                continue
            uuid, uuid_source = self._make_uuid(data)
            if uuid in seen:
                stats['skipped'] += 1
                if len(stats['warnings']) < 20:
                    stats['warnings'].append(_(
                        'Dubbel product %s overgeslagen.', uuid))
                continue
            seen.add(uuid)
            vals = {
                'uuid': uuid,
                'uuid_source': uuid_source,
                'ean': data['ean'],
                'supplier_code': data['code'],
                'name': data['name'] or data['code'] or data['ean'],
                'price': data['price'],
                'currency_id': self._get_currency(
                    data['currency'], currencies).id,
                'last_seen': now,
                'active': True,
            }
            if self.store_raw_data:
                vals['raw_data'] = json.dumps(raw, indent=2, default=str,
                                              ensure_ascii=False)
            supplier_product = existing.get(uuid)
            if supplier_product:
                supplier_product.write(vals)
                stats['updated'] += 1
            else:
                vals['connection_id'] = self.id
                supplier_product = SupplierProduct.create(vals)
                existing[uuid] = supplier_product
                stats['created'] += 1
            supplier_product._set_stock(self._get_entities(
                data['stock'], entities))
            if self.link_products and not supplier_product.product_id:
                product = supplier_product._find_product()
                if product:
                    supplier_product.product_id = product
            if self.update_supplierinfo and supplier_product.product_id:
                supplier_product._update_supplierinfo()
        if self.archive_missing:
            missing = SupplierProduct.browse([
                sp.id for uuid, sp in existing.items()
                if uuid not in seen and sp.active])
            if missing:
                missing.write({'active': False})
                missing.stock_ids.write({'quantity': 0.0,
                                         'available': False})
                stats['archived'] = len(missing)
        return stats

    def _make_uuid(self, data):
        """UUID of a supplier product: its EAN when it has a valid one,
        otherwise its supplier product code, prefixed with the supplier so it
        cannot collide with an EAN or a code of another supplier."""
        if data['ean']:
            return data['ean'], 'ean'
        return 'S%s-%s' % (self.partner_id.id, data['code']), 'code'

    def _get_currency(self, code, cache):
        if not code:
            return self.currency_id
        code = code.upper()
        if code not in cache:
            cache[code] = self.env['res.currency'].with_context(
                active_test=False).search([('name', '=', code)], limit=1) \
                or self.currency_id
        return cache[code]

    def _get_entities(self, stock, entities):
        """Map the parsed stock [(code, name, qty[, available])] on entity
        records, creating new entities. Returns {entity: (qty, available)};
        ``available`` is None when the supplier only gives a quantity."""
        result = {}
        Entity = self.env['df.connects.supplier.entity']
        for line in stock:
            code, name, qty = line[:3]
            available = line[3] if len(line) > 3 else None
            entity = entities.get(code)
            if not entity:
                entity = Entity.create({
                    'connection_id': self.id,
                    'code': code,
                    'name': name or (self.partner_id.name
                                     if code == DEFAULT_ENTITY else code),
                })
                entities[code] = entity
            elif name and entity.name == entity.code and name != code:
                entity.name = name
            old_qty, old_available = result.get(entity, (0.0, None))
            if available is None:
                available = old_available
            elif old_available:
                available = True
            result[entity] = (old_qty + qty, available)
        return result

    # ------------------------------------------------------------------------
    # Fetching
    # ------------------------------------------------------------------------
    def _fetch_records(self):
        """Generator of the raw product records of the supplier, dispatched
        on the connector type."""
        self.ensure_one()
        method = getattr(self, '_fetch_records_%s' % self.connector_type,
                         None)
        if not method:
            raise UserError(_('Type koppeling %s wordt niet ondersteund.',
                              self.connector_type))
        return method()

    def _parse_record(self, raw):
        """Parsed product: {'ean', 'code', 'name', 'price', 'currency',
        'stock': [(entity code, entity name, quantity[, available])]}.
        ``available`` (optional) is for suppliers that tell whether an entity
        has stock without giving the quantity; without it, available means
        quantity > 0."""
        self.ensure_one()
        method = getattr(self, '_parse_record_%s' % self.connector_type,
                         self._parse_record_mapping)
        return method(raw)

    def _get_url(self, path):
        self.ensure_one()
        path = (path or '').strip()
        if path.startswith(('http://', 'https://')):
            return path
        if not self.base_url:
            raise UserError(_('Vul de basis-URL van de koppeling in.'))
        return self.base_url.strip().rstrip('/') + '/' + path.lstrip('/')

    def _get_request_auth(self):
        """Headers, query parameters and requests auth for the
        authentication of the connection."""
        self.ensure_one()
        conn = self.sudo()
        headers = {'Accept': 'application/json'}
        if self.extra_headers and self.extra_headers.strip():
            headers.update(json.loads(self.extra_headers))
        params = {}
        if self.extra_params and self.extra_params.strip():
            params.update(json.loads(self.extra_params))
        auth = None
        if self.auth_type in ('api_key_header', 'api_key_query', 'bearer') \
                and not conn.api_key:
            raise UserError(_('Vul de API-sleutel van de koppeling in.'))
        if self.auth_type == 'api_key_header':
            headers[self.api_key_name or 'X-API-Key'] = conn.api_key
        elif self.auth_type == 'api_key_query':
            params[self.api_key_name or 'api_key'] = conn.api_key
        elif self.auth_type == 'bearer':
            headers['Authorization'] = 'Bearer %s' % conn.api_key
        elif self.auth_type == 'basic':
            auth = (conn.username or '', conn.password or '')
        return headers, params, auth

    def _request(self, url, params=None, body=None, method=None):
        """Do one request and return the decoded JSON. ``method`` defaults
        to the HTTP method of the connection; with POST, ``body`` and
        ``params`` go into the JSON body together with the configured
        body."""
        self.ensure_one()
        method = method or self.http_method
        headers, auth_params, auth = self._get_request_auth()
        kwargs = {
            'headers': headers, 'auth': auth, 'timeout': self.timeout,
            'verify': self.verify_ssl,
        }
        if method == 'POST':
            # Authentication parameters stay in the URL, the rest goes in the
            # body together with the configured body.
            kwargs['params'] = auth_params
            payload = json.loads(self.request_body) \
                if self.request_body and self.request_body.strip() else {}
            if isinstance(payload, dict):
                payload.update(params or {})
                payload.update(body or {})
            kwargs['json'] = payload
        else:
            kwargs['params'] = dict(auth_params, **(params or {}))
        try:
            response = self._send_request(method, url, kwargs)
        except requests.exceptions.RequestException as e:
            raise UserError(_('Geen verbinding met %(url)s: %(error)s',
                              url=url, error=e))
        if response.status_code >= 400:
            raise UserError(_(
                'De leverancier antwoordde met fout %(status)s op %(url)s: '
                '%(body)s', status=response.status_code, url=url,
                body=(response.text or '')[:500]))
        try:
            return response.json()
        except ValueError:
            raise UserError(_('Het antwoord van %s is geen geldige JSON.',
                              url))

    def _send_request(self, method, url, kwargs):
        """Send the HTTP request; hook for connectors that need to retry
        (expired token, rate limit)."""
        return requests.request(method, url, **kwargs)

    def _extract_records(self, payload):
        records = get_path(payload, self.records_path) \
            if self.records_path else payload
        if records is None:
            return []
        if isinstance(records, dict):
            # A single product, or an object keyed by product code.
            if all(isinstance(v, dict) for v in records.values()) \
                    and records and self.map_code not in records:
                return list(records.values())
            return [records]
        if not isinstance(records, list):
            raise UserError(_(
                'Op pad "%s" staat geen lijst van producten.',
                self.records_path or ''))
        return records

    def _fetch_records_rest_json(self):
        """Read the products page by page with the configured pagination."""
        url = self._get_url(self.products_endpoint)
        size_params = {self.page_size_param: self.page_size} \
            if self.page_size_param and self.pagination != 'none' else {}
        page = self.page_start
        offset = 0
        for _page_number in range(self.max_pages):
            params = dict(size_params)
            if self.pagination == 'page':
                params[self.page_param or 'page'] = page
            elif self.pagination == 'offset':
                params[self.offset_param or 'offset'] = offset
            payload = self._request(url, params=params)
            records = self._extract_records(payload)
            yield from records
            if self.pagination == 'none':
                return
            if self.pagination == 'next_link':
                next_url = get_path(payload, self.next_link_path) \
                    if isinstance(payload, dict) else None
                if not next_url or not isinstance(next_url, str) \
                        or not records:
                    return
                # The next link already holds the paging; keep only the page
                # size when the link does not give it.
                url = urljoin(url, next_url)
                size_params = {} if '?' in next_url else size_params
                continue
            if not records or len(records) < self.page_size:
                return
            page += 1
            offset += len(records)
        _logger.warning('DF Connects: %s stopped after %s pages', self.name,
                        self.max_pages)

    def _parse_record_mapping(self, raw):
        """Parse a record with the field mapping of the connection."""
        ean = normalize_ean(get_path(raw, self.map_ean)) \
            if self.map_ean else False
        code = to_text(get_path(raw, self.map_code)) \
            if self.map_code else False
        name = to_text(get_path(raw, self.map_name)) \
            if self.map_name else False
        price = to_float(get_path(raw, self.map_price)) \
            if self.map_price else 0.0
        currency = to_text(get_path(raw, self.map_currency)) \
            if self.map_currency else False
        return {
            'ean': ean,
            'code': code,
            'name': name,
            'price': price,
            'currency': currency,
            'stock': self._parse_stock(raw),
        }

    def _parse_stock(self, raw):
        """Stock per entity as [(code, name, qty)]."""
        stock = get_path(raw, self.map_stock_path) \
            if self.map_stock_path else None
        result = []
        if isinstance(stock, dict):
            for code, value in stock.items():
                if isinstance(value, dict):
                    qty = to_float(get_path(value, self.map_stock_quantity))
                    name = to_text(get_path(value, self.map_stock_entity_name)) \
                        if self.map_stock_entity_name else False
                else:
                    qty, name = to_float(value), False
                result.append((str(code), name, qty))
        elif isinstance(stock, list):
            for line in stock:
                if not isinstance(line, dict):
                    continue
                code = to_text(get_path(line, self.map_stock_entity)) \
                    or DEFAULT_ENTITY
                name = to_text(get_path(line, self.map_stock_entity_name)) \
                    if self.map_stock_entity_name else False
                qty = to_float(get_path(line, self.map_stock_quantity))
                result.append((code, name, qty))
        if not result and self.map_quantity:
            qty = get_path(raw, self.map_quantity)
            if qty is not None:
                result.append((DEFAULT_ENTITY, False, to_float(qty)))
        return result
