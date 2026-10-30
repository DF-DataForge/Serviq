# -*- coding: utf-8 -*-
from odoo import _, api, models
from odoo.exceptions import UserError, ValidationError


class ReplacementFlow(models.AbstractModel):
    """Swap the serial of a component of the installation and keep the
    replacement history."""
    _name = 'serviq.portal.flow.handler.replacement'
    _inherit = 'serviq.portal.flow.handler'
    _description = 'Portaalflow: vervanging'

    @api.model
    def _flow_applies(self, task, flow):
        return bool(task.serviq_installation_id) \
            and super()._flow_applies(task, flow)

    @api.model
    def _rp_replaceable_lines(self, installation):
        """Components that can be swapped: role 'Vervangbaar', or any
        component with a serial when it has no role."""
        return installation.line_ids.filtered(
            lambda l: l.role_id.is_replaceable
            or (not l.role_id and l.lot_id))

    @api.model
    def _rp_line(self, task, line_id):
        try:
            line_id = int(line_id or 0)
        except (TypeError, ValueError):
            line_id = 0
        line = self._rp_replaceable_lines(task.serviq_installation_id) \
            .filtered(lambda l: l.id == line_id)
        if not line:
            raise UserError(_('Kies een component om te vervangen.'))
        return line

    @api.model
    def _rp_new_lot(self, line, serial):
        """Validated lot for the new part of `line`; raises UserError /
        ValidationError otherwise."""
        serial = (serial or '').strip()
        if not serial:
            raise UserError(_('Geef het serienummer van het nieuwe '
                              'onderdeel op.'))
        if serial == (line.lot_id.name or ''):
            raise UserError(_('Dit is het huidige serienummer.'))
        lot = self._flow_find_lot(serial, line.product_tmpl_id)
        if not lot:
            raise UserError(_('Serienummer "%s" is niet gekend.', serial))
        installation = line.installation_id
        installation._validate_lot_for_line(
            lot, line=line, expected_product_tmpl=line.product_tmpl_id)
        if lot in (installation.line_ids - line).lot_id \
                or lot == installation.lot_id:
            raise UserError(_(
                'Serienummer "%s" wordt al gebruikt in deze installatie.',
                lot.name))
        return lot

    @api.model
    def _flow_values(self, task, flow, partner, is_internal):
        installation = task.serviq_installation_id
        return {
            'rp_lines': self._rp_replaceable_lines(installation),
            'rp_history': self.env['serviq.installation.replacement']
            .search([('task_id', '=', task.id)]),
            'rp_check_url': '/my/installations/intervention/%d/flow/%s/check'
                            % (task.id, flow.code),
        }

    @api.model
    def _flow_check(self, task, flow, partner, is_internal, params):
        try:
            line = self._rp_line(task, params.get('line_id'))
            lot = self._rp_new_lot(line, params.get('serial'))
        except (UserError, ValidationError) as exc:
            return {'ok': False, 'message': exc.args[0] if exc.args else ''}
        return {'ok': True,
                'message': _('Serienummer %s is beschikbaar.', lot.name)}

    @api.model
    def _flow_submit(self, task, flow, partner, is_internal, post):
        line = self._rp_line(task, post.get('line_id'))
        new_lot = self._rp_new_lot(line, post.get('serial'))
        installation = line.installation_id
        old_lot = line.lot_id

        # Through the installation, so the change is traced in its chatter.
        installation.write({'line_ids': [(1, line.id, {
            'lot_id': new_lot.id,
            'serial_photo': False,
            'serial_photo_filename': False,
        })]})
        if old_lot.serviq_installation_id == installation:
            old_lot.serviq_installation_id = False
        replacement = self.env['serviq.installation.replacement'].create({
            'installation_id': installation.id,
            'task_id': task.id,
            'line_id': line.id,
            'product_tmpl_id': line.product_tmpl_id.id,
            'old_lot_id': old_lot.id,
            'new_lot_id': new_lot.id,
            'note': (post.get('note') or '').strip() or False,
        })
        body = _('Component vervangen door %(name)s: %(summary)s',
                 name=partner.name, summary=replacement._summary())
        if replacement.note:
            body = _('%(body)s (%(note)s)', body=body, note=replacement.note)
        self._flow_post(installation, partner, body)
        self._flow_post(task, partner, body)
        return _('Vervanging geregistreerd: %s', replacement._summary()), None
