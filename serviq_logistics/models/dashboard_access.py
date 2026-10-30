"""Per-dashboard access: one security group per dashboard, set per user
with a checkbox on the user form (see res_users.py)."""
from odoo import _
from odoo.exceptions import AccessError

# key -> (group xmlid, dashboard name)
DASHBOARDS = {
    'stock': ('serviq_logistics.group_dashboard_stock', 'Voorraadoverzicht'),
    'sn': ('serviq_logistics.group_dashboard_sn', 'Serienummers'),
    'incoming': ('serviq_logistics.group_dashboard_incoming', 'Inkomende goederen'),
    'outgoing': ('serviq_logistics.group_dashboard_outgoing', 'Uitgaande goederen'),
    'spare': ('serviq_logistics.group_dashboard_spare', 'Reserveonderdelen'),
}


def has_dashboard_access(env, key):
    return env.su or env.user.has_group(DASHBOARDS[key][0])


def access_flags(env):
    return {key: has_dashboard_access(env, key) for key in DASHBOARDS}


def check_dashboard_access(env, *keys):
    """Raise AccessError unless the user may open one of the dashboards
    `keys`. Calls made in sudo (e.g. the landing page tiles) pass."""
    if any(has_dashboard_access(env, key) for key in keys):
        return
    names = ', '.join(DASHBOARDS[key][1] for key in keys)
    raise AccessError(_('Je hebt geen toegang tot het dashboard %s. '
                        'Vraag een beheerder om het aan te vinken op je gebruiker.', names))
