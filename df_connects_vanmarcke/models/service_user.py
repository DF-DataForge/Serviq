# -*- coding: utf-8 -*-
"""Creation of the Van Marcke service user (Service Users - v1).

A user of the customer logs in once on the Van Marcke login page (OAuth
Authorization Code flow); Van Marcke sends the browser back to
/df_connects_vanmarcke/oauth/callback with a code. That code is exchanged for
a token of that user, which is only used to create the service user (or
reset its password) for the same customer number. The service user's
credentials are stored on the connection; the personal login and token are
not kept."""
import secrets
from datetime import timedelta
from urllib.parse import urlencode

import requests

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

CALLBACK_PATH = '/df_connects_vanmarcke/oauth/callback'
AUTHORIZE_PATH = '/v1/oauth/authorize'
SERVICE_USERS_PATH = '/v1/serviceusers'
# Time the user has to log in at Van Marcke.
STATE_VALIDITY = timedelta(minutes=15)


class DfConnectsConnection(models.Model):
    _inherit = 'df.connects.connection'

    vm_redirect_uri = fields.Char(
        string='Redirect URL',
        help='Redirect / callback URL registered at Van Marcke for this '
             'application. Empty: <web.base.url>' + CALLBACK_PATH + '. It '
             'must match the registered URL exactly.')
    vm_redirect_uri_used = fields.Char(
        string='Redirect URL (gebruikt)',
        compute='_compute_vm_redirect_uri_used')
    vm_service_user_id = fields.Char(string='ID service user', readonly=True,
                                     copy=False)
    vm_service_user_company = fields.Char(string='Klantnummer service user',
                                          readonly=True, copy=False)
    vm_oauth_state = fields.Char(groups='base.group_system', copy=False)
    vm_oauth_mode = fields.Selection(
        [('create', 'Aanmaken'), ('reset', 'Wachtwoord vernieuwen')],
        groups='base.group_system', copy=False)
    vm_oauth_started = fields.Datetime(groups='base.group_system',
                                       copy=False)

    @api.depends('vm_redirect_uri')
    def _compute_vm_redirect_uri_used(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url', '').rstrip('/')
        for rec in self:
            rec.vm_redirect_uri_used = rec.vm_redirect_uri \
                or base_url + CALLBACK_PATH

    # ------------------------------------------------------------------------
    # Step 1: send the user to the Van Marcke login
    # ------------------------------------------------------------------------
    def action_vm_create_service_user(self):
        return self._vm_start_service_user_login('create')

    def action_vm_reset_service_user(self):
        return self._vm_start_service_user_login('reset')

    def _vm_start_service_user_login(self, mode):
        self.ensure_one()
        if not self.env.user.has_group(
                'df_connects.group_df_connects_manager'):
            raise AccessError(_('Enkel een beheerder van de '
                                'leverancierskoppelingen kan dit.'))
        if self.connector_type != 'vanmarcke':
            raise UserError(_('Enkel voor een koppeling met Van Marcke.'))
        conn = self.sudo()
        if not conn.vm_client_id or not conn.vm_client_secret \
                or not conn.api_key:
            raise UserError(_(
                'Vul eerst de client ID, het client secret en de '
                'Application Key van Van Marcke in en sla de koppeling op.'))
        state = '%s-%s' % (self.id, secrets.token_urlsafe(24))
        conn.write({'vm_oauth_state': state, 'vm_oauth_mode': mode,
                    'vm_oauth_started': fields.Datetime.now()})
        query = urlencode({
            'response_type': 'code',
            'client_id': conn.vm_client_id,
            'redirect_uri': self.vm_redirect_uri_used,
            'state': state,
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '%s?%s' % (self._vm_api_url(AUTHORIZE_PATH), query),
            'target': 'self',
        }

    # ------------------------------------------------------------------------
    # Step 2: back from Van Marcke (called by the controller)
    # ------------------------------------------------------------------------
    @api.model
    def _vm_find_oauth_connection(self, state):
        """Connection that started the login with ``state``, still valid."""
        if not state:
            return self.browse()
        conn = self.sudo().search([('vm_oauth_state', '=', state)], limit=1)
        if not conn or not conn.vm_oauth_started or \
                conn.vm_oauth_started + STATE_VALIDITY < fields.Datetime.now():
            return self.browse()
        return conn

    def _vm_oauth_callback(self, code):
        """Exchange ``code`` for a token of the logged in user and create
        the service user (or reset its password). Returns a message for the
        chatter; raises UserError when it fails."""
        self.ensure_one()
        conn = self.sudo()
        mode = conn.vm_oauth_mode or 'create'
        # One use only.
        conn.write({'vm_oauth_state': False, 'vm_oauth_started': False})
        token_data = conn._vm_token_request({
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': self.vm_redirect_uri_used,
        })
        user_token = token_data['access_token']
        if mode == 'create':
            response = conn._vm_service_user_call('POST', '', user_token)
            if response.status_code in (403, 409):
                raise UserError(_(
                    'Er bestaat al een service user voor dit klantnummer en '
                    'deze applicatie. Gebruik "Wachtwoord service user '
                    'vernieuwen" om een nieuw wachtwoord te krijgen.'))
        else:
            response = conn._vm_service_user_call('GET', '', user_token)
            user_id = conn._vm_service_user_data(response).get('id')
            if not user_id:
                raise UserError(_('Van Marcke gaf geen service user terug '
                                  'voor dit klantnummer.'))
            response = conn._vm_service_user_call(
                'POST', '/%s/resetpassword' % user_id, user_token)
        service_user = conn._vm_service_user_data(response)
        if not service_user.get('userName') or \
                not service_user.get('password'):
            raise UserError(_('Van Marcke gaf geen gebruikersnaam en '
                              'wachtwoord van de service user terug.'))
        conn.write({
            'vm_grant_type': 'password',
            'username': service_user['userName'],
            'password': service_user['password'],
            'vm_service_user_id': service_user.get('id') or False,
            'vm_service_user_company': service_user.get('company') or False,
        })
        message = _(
            'Service user %(user)s %(action)s voor klantnummer %(company)s. '
            'Gebruikersnaam en wachtwoord zijn op de koppeling bewaard; Van '
            'Marcke stuurt ze ook per mail naar wie aanmeldde.',
            user=service_user['userName'],
            action=_('aangemaakt') if mode == 'create'
            else _('kreeg een nieuw wachtwoord'),
            company=service_user.get('company') or '-')
        self.message_post(body=message)
        return message

    def _vm_service_user_call(self, method, path, user_token):
        self._vm_wait_rate_limit()
        url = self._vm_api_url(SERVICE_USERS_PATH + path)
        try:
            response = requests.request(method, url, headers={
                'Accept': 'application/json',
                'x-api-key': self.api_key,
                'Authorization': 'Bearer %s' % user_token,
            }, timeout=self.timeout, verify=self.verify_ssl)
        except requests.exceptions.RequestException as e:
            raise UserError(_('Geen verbinding met %(url)s: %(error)s',
                              url=url, error=e))
        if response.status_code >= 400 and response.status_code not in (
                403, 409):
            raise UserError(_(
                'Van Marcke antwoordde met fout %(status)s op %(url)s: '
                '%(body)s', status=response.status_code, url=url,
                body=(response.text or '')[:500]))
        return response

    @staticmethod
    def _vm_service_user_data(response):
        if response.status_code >= 400:
            raise UserError(_(
                'Van Marcke antwoordde met fout %(status)s: %(body)s',
                status=response.status_code,
                body=(response.text or '')[:500]))
        try:
            payload = response.json()
        except ValueError:
            return {}
        service_user = payload.get('serviceUser') \
            if isinstance(payload, dict) else None
        return service_user if isinstance(service_user, dict) else {}
