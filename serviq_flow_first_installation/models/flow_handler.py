# -*- coding: utf-8 -*-
from odoo import _, api, models
from odoo.exceptions import UserError


class FirstInstallationFlow(models.AbstractModel):
    """Register the installation at its first installation: installation
    product + serial number from the customer stock of the distributor."""
    _name = 'serviq.portal.flow.handler.first_installation'
    _inherit = 'serviq.portal.flow.handler'
    _description = 'Portaalflow: eerste installatie'

    @api.model
    def _fi_products(self):
        """Installation products: products whose component role is an
        installation product."""
        return self.env['product.template'].search([
            ('serviq_role_id.is_installation_product', '=', True),
            ('type', '=', 'consu'),
        ], order='name')

    @api.model
    def _flow_values(self, task, flow, partner, is_internal):
        if task.serviq_installation_id:
            return {'fi_installation': task.serviq_installation_id}
        distributors = self._flow_distributors(task, partner, is_internal)
        products = self._fi_products()
        lots = self._flow_available_lots(distributors, products)
        return {
            'fi_installation': task.serviq_installation_id,
            # Only products with a serial available in the stock.
            'fi_products': products.filtered(
                lambda p: p in lots.product_id.product_tmpl_id),
            'fi_lots': lots,
            'fi_has_distributor_stock': bool(
                distributors.mapped('property_stock_customer')),
        }

    @api.model
    def _flow_submit(self, task, flow, partner, is_internal, post):
        if task.serviq_installation_id:
            raise UserError(_('Deze interventie heeft al een installatie.'))
        try:
            product_tmpl_id = int(post.get('product_tmpl_id') or 0)
            lot_id = int(post.get('lot_id') or 0)
        except (TypeError, ValueError):
            product_tmpl_id = lot_id = 0
        if not product_tmpl_id or not lot_id:
            raise UserError(_('Kies een product en een serienummer.'))
        product_tmpl = self._fi_products().filtered(
            lambda p: p.id == product_tmpl_id)
        if not product_tmpl:
            raise UserError(_('Dit product is geen installatieproduct.'))

        # The serial must be available in the stock of a distributor the
        # user works with; that distributor becomes the distributor of the
        # installation.
        distributors = self._flow_distributors(task, partner, is_internal)
        lot = self._flow_available_lots(distributors, product_tmpl) \
            .filtered(lambda l: l.id == lot_id)
        if not lot:
            raise UserError(_(
                'Dit serienummer is niet beschikbaar in de voorraad van de '
                'distributeur.'))
        quant = self.env['stock.quant'].search([
            ('lot_id', '=', lot.id), ('quantity', '>', 0),
            ('location_id', 'in',
             distributors.mapped('property_stock_customer').ids),
        ], limit=1)
        distributor = distributors.filtered(
            lambda d: d.property_stock_customer == quant.location_id)[:1]

        commercial = partner.commercial_partner_id
        installer = task.serviq_installer_id
        if not installer and not is_internal and (
                commercial.serviq_is_installer or partner.serviq_is_installer):
            installer = commercial if commercial.serviq_is_installer \
                else partner
        category = product_tmpl.serviq_category_id
        Installation = self.env['serviq.installation']
        installation = Installation.with_context(
            defer_creation_summary=True).create({
                'product_tmpl_id': product_tmpl.id,
                'category_id': category.id,
                'customer_id': task.partner_id.id,
                'distributor_id': (distributor or task.serviq_distributor_id).id,
                'installer_id': installer.id,
                'lot_id': lot.id,
                'line_ids': Installation._bom_line_commands(product_tmpl),
                'state': 'active' if category.active_after_first_installation
                else 'installation',
            })
        installation._post_creation_summary(
            origin=_('Portaal, interventie %s', task.name))
        task.write({'serviq_installation_id': installation.id})
        self._flow_post(task, partner, _(
            'Installatie %s aangemaakt vanuit het portaal.',
            installation.display_name))
        return _('Installatie %s aangemaakt.', installation.display_name), None
