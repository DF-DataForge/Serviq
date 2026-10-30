# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    serviq_is_distributor = fields.Boolean(string='Is distributeur')
    serviq_is_installer = fields.Boolean(string='Is installateur')
    serviq_can_install_for_ids = fields.Many2many(
        'res.partner', 'serviq_partner_installer_distributor_rel',
        'installer_id', 'distributor_id', string='Installeert voor',
        domain="[('serviq_is_distributor', '=', True)]",
        help='Distributors this installer can work for.')
    serviq_installation_count = fields.Integer(
        string='Installaties', compute='_compute_serviq_installation_count')

    def _compute_serviq_installation_count(self):
        Installation = self.env['serviq.installation']
        for partner in self:
            commercial = partner.commercial_partner_id.id or partner.id
            partner.serviq_installation_count = Installation.search_count([
                ('parent_line_id', '=', False),
                '|', '|',
                ('customer_id', 'child_of', commercial),
                ('distributor_id', 'child_of', commercial),
                ('installer_id', 'child_of', commercial),
            ]) if isinstance(partner.id, int) else 0

    def action_view_serviq_installations(self):
        self.ensure_one()
        commercial = self.commercial_partner_id.id or self.id
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Installaties'),
            'res_model': 'serviq.installation',
            'view_mode': 'kanban,list,form',
            'domain': [
                ('parent_line_id', '=', False),
                '|', '|',
                ('customer_id', 'child_of', commercial),
                ('distributor_id', 'child_of', commercial),
                ('installer_id', 'child_of', commercial),
            ],
            'context': {'default_customer_id': self.id},
        }

    # ------------------------------------------------------------------
    # Customer-specific stock location of distributors
    # ------------------------------------------------------------------
    @api.model
    def _serviq_use_distributor_locations(self):
        return bool(self.env['ir.config_parameter'].sudo().get_param(
            'serviq_installation.distributor_locations'))

    def _serviq_get_or_create_location(self):
        self.ensure_one()
        Location = self.env['stock.location'].sudo()
        location = Location.search(
            [('serviq_partner_id', '=', self.id)], limit=1)
        if location:
            return location
        parent = self.env.ref('stock.stock_location_customers',
                              raise_if_not_found=False)
        return Location.create({
            'name': self.name,
            'usage': 'customer',
            'company_id': self.company_id.id,
            'serviq_partner_id': self.id,
            'location_id': parent.id if parent else False,
        })

    def _serviq_apply_distributor_location(self):
        """Set the distributor's customer-specific location on the
        distributor itself and on all its sub-contacts."""
        for partner in self:
            location = partner._serviq_get_or_create_location()
            self.search([('id', 'child_of', partner.id)]).write(
                {'property_stock_customer': location.id})

    def _serviq_distributor_ancestor(self):
        """Nearest parent that is a distributor, or an empty recordset."""
        self.ensure_one()
        node = self.parent_id
        while node:
            if node.serviq_is_distributor:
                return node
            node = node.parent_id
        return self.browse()

    def _serviq_inherit_distributor_location(self):
        """Sub-contacts of a distributor inherit its customer-specific
        location."""
        for partner in self:
            location = partner._serviq_distributor_ancestor() \
                .property_stock_customer
            if location:
                self.search([('id', 'child_of', partner.id)]).write(
                    {'property_stock_customer': location.id})

    @api.model_create_multi
    def create(self, vals_list):
        partners = super().create(vals_list)
        if self._serviq_use_distributor_locations():
            distributors = partners.filtered('serviq_is_distributor')
            distributors._serviq_apply_distributor_location()
            (partners - distributors)._serviq_inherit_distributor_location()
        return partners

    def write(self, vals):
        res = super().write(vals)
        if self._serviq_use_distributor_locations():
            if vals.get('serviq_is_distributor'):
                self.filtered('serviq_is_distributor') \
                    ._serviq_apply_distributor_location()
            if vals.get('parent_id'):
                self.filtered(lambda p: not p.serviq_is_distributor) \
                    ._serviq_inherit_distributor_location()
        return res
