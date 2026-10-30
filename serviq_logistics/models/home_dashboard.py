from odoo import models, api

from .dashboard_cache import cached
from .dashboard_access import access_flags

OPERATIONAL = ('stock', 'sn', 'incoming', 'outgoing', 'spare')


class HomeDashboard(models.AbstractModel):
    _name = 'serviq.logistics.home'
    _description = 'Logistiek: overzicht (landingspagina)'

    @api.model
    def get_home_data(self, subgroup=None, force=False):
        """Operational KPIs for the landing page tiles, honouring the
        segment filter, and which dashboards the user may open (`access`).
        Only the tiles of those dashboards are returned."""
        env = self.env
        # the tiles are computed in sudo (shared cache); what the user
        # gets back is limited to the dashboards they have access to
        su = env(su=True)

        def compute():
            return {
                'stock': su['serviq.logistics.stock'].get_dashboard_summary(subgroup),
                'sn': su['serviq.logistics.sn'].get_summary(subgroup),
                'incoming': su['serviq.logistics.incoming'].get_incoming_summary(subgroup),
                'outgoing': su['serviq.logistics.outgoing'].get_outgoing_summary(subgroup),
                'spare': su['serviq.logistics.spare'].get_spare_stock_summary(
                    subgroup=subgroup),
            }
        access = access_flags(env)
        if any(access[k] for k in OPERATIONAL):
            data = dict(cached(self, 'home.operational', (subgroup,), compute, force=force))
        else:
            data = {}
        for key in OPERATIONAL:
            if not access[key]:
                data.pop(key, None)
        data['access'] = access
        return data
