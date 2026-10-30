# -*- coding: utf-8 -*-
from markupsafe import Markup

from odoo import _, api, models


class PortalFlowHandler(models.AbstractModel):
    """Contract of a portal flow. A flow addon implements it in its own
    AbstractModel::

        class MyFlow(models.AbstractModel):
            _name = 'serviq.portal.flow.handler.<code>'
            _inherit = 'serviq.portal.flow.handler'

    and points its ``serviq.portal.flow`` record at it (``handler_model``).

    The portal calls the handler with sudo(); the access to the
    intervention has been checked before (installer / distributor of the
    task, or an internal user). ``partner`` is the contact of the portal
    user, ``is_internal`` tells whether the user is an internal user.
    """
    _name = 'serviq.portal.flow.handler'
    _description = 'Handler van een portaalflow'

    # ------------------------------------------------------------------
    # Contract
    # ------------------------------------------------------------------
    @api.model
    def _flow_applies(self, task, flow):
        """The flow is shown on the page of intervention `task`: its type
        is one of the flow's intervention types (any type when none is
        set) and, when the flow is restricted to categories, the category
        of the installation of the task is one of them (an intervention
        without installation, or an installation without category, is not
        restricted)."""
        if flow.intervention_type_ids \
                and task.serviq_intervention_type_id \
                not in flow.intervention_type_ids:
            return False
        category = task.serviq_installation_id.category_id
        if flow.installation_category_ids and category \
                and category not in flow.installation_category_ids:
            return False
        return True

    @api.model
    def _flow_values(self, task, flow, partner, is_internal):
        """Extra values for the QWeb section of the flow (merged into the
        values the template of the flow is rendered with). Prefix the keys
        with the code of the flow to avoid clashes with other flows."""
        return {}

    @api.model
    def _flow_submit(self, task, flow, partner, is_internal, post):
        """Handle a POST of the flow's form on
        /my/installations/intervention/<task>/flow/<code>.

        Return ``(message, error)`` (either may be None) to come back to
        the intervention page with that notification, or a URL (str) to
        redirect to. Raising UserError / ValidationError rolls back what
        was written and shows the error."""
        return None, _('Deze flow verwerkt geen formulieren.')

    @api.model
    def _flow_check(self, task, flow, partner, is_internal, params):
        """Optional live check (GET, JSON) on
        /my/installations/intervention/<task>/flow/<code>/check, e.g. to
        validate a serial while it is typed. Returns a JSON-serialisable
        dict, by convention ``{'ok': bool, 'message': str}``."""
        return {'ok': False, 'message': ''}

    # ------------------------------------------------------------------
    # Helpers shared by the flows
    # ------------------------------------------------------------------
    @api.model
    def _flow_distributors(self, task, partner, is_internal):
        """Distributors whose customer stock the user can use for this
        intervention: the distributor of the installation / task, else the
        distributors the installer works for, the distributor itself, or
        every distributor for internal users."""
        Partner = self.env['res.partner']
        distributor = task.serviq_installation_id.distributor_id \
            or task.serviq_distributor_id
        if distributor:
            return distributor
        commercial = partner.commercial_partner_id
        if is_internal:
            return Partner.search([('serviq_is_distributor', '=', True)])
        result = Partner.browse()
        if commercial.serviq_is_installer or partner.serviq_is_installer:
            result |= commercial.serviq_can_install_for_ids \
                | partner.serviq_can_install_for_ids
        if commercial.serviq_is_distributor:
            result |= commercial
        elif partner.serviq_is_distributor:
            result |= partner
        return result

    @api.model
    def _flow_available_lots(self, distributors, product_tmpls=None):
        """Serials in stock in the customer location of `distributors`, not
        linked to an installation nor used on a component, optionally of
        one of `product_tmpls`."""
        Lot = self.env['stock.lot']
        locations = distributors.mapped('property_stock_customer')
        if not locations:
            return Lot
        domain = [('location_id', 'in', locations.ids),
                  ('quantity', '>', 0), ('lot_id', '!=', False)]
        if product_tmpls is not None:
            domain.append(('product_id.product_tmpl_id', 'in',
                           product_tmpls.ids))
        lots = self.env['stock.quant'].search(domain).lot_id
        used = self.env['serviq.installation.line'].search(
            [('lot_id', 'in', lots.ids)]).lot_id
        return (lots - used).filtered(
            lambda lot: not lot.serviq_installation_id).sorted('name')

    @api.model
    def _flow_find_lot(self, serial, product_tmpl=None):
        """Lot named `serial`, preferably of `product_tmpl` (the validation
        of the installation reports a product mismatch)."""
        serial = (serial or '').strip()
        Lot = self.env['stock.lot']
        if not serial:
            return Lot
        lots = Lot.search([('name', '=', serial)], limit=20)
        if product_tmpl:
            return lots.filtered(
                lambda lot: lot.product_id.product_tmpl_id == product_tmpl
            )[:1] or lots[:1]
        return lots[:1]

    @api.model
    def _flow_post(self, records, partner, body):
        """Chatter message on `records` (tasks, installations) in the name
        of the portal user."""
        body = body if isinstance(body, Markup) else Markup('%s') % body
        for record in records:
            record.message_post(body=body, author_id=partner.id)
