# -*- coding: utf-8 -*-
import logging

from odoo import _, fields, models

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    serviq_installation_ids = fields.One2many(
        'serviq.installation', 'delivery_picking_id',
        string='Aangemaakte installaties', readonly=True)
    serviq_installation_count = fields.Integer(
        compute='_compute_serviq_installation_count')

    def _compute_serviq_installation_count(self):
        for picking in self:
            picking.serviq_installation_count = len(
                picking.serviq_installation_ids)

    def action_view_serviq_installations(self):
        self.ensure_one()
        installations = self.serviq_installation_ids
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Installaties'),
            'res_model': 'serviq.installation',
            'view_mode': 'list,form',
            'domain': [('id', 'in', installations.ids)],
        }
        if len(installations) == 1:
            action.update(view_mode='form', res_id=installations.id)
        return action

    def _action_done(self):
        res = super()._action_done()
        for picking in self:
            # Never block the delivery validation itself: run the
            # auto-creation in a savepoint and log failures.
            try:
                with self.env.cr.savepoint():
                    picking._serviq_auto_create_installations()
            except Exception:
                _logger.exception(
                    'Automatic installation creation failed for delivery '
                    '%s', picking.name)
        return res

    # ------------------------------------------------------------------
    # Auto-create installations on delivery
    # ------------------------------------------------------------------
    def _serviq_free_lot(self, lot):
        """`lot` is not on an installation yet (e.g. a replacement unit
        registered via the portal)."""
        if not lot:
            return True
        if lot.serviq_installation_id:
            return False
        return not self.env['serviq.installation.line'].sudo().search_count(
            [('lot_id', '=', lot.id)], limit=1)

    def _serviq_create_delivery_task(self, installation):
        """Plan the intervention the category asks for after a delivery
        (e.g. the commissioning), once."""
        itype = installation.category_id.delivery_intervention_type_id
        Task = self.env['project.task'].sudo()
        if not itype:
            return Task
        existing = Task.search([
            ('serviq_installation_id', '=', installation.id),
            ('serviq_intervention_type_id', '=', itype.id),
        ], limit=1)
        if existing:
            return existing
        project = installation._intervention_project()
        if not project:
            return Task
        return Task.create({
            'name': '%s - %s' % (itype.name, installation.name or ''),
            'project_id': project.id,
            'partner_id': installation.customer_id.id,
            'serviq_installation_id': installation.id,
            'serviq_intervention_type_id': itype.id,
            'serviq_installer_id': installation.installer_id.id,
        })

    def _serviq_auto_create_installations(self):
        """When an outgoing delivery holding installation products of a
        category that has 'Aanmaken bij levering' is done, create the
        installations:

        - a category with an installation product gets one installation of
          that product per delivery, holding the delivered units as
          components;
        - otherwise every delivered unit becomes its own installation, with
          the components of its bill of materials.

        The distributor is the customer of the sales order, the customer
        the delivery address. The category's intervention after delivery
        is planned for each new installation.
        """
        self.ensure_one()
        Installation = self.env['serviq.installation']
        if self.picking_type_code != 'outgoing' or self.state != 'done':
            return Installation
        move_lines = self.move_line_ids.filtered(
            lambda ml: ml.quantity > 0
            and ml.product_id.serviq_role_id.is_installation_product
            and ml.product_id.serviq_category_id.auto_create_on_delivery
            and self._serviq_free_lot(ml.lot_id))
        if not move_lines:
            return Installation
        sale = self.sale_id if 'sale_id' in self._fields else False
        distributor = sale.partner_id if sale else self.partner_id
        customer = self.partner_id or distributor
        origin = _('levering %s', self.name)
        if sale:
            origin = _('levering %(picking)s (order %(order)s)',
                       picking=self.name, order=sale.name)
        base_vals = {
            'distributor_id': distributor.id
            if distributor.serviq_is_distributor else False,
            'customer_id': customer.id,
            'state': 'delivered',
            'delivery_picking_id': self.id,
        }
        Model = Installation.sudo().with_context(
            skip_lot_validation=True, defer_creation_summary=True)
        created = Installation
        for category, cat_lines in move_lines.grouped(
                lambda ml: ml.product_id.serviq_category_id).items():
            wrapper = category.wrapper_product_tmpl_id
            if wrapper:
                lines = []
                for ml in cat_lines:
                    units = 1 if ml.lot_id else max(int(ml.quantity), 1)
                    lines += [(0, 0, {
                        'product_tmpl_id': ml.product_id.product_tmpl_id.id,
                        'product_qty': 1,
                        'lot_id': ml.lot_id.id,
                    })] * units
                created |= Model.create(dict(
                    base_vals, product_tmpl_id=wrapper.id,
                    category_id=category.id, line_ids=lines))
                continue
            for ml in cat_lines:
                units = 1 if ml.lot_id else max(int(ml.quantity), 1)
                tmpl = ml.product_id.product_tmpl_id
                for _unit in range(units):
                    created |= Model.create(dict(
                        base_vals, product_tmpl_id=tmpl.id,
                        category_id=category.id, lot_id=ml.lot_id.id,
                        line_ids=Installation._bom_line_commands(tmpl)))
        for installation in created:
            installation._post_creation_summary(origin=origin)
            self._serviq_create_delivery_task(installation)
        self.message_post(body=_(
            'Installaties automatisch aangemaakt voor deze levering: %s',
            ', '.join(created.mapped('display_name'))))
        return created
