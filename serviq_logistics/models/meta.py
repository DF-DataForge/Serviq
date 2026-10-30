from odoo import models, api

from .labels import NO_TYPE, NO_TYPE_LABEL


class LogisticsMeta(models.AbstractModel):
    """Filter options shared by all logistic dashboards: the segments
    (installation categories) and the product types (component roles).
    Loaded once per page by the JS (product_types.js / subgroup_filter.js)
    so the dashboards hold no hardcoded categories or types."""
    _name = 'serviq.logistics.meta'
    _description = 'Logistiek dashboards: filteropties'

    @api.model
    def get_filter_options(self):
        categories = self.env['serviq.installation.category'].sudo().search(
            [], order='sequence, id')
        roles = self.env['serviq.component.role'].sudo().with_context(
            active_test=False).search([], order='sequence, id')
        return {
            'segments': [{'value': c.code, 'label': c.name}
                         for c in categories if c.code],
            'types': [{'key': r.code, 'label': r.name, 'spare': bool(r.is_spare_part)}
                      for r in roles if r.code] + [
                {'key': NO_TYPE, 'label': NO_TYPE_LABEL, 'spare': False}],
        }
