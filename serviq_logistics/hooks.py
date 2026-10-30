"""Initial dashboard access, so the warehouse team can open the
dashboards right after installation: every internal user with Inventory /
User rights gets all logistic dashboards. Access is managed per user
afterwards with the checkboxes on the user form."""

DASHBOARD_GROUPS = ['group_dashboard_stock', 'group_dashboard_sn', 'group_dashboard_incoming',
                    'group_dashboard_outgoing', 'group_dashboard_spare']


def grant_initial_dashboard_access(env):
    users = env['res.users'].with_context(active_test=False).search([('share', '=', False)])
    members = users.filtered(lambda u: u.has_group('stock.group_stock_user'))
    if not members:
        return
    for xmlid in DASHBOARD_GROUPS:
        group = env.ref('serviq_logistics.' + xmlid, raise_if_not_found=False)
        if group:
            group.write({'user_ids': [(4, uid) for uid in members.ids]})


def post_init_hook(env):
    grant_initial_dashboard_access(env)
