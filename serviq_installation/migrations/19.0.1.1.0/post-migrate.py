# -*- coding: utf-8 -*-
# * Working with distributors became optional (group_serviq_distributor).
#   Databases from before used distributors: keep the feature on for them.
# * The on/off check of the distributor stock became the serial-number
#   validation mode: on -> 'distributor', off -> 'none'.
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    env.ref('base.group_user').write({'implied_ids': [
        (4, env.ref('serviq_installation.group_serviq_distributor').id)]})

    params = env['ir.config_parameter'].sudo()
    if not params.get_param('serviq_installation.sn_validation'):
        old = params.get_param('serviq_installation.check_distributor_stock')
        params.set_param('serviq_installation.sn_validation',
                         'distributor' if old else 'none')
    params.search([('key', '=',
                    'serviq_installation.check_distributor_stock')]).unlink()
