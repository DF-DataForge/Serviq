# -*- coding: utf-8 -*-
from datetime import timedelta
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import HttpCase, TransactionCase, tagged

from odoo.addons.df_connects.tests.common import FakeResponse

MODULE = 'odoo.addons.df_connects_vanmarcke.models'
TOKEN = MODULE + '.connection.requests.post'
SERVICE = MODULE + '.service_user.requests.request'
API = 'https://api.vanmarcke.com'
SERVICE_USER = {'serviceUser': {
    'userName': 'API-DEMO-V96925', 'password': 'uupzfXdUg}4y',
    'firstName': 'API_USER', 'company': 'V96925', 'active': 'true',
    'id': 'P018846'}}


class TestServiceUser(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().set_param(
            'web.base.url', 'https://platsr.be')
        cls.connection = cls.env['df.connects.connection'].create({
            'name': 'Van Marcke',
            'partner_id': cls.env['res.partner'].create(
                {'name': 'Van Marcke'}).id,
            'connector_type': 'vanmarcke',
            'vm_grant_type': 'client_credentials',
            'vm_client_id': 'client',
            'vm_client_secret': 'secret',
            'api_key': 'app-key',
        })

    def setUp(self):
        super().setUp()
        self.token_calls = []
        self.service_calls = []
        self.service_answers = []
        for target, fake in ((TOKEN, self._fake_token),
                             (SERVICE, self._fake_service)):
            patcher = patch(target, side_effect=fake)
            patcher.start()
            self.addCleanup(patcher.stop)

    def _fake_token(self, url, data=None, auth=None, **kwargs):
        self.token_calls.append((url, data, auth))
        # The OAuth spec names the token "accessToken".
        return FakeResponse({'accessToken': 'user-token', 'expires_in': 60})

    def _fake_service(self, method, url, headers=None, **kwargs):
        self.service_calls.append((method, url, headers))
        return self.service_answers.pop(0)

    def _start(self, mode='create'):
        action = self.connection.action_vm_create_service_user() \
            if mode == 'create' else \
            self.connection.action_vm_reset_service_user()
        split = urlsplit(action['url'])
        self.assertEqual(split.scheme + '://' + split.netloc + split.path,
                         API + '/v1/oauth/authorize')
        return parse_qs(split.query)

    def test_redirect_uri(self):
        self.assertEqual(
            self.connection.vm_redirect_uri_used,
            'https://platsr.be/df_connects_vanmarcke/oauth/callback')
        self.connection.vm_redirect_uri = \
            'https://staging.platsr.be/df_connects_vanmarcke/oauth/callback'
        query = self._start()
        self.assertEqual(query['redirect_uri'],
                         [self.connection.vm_redirect_uri])

    def test_create(self):
        query = self._start()
        self.assertEqual(query['response_type'], ['code'])
        self.assertEqual(query['client_id'], ['client'])
        state = query['state'][0]
        Connection = self.env['df.connects.connection']
        self.assertEqual(Connection._vm_find_oauth_connection(state),
                         self.connection)
        self.assertFalse(Connection._vm_find_oauth_connection('wrong'))

        self.service_answers = [FakeResponse(SERVICE_USER)]
        self.connection._vm_oauth_callback('the-code')
        url, data, auth = self.token_calls[0]
        self.assertEqual(data, {
            'grant_type': 'authorization_code', 'code': 'the-code',
            'redirect_uri':
                'https://platsr.be/df_connects_vanmarcke/oauth/callback'})
        self.assertEqual(auth, ('client', 'secret'))
        method, url, headers = self.service_calls[0]
        self.assertEqual((method, url), ('POST', API + '/v1/serviceusers'))
        self.assertEqual(headers['Authorization'], 'Bearer user-token')
        self.assertEqual(headers['x-api-key'], 'app-key')
        conn = self.connection.sudo()
        self.assertEqual((conn.username, conn.password, conn.vm_grant_type),
                         ('API-DEMO-V96925', 'uupzfXdUg}4y', 'password'))
        self.assertEqual(conn.vm_service_user_company, 'V96925')
        self.assertFalse(conn.vm_access_token, 'user token not kept')
        # The state can only be used once.
        self.assertFalse(Connection._vm_find_oauth_connection(state))
        self.assertNotIn('uupzfXdUg', self.connection.message_ids[0].body)

    def test_create_existing(self):
        self._start()
        self.service_answers = [FakeResponse(
            {'errors': [{'code': 'conflict'}]}, status=403)]
        with self.assertRaisesRegex(UserError, 'bestaat al'):
            self.connection._vm_oauth_callback('the-code')

    def test_reset(self):
        self._start('reset')
        self.service_answers = [
            FakeResponse({'serviceUser': dict(SERVICE_USER['serviceUser'],
                                              password=None)}),
            FakeResponse(dict(SERVICE_USER, serviceUser=dict(
                SERVICE_USER['serviceUser'], password='new-pw'))),
        ]
        self.connection._vm_oauth_callback('the-code')
        self.assertEqual(
            [(m, u) for m, u, _h in self.service_calls],
            [('GET', API + '/v1/serviceusers'),
             ('POST', API + '/v1/serviceusers/P018846/resetpassword')])
        self.assertEqual(self.connection.sudo().password, 'new-pw')

    def test_state_expires(self):
        state = self._start()['state'][0]
        self.connection.sudo().vm_oauth_started = \
            fields.Datetime.now() - timedelta(hours=1)
        self.assertFalse(self.env['df.connects.connection']
                         ._vm_find_oauth_connection(state))

    def test_needs_credentials(self):
        self.connection.vm_client_secret = False
        with self.assertRaises(UserError):
            self.connection.action_vm_create_service_user()


@tagged('post_install', '-at_install')
class TestServiceUserCallback(HttpCase):

    def test_callback_route(self):
        connection = self.env['df.connects.connection'].create({
            'name': 'Van Marcke',
            'partner_id': self.env['res.partner'].create(
                {'name': 'Van Marcke'}).id,
            'connector_type': 'vanmarcke',
            'vm_client_id': 'client', 'vm_client_secret': 'secret',
            'api_key': 'app-key',
        })
        self.authenticate('admin', 'admin')
        response = self.url_open(
            '/df_connects_vanmarcke/oauth/callback?code=x&state=wrong',
            allow_redirects=False)
        self.assertEqual(response.status_code, 400)

        state = parse_qs(urlsplit(connection.with_user(
            self.env.ref('base.user_admin')).action_vm_create_service_user()[
            'url']).query)['state'][0]
        with patch(TOKEN, return_value=FakeResponse(
                {'access_token': 'user-token'})), \
                patch(SERVICE, return_value=FakeResponse(SERVICE_USER)):
            response = self.url_open(
                '/df_connects_vanmarcke/oauth/callback?code=c&state=%s'
                % state, allow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertTrue(response.headers['Location'].endswith(
            '/odoo/action-df_connects.connection_action/%s' % connection.id))
        self.assertEqual(connection.sudo().username, 'API-DEMO-V96925')
