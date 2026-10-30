# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class CommissioningFlow(models.AbstractModel):
    """Complete the components of the installation (serial, note) and
    finish the commissioning."""
    _name = 'serviq.portal.flow.handler.commissioning'
    _inherit = 'serviq.portal.flow.handler'
    _description = 'Portaalflow: inbedrijfstelling'

    @api.model
    def _flow_applies(self, task, flow):
        return bool(task.serviq_installation_id) \
            and super()._flow_applies(task, flow)

    @api.model
    def _flow_values(self, task, flow, partner, is_internal):
        installation = task.serviq_installation_id
        return {
            'co_installation': installation,
            'co_lines': installation.line_ids,
            'co_done': task.state == '1_done' or task._serviq_is_finished(),
        }

    @api.model
    def _co_line_commands(self, installation, post):
        """Update commands for the component lines whose serial or note
        changed in the form (fields serial_<line id> / note_<line id>)."""
        commands = []
        for line in installation.line_ids:
            vals = {}
            serial = (post.get('serial_%d' % line.id) or '').strip()
            if serial and serial != (line.lot_id.name or ''):
                lot = self._flow_find_lot(serial, line.product_tmpl_id)
                if not lot:
                    raise UserError(_(
                        'Serienummer "%(serial)s" voor %(component)s is niet '
                        'gekend.', serial=serial,
                        component=line.product_tmpl_id.display_name))
                installation._validate_lot_for_line(
                    lot, line=line,
                    expected_product_tmpl=line.product_tmpl_id)
                vals['lot_id'] = lot.id
            note_key = 'note_%d' % line.id
            if note_key in post:
                note = (post.get(note_key) or '').strip()
                if note != (line.note or ''):
                    vals['note'] = note or False
            if vals:
                commands.append((1, line.id, vals))
        return commands

    @api.model
    def _flow_submit(self, task, flow, partner, is_internal, post):
        installation = task.serviq_installation_id
        if not installation:
            raise UserError(_('Deze interventie heeft geen installatie.'))
        finish = post.get('action') == 'finish'
        if task.state == '1_done' or task._serviq_is_finished():
            raise UserError(_('Deze inbedrijfstelling is al afgerond.'))

        commands = self._co_line_commands(installation, post)
        if commands:
            # Through the installation, so the changes are traced in its
            # chatter.
            installation.write({'line_ids': commands})
        if not finish:
            return (_('Componenten opgeslagen.') if commands
                    else _('Geen wijzigingen.')), None

        missing = installation.line_ids.filtered(
            lambda l: not l.lot_id and not l.serial_photo
            and l.product_tmpl_id.tracking == 'serial')
        if missing:
            raise UserError(_(
                'Vul eerst het serienummer in van: %s.',
                ', '.join(missing.product_tmpl_id.mapped('display_name'))))
        # Done -> the core moves the installation to 'Actief'.
        task.write({'state': '1_done', 'date_end': fields.Datetime.now()})
        body = _('Inbedrijfstelling afgerond door %s via het portaal.',
                 partner.name)
        self._flow_post(task, partner, body)
        self._flow_post(installation, partner, body)
        return _('Inbedrijfstelling afgerond.'), None
