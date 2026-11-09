# -*- coding: utf-8 -*-
# Working with distributors became optional (group_serviq_distributor).
# Databases from before used distributors: keep the feature on for them.
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    env.ref('base.group_user').write({'implied_ids': [
        (4, env.ref('serviq_installation.group_serviq_distributor').id)]})
