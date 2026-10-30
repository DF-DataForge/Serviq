# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request

from odoo.addons.serviq_portal.controllers.portal import ServiqPortal


class RefrigerantPortal(ServiqPortal):

    @http.route(['/my/installations/<int:installation_id>/'
                 'refrigerant-logbook.pdf'],
                type='http', auth='user', website=True, methods=['GET'])
    def serviq_refrigerant_logbook(self, installation_id, **kw):
        """Logbook of the installation as PDF, so it can be shown on site
        at an inspection."""
        installation = request.env['serviq.installation'].sudo().browse(
            installation_id)
        if not self._check_installation_access(installation) \
                or not installation.has_refrigerant:
            return self._serviq_no_access()
        pdf, _type = request.env['ir.actions.report'].sudo() \
            ._render_qweb_pdf(
                'serviq_flow_refrigerant.action_report_refrigerant_logbook',
                [installation.id])
        filename = 'logboek-%s.pdf' % (installation.code or installation.id)
        return request.make_response(pdf, headers=[
            ('Content-Type', 'application/pdf'),
            ('Content-Length', len(pdf)),
            ('Content-Disposition', 'inline; filename="%s"'
             % filename.replace('/', '-')),
        ])
