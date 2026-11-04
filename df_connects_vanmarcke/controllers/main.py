# -*- coding: utf-8 -*-
import logging

from odoo import _, http
from odoo.exceptions import UserError
from odoo.http import request

from ..models.service_user import CALLBACK_PATH

_logger = logging.getLogger(__name__)


class VanMarckeOAuth(http.Controller):

    @http.route(CALLBACK_PATH, type='http', auth='user', methods=['GET'])
    def vanmarcke_oauth_callback(self, code=None, state=None, error=None,
                                 error_description=None, **kwargs):
        """Van Marcke sends the browser back here after the login started
        by "Service user aanmaken" on a connection."""
        Connection = request.env['df.connects.connection']
        connection = Connection._vm_find_oauth_connection(state)
        if not connection:
            return request.make_response(
                _('Ongeldige of verlopen aanmelding. Start opnieuw vanaf de '
                  'koppeling.'), status=400)
        if not request.env.user.has_group(
                'df_connects.group_df_connects_manager'):
            return request.make_response(
                _('Enkel een beheerder van de leverancierskoppelingen kan '
                  'een service user aanmaken.'), status=403)
        if error or not code:
            message = _('Aanmelden bij Van Marcke geannuleerd of mislukt: '
                        '%s', error_description or error or '-')
            connection.sudo().write({'vm_oauth_state': False})
            connection.message_post(body=message)
        else:
            try:
                connection._vm_oauth_callback(code)
            except UserError as e:
                request.env.cr.rollback()
                connection.sudo().write({'vm_oauth_state': False})
                _logger.warning('Van Marcke service user: %s', e)
                connection.message_post(body=_(
                    'Service user aanmaken mislukt: %s',
                    e.args[0] if e.args else e))
        return request.redirect(
            '/odoo/action-df_connects.connection_action/%s' % connection.id)
