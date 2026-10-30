from odoo import api, fields, models

from .dashboard_access import DASHBOARDS

# user field -> dashboard key (see dashboard_access.DASHBOARDS)
_FIELDS = {
    'serviq_dash_stock': 'stock',
    'serviq_dash_sn': 'sn',
    'serviq_dash_incoming': 'incoming',
    'serviq_dash_outgoing': 'outgoing',
    'serviq_dash_spare': 'spare',
}


class ResUsers(models.Model):
    _inherit = 'res.users'

    # Checkboxes on the user form, one per dashboard: each one adds or
    # removes the user from the group of that dashboard.
    serviq_dash_stock = fields.Boolean('Voorraadoverzicht', compute='_compute_serviq_dash', inverse='_inverse_serviq_dash')
    serviq_dash_sn = fields.Boolean('Serienummers', compute='_compute_serviq_dash', inverse='_inverse_serviq_dash')
    serviq_dash_incoming = fields.Boolean('Inkomende goederen', compute='_compute_serviq_dash', inverse='_inverse_serviq_dash')
    serviq_dash_outgoing = fields.Boolean('Uitgaande goederen', compute='_compute_serviq_dash', inverse='_inverse_serviq_dash')
    serviq_dash_spare = fields.Boolean('Reserveonderdelen', compute='_compute_serviq_dash', inverse='_inverse_serviq_dash')

    def _serviq_dash_groups(self):
        return {name: self.env.ref(DASHBOARDS[key][0], raise_if_not_found=False)
                for name, key in _FIELDS.items()}

    @api.depends('group_ids')
    def _compute_serviq_dash(self):
        groups = self._serviq_dash_groups()
        for user in self:
            # _origin: in the form (onchange) the user and its groups are
            # new-record copies; compare the real ids
            member = set(user.group_ids._origin.ids)
            for name, group in groups.items():
                user[name] = bool(group) and group.id in member

    def _inverse_serviq_dash(self):
        groups = self._serviq_dash_groups()
        for user in self:
            member = set(user.group_ids._origin.ids)
            commands = []
            for name, group in groups.items():
                if not group:
                    continue
                if user[name] and group.id not in member:
                    commands.append((4, group.id))
                elif not user[name] and group.id in member:
                    commands.append((3, group.id))
            if commands:
                # assignment works for saved users and in the form (onchange)
                user.group_ids = commands
