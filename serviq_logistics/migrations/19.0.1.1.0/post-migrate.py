"""Upgrade to the Voorraadstroom dashboard: the existing warehouse team
(internal users with Inventory / User rights) gets its new access group,
as a fresh installation would give it (see hooks.py)."""
from odoo import SUPERUSER_ID, api

from odoo.addons.serviq_logistics.hooks import grant_initial_dashboard_access


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    grant_initial_dashboard_access(env, ['group_dashboard_flow'])
