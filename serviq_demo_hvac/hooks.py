# -*- coding: utf-8 -*-
# Builds the "Frisair Klimaattechniek" demo company on install: a Belgian
# airco installer that stores its airco units in the Stoqflow fulfilment
# warehouse (a plain Odoo warehouse here, without the Stoqflow integration).
#   * master data: company, the own workshop warehouse (with spare parts
#     shelf and service vans), the Stoqflow warehouse, partners, Serviq
#     configuration, serial-tracked units, mounting kits (BoM), spare parts
#     and installation packages (kit BoM of outdoor + indoor unit + mounting
#     kit);
#   * a few weeks of documents: units bought into Stoqflow, kit parts bought
#     into the workshop, kits assembled and resupplied to Stoqflow, packages
#     sold and delivered by Stoqflow with their serial numbers, spare parts
#     on the vans and sold to a colleague installer;
#   * the installations at the customers with their interventions, and
#     repair orders on installed units (warranty and paid, every stage);
#   * open orders still waiting to be delivered or received.
import logging
from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

MODULE = 'serviq_demo_hvac'
# Serial number prefix per serial-tracked product (internal reference)
SERIAL_PREFIXES = {
    'NK-AERO-OUT-25': 'AO25', 'NK-AERO-OUT-35': 'AO35', 'NK-AERO-OUT-50': 'AO50',
    'NK-AERO-IN-25': 'AI25', 'NK-AERO-IN-35': 'AI35', 'NK-AERO-IN-50': 'AI50',
}
_serial_counters = {}


def post_init_hook(env):
    company = _setup_company(env)
    _enable_features(env)
    wks, sqf, locations = _setup_warehouses(env, company)
    serviq = _setup_serviq(env, company)
    partners = _setup_partners(env)
    products = _setup_products(env, partners, serviq, wks, sqf)
    _run_unit_purchases(env, partners, products, sqf)
    _run_kit_assembly(env, partners, products, wks, sqf)
    _run_spare_parts(env, partners, products, wks, locations)
    installations = _run_package_sales(env, partners, products, serviq, sqf)
    installations.update(_setup_older_installations(env, partners, products, serviq))
    _run_open_orders(env, partners, products, sqf)
    _run_repairs(env, partners, products, serviq, wks, locations, installations)
    _setup_orderpoints(env, products, wks, sqf)
    _logger.info('Frisair Klimaattechniek demo data installed')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _xmlid(record, name):
    """Give a demo record an external ID so it can be found with env.ref()."""
    record.env['ir.model.data'].create({
        'module': MODULE,
        'name': name,
        'model': record._name,
        'res_id': record.id,
        'noupdate': True,
    })
    return record


def _days_ago(days):
    return fields.Datetime.now() - timedelta(days=days)


def _next_serial(product, date):
    """Next serial number of a unit, e.g. AO35-2609-0004: product prefix,
    production year and month, sequence."""
    key = (SERIAL_PREFIXES[product.default_code], date.strftime('%y%m'))
    _serial_counters[key] = _serial_counters.get(key, 0) + 1
    return '%s-%s-%04d' % (key + (_serial_counters[key],))


def _receive_serials(move, date):
    """Register a serial number per received unit."""
    move.move_line_ids.unlink()
    move.env['stock.move.line'].create([{
        'move_id': move.id,
        'picking_id': move.picking_id.id,
        'product_id': move.product_id.id,
        'product_uom_id': move.product_id.uom_id.id,
        'location_id': move.location_id.id,
        'location_dest_id': move.location_dest_id.id,
        'lot_name': _next_serial(move.product_id, date),
        'quantity': 1,
    } for _unit in range(int(move.product_uom_qty))])


def _validate(picking, date_done=None):
    """Process a picking in full, as if the warehouse handled every line.
    Received serial-tracked units get a new serial number; deliveries use
    the serials reserved by Odoo."""
    picking.action_assign()
    for move in picking.move_ids:
        if move.product_id.tracking == 'serial' and picking.picking_type_code == 'incoming':
            _receive_serials(move, date_done or fields.Datetime.now())
        else:
            move.quantity = move.product_uom_qty
    picking.move_ids.picked = True
    picking.with_context(skip_backorder=True, skip_sms=True).button_validate()
    if picking.state != 'done':
        raise UserError('Demo data: picking %s could not be validated' % picking.name)
    if date_done:
        picking.date_done = date_done
        picking.move_ids.date = date_done
        picking.move_ids.move_line_ids.date = date_done
    return picking


def _purchase(env, vendor, lines, picking_type, days_ago=0, receive=False, location_dest=None):
    po = env['purchase.order'].create({
        'partner_id': vendor.id,
        'user_id': env.ref('base.user_admin').id,
        'picking_type_id': picking_type.id,
        'date_order': _days_ago(days_ago),
        'order_line': [
            Command.create({'product_id': product.id, 'product_qty': qty})
            for product, qty in lines
        ],
    })
    po.button_confirm()
    if location_dest:
        po.picking_ids.location_dest_id = location_dest
        po.picking_ids.move_ids.location_dest_id = location_dest
    if receive:
        for picking in po.picking_ids:
            _validate(picking, _days_ago(max(days_ago - 7, 0)))
    return po


def _sell(env, customer, lines, warehouse, days_ago=0, confirm=True, deliver=False):
    so = env['sale.order'].create({
        'partner_id': customer.id,
        # The hook runs as OdooBot; make the admin the salesperson so the
        # orders show up under the default "My Quotations" filter.
        'user_id': env.ref('base.user_admin').id,
        'warehouse_id': warehouse.id,
        'date_order': _days_ago(days_ago),
        'order_line': [
            Command.create({'product_id': product.id, 'product_uom_qty': qty})
            for product, qty in lines
        ],
    })
    if confirm:
        so.action_confirm()
        so.date_order = _days_ago(days_ago)
    if deliver:
        for picking in so.picking_ids:
            _validate(picking, _days_ago(max(days_ago - 1, 0)))
    return so


def _manufacture(env, product, qty, warehouse, days_ago=0, produce=False):
    mo = env['mrp.production'].create({
        'product_id': product.id,
        'user_id': env.ref('base.user_admin').id,
        'product_qty': qty,
        'picking_type_id': warehouse.manu_type_id.id,
        'date_start': _days_ago(days_ago),
    })
    mo.action_confirm()
    mo.action_assign()
    if produce:
        mo.qty_producing = qty
        mo.move_raw_ids.picked = True
        mo.with_context(skip_backorder=True).button_mark_done()
        mo.date_finished = _days_ago(days_ago)
    return mo


def _transfer(env, picking_type, source, dest, lines, days_ago=0):
    """Internal transfer between two locations of the workshop, done."""
    picking = env['stock.picking'].create({
        'picking_type_id': picking_type.id,
        'location_id': source.id,
        'location_dest_id': dest.id,
        'move_ids': [Command.create({
            'product_id': product.id,
            'product_uom_qty': qty,
            'location_id': source.id,
            'location_dest_id': dest.id,
        }) for product, qty in lines],
    })
    picking.action_confirm()
    return _validate(picking, _days_ago(days_ago))


def _task(env, serviq, installation, itype, deadline_days, done=False, description=None):
    """Intervention on an installation. `deadline_days` is the planned
    day relative to today (negative: in the past); None: not planned."""
    vals = {
        'name': '%s - %s' % (itype.name, installation.customer_id.name),
        'project_id': serviq['project'].id,
        'partner_id': installation.customer_id.id,
        'serviq_installation_id': installation.id,
        'serviq_intervention_type_id': itype.id,
        'serviq_installer_id': installation.installer_id.id,
        'user_ids': [Command.set(env.ref('base.user_admin').ids)],
        'description': description or False,
        'stage_id': serviq['stage_planned'].id if deadline_days is not None else serviq['stage_new'].id,
    }
    if deadline_days is not None:
        vals['date_deadline'] = fields.Datetime.now().replace(
            hour=8, minute=0, second=0, microsecond=0) + timedelta(days=deadline_days)
    if done:
        vals.update(state='1_done', stage_id=serviq['stage_done'].id)
    task = env['project.task'].create(vals)
    if done:
        # Closing a task stamps it with the current time: backdate it.
        task.date_end = vals['date_deadline'] + timedelta(hours=3)
    return task


# ---------------------------------------------------------------------------
# Company and features
# ---------------------------------------------------------------------------

def _setup_company(env):
    company = env.ref('base.main_company')
    company.write({
        'name': 'Frisair Klimaattechniek BV',
        'street': 'Industrieweg 18',
        'zip': '2800',
        'city': 'Mechelen',
        'country_id': env.ref('base.be').id,
        'phone': '+32 15 55 01 80',
        'email': 'info@frisair.example',
        'website': 'https://frisair.example',
    })
    # Belgian chart of accounts and taxes (sets the company currency to EUR).
    # On a fresh database Odoo postpones loading the generic chart until the
    # registry is ready, which would overwrite this one: cancel that.
    if hasattr(env.registry, '_auto_install_template'):
        del env.registry._auto_install_template
    if company.chart_template != 'be_comp':
        env['account.chart.template'].try_loading('be_comp', company, install_demo=False)
    env['product.pricelist'].search([]).currency_id = env.ref('base.EUR')
    env.ref('base.user_admin').partner_id.write({'name': 'Frisair Admin'})
    return company


def _enable_features(env):
    """Turn on the settings the demo relies on: serial numbers,
    multi-warehouse with locations and routes."""
    groups = [
        'stock.group_production_lot',
        'stock.group_stock_multi_locations',
        'stock.group_stock_multi_warehouses',
        'stock.group_adv_location',
    ]
    env.ref('base.group_user').write({
        'implied_ids': [Command.link(env.ref(xid).id) for xid in groups],
    })


def _setup_warehouses(env, company):
    """Frisair Werkplaats: own warehouse and workshop, with a spare parts
    shelf and a location per service van. Stoqflow Fulfilment: the
    fulfilment partner's warehouse storing the airco units and the mounting
    kits."""
    wks = env['stock.warehouse'].search([('company_id', '=', company.id)], limit=1)
    wks.write({'name': 'Frisair Werkplaats', 'code': 'FRW'})
    # Renaming the code does not rename existing sequences; align them
    for picking_type, code in [(wks.manu_type_id, 'MO'), (wks.repair_type_id, 'RO')]:
        picking_type.sequence_id.prefix = 'FRW/%s/' % code
    _xmlid(wks, 'warehouse_workshop')

    Location = env['stock.location']
    spare = _xmlid(Location.create({
        'name': 'Reserveonderdelen',
        'location_id': wks.lot_stock_id.id,
        'usage': 'internal',
        'serviq_is_spare_parts_location': True,
    }), 'location_spare_parts')
    # The vans hang under the warehouse, not under its stock: their stock is
    # not used for sales, only for the interventions.
    vans = {}
    for key, name in [('van_1', 'Servicewagen 1 (1-ABC-123)'), ('van_2', 'Servicewagen 2 (1-DEF-456)')]:
        vans[key] = _xmlid(Location.create({
            'name': name,
            'location_id': wks.view_location_id.id,
            'usage': 'internal',
        }), 'location_%s' % key)

    stoqflow_partner = env['res.partner'].create({
        'name': 'Stoqflow Fulfilment Centre',
        'is_company': True,
        'comment': 'Fulfilmentpartner die onze airco-units en montagekits opslaat en uitlevert.',
    })
    sqf = env['stock.warehouse'].create({
        'name': 'Stoqflow Fulfilment',
        'code': 'SQF',
        'company_id': company.id,
        'partner_id': stoqflow_partner.id,
        'manufacture_to_resupply': False,
        'resupply_wh_ids': [Command.link(wks.id)],
    })
    _xmlid(sqf, 'warehouse_stoqflow')
    # Sales are shipped by Stoqflow by default, also when entered in the backend
    env.ref('base.user_admin').property_warehouse_id = sqf

    # Repairs are done on site by the workshop: the unit stays at the
    # customer, parts come from the spare parts shelf (or a van, chosen on
    # the repair order). Stoqflow does not repair: new repair orders take the
    # operation type of the user's default warehouse (Stoqflow), so that
    # warehouse points to the workshop's type and its own is archived.
    wks.repair_type_id.write({
        'name': 'Herstellingen op locatie',
        'default_location_src_id': spare.id,
        'default_product_location_src_id': env.ref('stock.stock_location_customers').id,
        'default_product_location_dest_id': env.ref('stock.stock_location_customers').id,
    })
    sqf_repair_type = sqf.repair_type_id
    sqf.repair_type_id = wks.repair_type_id
    sqf_repair_type.active = False
    return wks, sqf, dict(vans, spare=spare)


# ---------------------------------------------------------------------------
# Serviq configuration
# ---------------------------------------------------------------------------

def _setup_serviq(env, company):
    category = _xmlid(env['serviq.installation.category'].create({
        'name': 'Split airco',
        'code': 'split_airco',
        'requires_commissioning': True,
        'delivery_intervention_type_id': env.ref(
            'serviq_installation.intervention_type_commissioning').id,
    }), 'category_split')

    Role = env['serviq.component.role']
    roles = {}
    for sequence, (key, name, extra) in enumerate([
        ('package', 'Installatiepakket', {'is_installation_product': True}),
        ('outdoor', 'Buitenunit', {'is_replaceable': True}),
        ('indoor', 'Binnenunit', {'is_replaceable': True}),
        ('mounting_kit', 'Montagekit', {}),
        ('spare_part', 'Reserveonderdeel', {'is_spare_part': True}),
    ], start=1):
        roles[key] = _xmlid(Role.create(dict(
            {'name': name, 'code': key, 'sequence': sequence * 10}, **extra)), 'role_%s' % key)

    Stage = env['project.task.type']
    stages = {key: Stage.create({'name': name, 'sequence': seq, 'fold': fold})
              for key, name, seq, fold in [('new', 'Nieuw', 1, False),
                                           ('planned', 'Ingepland', 2, False),
                                           ('done', 'Afgerond', 3, True)]}
    project = _xmlid(env['project.project'].create({
        'name': 'Interventies',
        'type_ids': [Command.set([s.id for s in stages.values()])],
    }), 'project_interventions')
    env['ir.config_parameter'].sudo().set_param(
        'serviq_installation.intervention_project_id', project.id)

    # Frisair installs its own installations
    company.partner_id.serviq_is_installer = True

    def itype(name):
        return env.ref('serviq_installation.intervention_type_%s' % name)

    return {
        'category': category, 'roles': roles, 'project': project,
        'stage_new': stages['new'], 'stage_planned': stages['planned'],
        'stage_done': stages['done'], 'installer': company.partner_id,
        'commissioning': itype('commissioning'), 'repair': itype('repair'),
        'maintenance': itype('maintenance'), 'replacement': itype('replacement'),
    }


# ---------------------------------------------------------------------------
# Partners
# ---------------------------------------------------------------------------

def _setup_partners(env):
    def country(code):
        return env.ref('base.%s' % code).id

    def company_partner(key, name, street, zip_code, city, code, email, **extra):
        partner = env['res.partner'].create(dict({
            'name': name, 'is_company': True, 'street': street, 'zip': zip_code,
            'city': city, 'country_id': country(code), 'email': email,
        }, **extra))
        return key, _xmlid(partner, 'partner_%s' % key)

    def person(key, name, street, zip_code, city, email, phone):
        partner = env['res.partner'].create({
            'name': name, 'street': street, 'zip': zip_code, 'city': city,
            'country_id': country('be'), 'email': email, 'phone': phone,
        })
        return key, _xmlid(partner, 'partner_%s' % key)

    return dict([
        # Suppliers
        company_partner('nordklima', 'Nordklima Distribution GmbH', 'Kältestrasse 12', '50829',
                        'Köln', 'de', 'orders@nordklima.example'),
        company_partner('techniparts', 'Techniparts Installatie NV', 'Noorderlaan 140', '2030',
                        'Antwerpen', 'be', 'verkoop@techniparts.example'),
        company_partner('koperklim', 'KoperKlim BV', 'Esp 210', '5633 AA',
                        'Eindhoven', 'nl', 'order@koperklim.example'),
        company_partner('klimaparts', 'Klimaparts Service NV', 'Skaldenstraat 61', '9042',
                        'Gent', 'be', 'service@klimaparts.example'),
        # Customers of the package sales
        person('claes', 'Familie Claes', 'Kessel-Dorp 27', '2560', 'Nijlen',
               'gert.claes@example.com', '+32 475 12 34 56'),
        person('vandenbroeck', 'Lien Van den Broeck', 'Adegemstraat 9', '2800', 'Mechelen',
               'lien.vandenbroeck@example.com', '+32 486 22 33 44'),
        company_partner('vanhoof', 'Bakkerij Van Hoof', 'Stationsstraat 54', '2570', 'Duffel', 'be',
                        'info@bakkerijvanhoof.example', phone='+32 15 31 22 10'),
        person('wouters', 'Sofie Wouters', 'Putsesteenweg 112', '2820', 'Bonheiden',
               'sofie.wouters@example.com', '+32 499 45 67 89'),
        company_partner('delinde', 'Dokterspraktijk De Linde', 'Tremelobaan 8', '3140',
                        'Keerbergen', 'be', 'praktijk@delinde.example', phone='+32 15 51 40 40'),
        person('janssens', 'Pieter Janssens', 'Mechelsesteenweg 301', '2860', 'Sint-Katelijne-Waver',
               'pieter.janssens@example.com', '+32 472 98 76 54'),
        person('maes', 'Elke Maes', 'Bergstraat 15', '2220', 'Heist-op-den-Berg',
               'elke.maes@example.com', '+32 468 11 22 33'),
        person('peeters', 'Thomas Peeters', 'Boomsesteenweg 77', '2840', 'Rumst',
               'thomas.peeters@example.com', '+32 494 55 66 77'),
        # Customers of the open orders
        person('verbruggen', 'Ann Verbruggen', 'Tervuursesteenweg 45', '3190', 'Boortmeerbeek',
               'ann.verbruggen@example.com', '+32 476 33 44 55'),
        company_partner('goossens', 'Notariskantoor Goossens', 'Kartuizersvest 3', '2500', 'Lier',
                        'be', 'kantoor@notarisgoossens.example', phone='+32 3 480 12 12'),
        person('desmet', 'Jan De Smet', 'Liersesteenweg 210', '2800', 'Mechelen',
               'jan.desmet@example.com', '+32 485 77 88 99'),
        # Customers with an older installation (before the demo history)
        person('mertens', 'Familie Mertens', 'Tisseltsesteenweg 19', '2830', 'Willebroek',
               'karen.mertens@example.com', '+32 478 21 43 65'),
        company_partner('lena', 'Kapsalon Lena', 'Bruul 88', '2800', 'Mechelen', 'be',
                        'hallo@kapsalonlena.example', phone='+32 15 20 30 40'),
        person('wuyts', 'Familie Wuyts', 'Grote Markt 6', '2500', 'Lier',
               'bart.wuyts@example.com', '+32 497 13 57 91'),
        company_partner('garage', 'Garage Peeters & Zn', 'Antwerpsesteenweg 400', '2630', 'Aartselaar',
                        'be', 'garage@peeterszn.example', phone='+32 3 877 66 55'),
        # Colleague installer buying units and spare parts
        company_partner('verhaegen', 'Koeltechniek Verhaegen', 'Ambachtenlaan 22', '3001', 'Leuven',
                        'be', 'bestel@verhaegen-koeltechniek.example', phone='+32 16 40 50 60'),
    ])


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------

def _setup_products(env, partners, serviq, wks, sqf):
    Category = env['product.category']
    root = Category.create({'name': 'Klimaattechniek'})
    cat_units = Category.create({'name': 'Airco-units', 'parent_id': root.id})
    cat_parts = Category.create({'name': 'Installatiemateriaal', 'parent_id': root.id})
    cat_kits = Category.create({'name': 'Montagekits', 'parent_id': root.id})
    cat_spare = Category.create({'name': 'Reserveonderdelen', 'parent_id': root.id})
    cat_packages = Category.create({'name': 'Installatiepakketten', 'parent_id': root.id})
    cat_services = Category.create({'name': 'Diensten', 'parent_id': root.id})

    route_buy = env.ref('purchase_stock.route_warehouse0_buy')
    route_manufacture = env.ref('mrp.route_warehouse0_manufacture')
    route_resupply = env['stock.route'].search([
        ('supplied_wh_id', '=', sqf.id), ('supplier_wh_id', '=', wks.id),
    ], limit=1)
    roles, category = serviq['roles'], serviq['category']

    def product(key, name, code, categ, cost, price, vendor=None, delay=0, weight=0.0,
                role=None, routes=None, **extra):
        vals = dict({
            'name': name,
            'default_code': code,
            'categ_id': categ.id,
            'type': 'consu',
            'is_storable': True,
            'standard_price': cost,
            'list_price': price,
            'weight': weight,
            'serviq_role_id': role.id if role else False,
            'route_ids': [Command.set(routes.ids)] if routes else False,
        }, **extra)
        if vendor:
            vals['seller_ids'] = [Command.create({
                'partner_id': vendor.id, 'price': cost, 'delay': delay, 'min_qty': 1,
            })]
        tmpl = _xmlid(env['product.template'].create(vals), 'product_%s' % key)
        return tmpl.product_variant_id

    # Airco units: serial-tracked, bought straight into the Stoqflow
    # warehouse; the serial numbers are registered on the receipt.
    units = {}
    for power, kw, out_cost, in_cost in [('25', '2,5', 520.0, 260.0),
                                         ('35', '3,5', 610.0, 290.0),
                                         ('50', '5,0', 840.0, 360.0)]:
        for side, role, label, cost, weight in [
            ('out', 'outdoor', 'buitenunit', out_cost, 32.0 + int(power) / 10),
            ('in', 'indoor', 'binnenunit wandmodel', in_cost, 9.0 + int(power) / 25),
        ]:
            key = '%s_%s' % (side, power)
            units[key] = product(
                key, 'Nordklima Aero %s %s kW' % (label, kw), 'NK-AERO-%s-%s' % (side.upper(), power),
                cat_units, cost, round(cost * 1.6, -1), partners['nordklima'], 21, weight,
                roles[role], route_buy, tracking='serial',
                description_sale='Split airco, koudemiddel R32, energieklasse A++',
            )
            units[key].product_tmpl_id.serviq_category_id = category

    # Parts of the mounting kits, bought into the workshop
    parts = {}
    for key, name, code, cost, vendor, delay, weight in [
        ('pipe_s', 'Koperleiding geïsoleerd 1/4"-3/8" (5 m)', 'KK-CU-1438-5', 38.0, 'koperklim', 10, 3.2),
        ('pipe_l', 'Koperleiding geïsoleerd 1/4"-1/2" (5 m)', 'KK-CU-1412-5', 46.0, 'koperklim', 10, 3.9),
        ('bracket', 'Muurbeugel buitenunit 450 mm', 'TP-MB-450', 22.0, 'techniparts', 5, 4.1),
        ('feet', 'Trillingsdempers buitenunit (set van 4)', 'TP-TD-4', 6.5, 'techniparts', 5, 0.6),
        ('drain', 'Condensafvoerslang 16 mm (5 m)', 'TP-CA-16-5', 4.8, 'techniparts', 5, 0.4),
        ('cable', 'Verbindingskabel 5G1,5 (5 m)', 'TP-KB-5G15-5', 9.9, 'techniparts', 5, 0.7),
        ('trunking', 'Leidinggoot 80 mm met bochten (set)', 'TP-LG-80', 18.5, 'techniparts', 5, 2.0),
    ]:
        parts[key] = product(key, name, code, cat_parts, cost, round(cost * 1.8, 2), partners[vendor],
                             delay, weight, routes=route_buy, sale_ok=False)

    # Mounting kits: assembled in the workshop, resupplied to Stoqflow
    kits = {}
    for key, name, code, price, pipe in [
        ('kit_s', 'Montagekit split 2,5-3,5 kW', 'FRW-MK-S', 249.0, 'pipe_s'),
        ('kit_l', 'Montagekit split 5,0 kW', 'FRW-MK-L', 289.0, 'pipe_l'),
    ]:
        kits[key] = product(
            key, name, code, cat_kits, 0.0, price, weight=11.5, role=roles['mounting_kit'],
            routes=route_manufacture | route_resupply, purchase_ok=False,
            description_sale='Samengesteld in onze werkplaats in Mechelen.',
        )
        bom = env['mrp.bom'].create({
            'product_tmpl_id': kits[key].product_tmpl_id.id,
            'product_qty': 1,
            'type': 'normal',
            'picking_type_id': wks.manu_type_id.id,
            'bom_line_ids': [
                Command.create({'product_id': parts[part].id, 'product_qty': 1})
                for part in (pipe, 'bracket', 'feet', 'drain', 'cable', 'trunking')
            ],
        })
        _xmlid(bom, 'bom_%s' % key)
        kits[key].product_tmpl_id.button_bom_cost()

    # Spare parts: kept in the workshop and the vans, never at Stoqflow
    spare = {}
    for key, name, code, cost, price, vendor, delay in [
        ('pcb', 'Printplaat binnenunit Aero', 'NK-SP-PCB-IN', 68.0, 145.0, 'nordklima', 14),
        ('fan_motor', 'Ventilatormotor buitenunit Aero', 'NK-SP-FAN-OUT', 92.0, 189.0, 'nordklima', 14),
        ('eev', 'Elektronisch expansieventiel Aero', 'NK-SP-EEV', 41.0, 95.0, 'nordklima', 14),
        ('remote', 'Afstandsbediening IR Aero', 'NK-SP-REMOTE', 14.0, 39.0, 'nordklima', 14),
        ('pump', 'Condenspomp mini', 'KP-CP-MINI', 48.0, 109.0, 'klimaparts', 3),
        ('ntc', 'Temperatuursensor NTC 10k', 'KP-NTC-10K', 6.0, 24.0, 'klimaparts', 3),
        ('filter', 'Filterset binnenunit Aero', 'KP-FLT-AERO', 7.5, 19.5, 'klimaparts', 3),
    ]:
        spare[key] = product(key, name, code, cat_spare, cost, price, partners[vendor], delay, 0.5,
                             roles['spare_part'], route_buy)

    # Installation packages: a kit BoM of an outdoor unit, an indoor unit and
    # a mounting kit. The delivery from Stoqflow holds the three components.
    packages = {}
    for power, kw, kit, price in [('25', '2,5', 'kit_s', 1690.0), ('35', '3,5', 'kit_s', 1890.0),
                                  ('50', '5,0', 'kit_l', 2390.0)]:
        key = 'package_%s' % power
        packages[power] = product(
            key, 'Installatiepakket split airco %s kW' % kw, 'FRW-PKG-%s' % power, cat_packages,
            0.0, price, role=roles['package'], is_storable=False, purchase_ok=False,
            serviq_category_id=category.id,
            description_sale='Buitenunit, binnenunit wandmodel en montagekit Nordklima Aero %s kW' % kw)
        bom = env['mrp.bom'].create({
            'product_tmpl_id': packages[power].product_tmpl_id.id,
            'product_qty': 1,
            'type': 'phantom',
            'bom_line_ids': [
                Command.create({'product_id': units['out_%s' % power].id, 'product_qty': 1}),
                Command.create({'product_id': units['in_%s' % power].id, 'product_qty': 1}),
                Command.create({'product_id': kits[kit].id, 'product_qty': 1}),
            ],
        })
        _xmlid(bom, 'bom_%s' % key)

    services = {}
    for key, name, code, price in [
        ('installation', 'Plaatsing split airco (forfait)', 'SRV-PLAATSING', 650.0),
        ('labour', 'Arbeid technieker (per uur)', 'SRV-ARBEID', 72.0),
        ('travel', 'Verplaatsing servicewagen', 'SRV-VERPL', 45.0),
    ]:
        services[key] = product(key, name, code, cat_services, 0.0, price, type='service',
                                is_storable=False, purchase_ok=False)

    return {
        'units': units, 'parts': parts, 'kits': kits, 'spare': spare,
        'packages': packages, 'services': services, 'route_resupply': route_resupply,
    }


# ---------------------------------------------------------------------------
# Airco units bought into the Stoqflow warehouse
# ---------------------------------------------------------------------------

def _run_unit_purchases(env, partners, products, sqf):
    units = products['units']
    nordklima = partners['nordklima']
    # Opening stock, received at Stoqflow with the serial numbers
    _purchase(env, nordklima, [
        (units['out_25'], 6), (units['in_25'], 6),
        (units['out_35'], 8), (units['in_35'], 8),
        (units['out_50'], 3), (units['in_50'], 3),
    ], sqf.in_type_id, days_ago=40, receive=True)
    _purchase(env, nordklima, [
        (units['out_35'], 6), (units['in_35'], 6),
        (units['out_25'], 4), (units['in_25'], 4),
    ], sqf.in_type_id, days_ago=16, receive=True)
    # On its way: still to be received at Stoqflow
    _purchase(env, nordklima, [
        (units['out_50'], 4), (units['in_50'], 4),
        (units['out_35'], 6), (units['in_35'], 6),
    ], sqf.in_type_id, days_ago=3)


# ---------------------------------------------------------------------------
# Mounting kits: parts bought into the workshop, assembled, resupplied
# ---------------------------------------------------------------------------

def _run_kit_assembly(env, partners, products, wks, sqf):
    parts, kits = products['parts'], products['kits']
    for vendor, lines in [
        ('koperklim', [('pipe_s', 30), ('pipe_l', 10)]),
        ('techniparts', [('bracket', 40), ('feet', 40), ('drain', 40), ('cable', 40), ('trunking', 40)]),
    ]:
        _purchase(env, partners[vendor], [(parts[k], q) for k, q in lines],
                  wks.in_type_id, days_ago=38, receive=True)
    # Reorder of copper pipe, still a request for quotation
    env['purchase.order'].create({
        'partner_id': partners['koperklim'].id,
        'user_id': env.ref('base.user_admin').id,
        'picking_type_id': wks.in_type_id.id,
        'order_line': [Command.create({'product_id': parts['pipe_s'].id, 'product_qty': 30})],
    })

    # Assembly in the workshop
    _manufacture(env, kits['kit_s'], 20, wks, days_ago=33, produce=True)
    _manufacture(env, kits['kit_l'], 8, wks, days_ago=32, produce=True)
    _manufacture(env, kits['kit_s'], 6, wks, days_ago=0)  # ready to produce

    # Resupply the Stoqflow warehouse: workshop -> transit -> Stoqflow
    route = products['route_resupply']
    _resupply(env, kits['kit_s'], 14, sqf, route, days_ago=30, receive=True)
    _resupply(env, kits['kit_l'], 6, sqf, route, days_ago=30, receive=True)
    # Shipped from the workshop, still to be received at Stoqflow
    _resupply(env, kits['kit_s'], 4, sqf, route, days_ago=1, receive=False)


def _resupply(env, product, qty, sqf, route, days_ago=0, receive=False):
    """Replenish the Stoqflow warehouse from the workshop. The workshop leg is
    always shipped; the receipt at Stoqflow is only done when receive=True."""
    # A one-off manual orderpoint drives the resupply route; Odoo removes it
    # again once it has nothing left to order.
    orderpoint = env['stock.warehouse.orderpoint'].create({
        'product_id': product.id, 'warehouse_id': sqf.id, 'location_id': sqf.lot_stock_id.id,
        'product_min_qty': 0, 'product_max_qty': 0, 'trigger': 'manual',
        'route_id': route.id, 'qty_to_order_manual': qty,
    })
    existing = env['stock.picking'].search([])
    orderpoint.action_replenish()
    orderpoint.exists().unlink()
    pickings = env['stock.picking'].search([('id', 'not in', existing.ids)])
    outgoing = pickings.filtered(lambda p: p.location_dest_id != sqf.lot_stock_id)
    incoming = pickings - outgoing
    for picking in outgoing:
        _validate(picking, _days_ago(days_ago))
    if receive:
        for picking in incoming:
            _validate(picking, _days_ago(max(days_ago - 1, 0)))


# ---------------------------------------------------------------------------
# Spare parts: workshop shelf, service vans, sales to a colleague installer
# ---------------------------------------------------------------------------

def _run_spare_parts(env, partners, products, wks, locations):
    spare = products['spare']
    shelf = locations['spare']
    _purchase(env, partners['nordklima'], [
        (spare['fan_motor'], 3), (spare['eev'], 3), (spare['remote'], 6),
    ], wks.in_type_id, days_ago=36, receive=True, location_dest=shelf)
    _purchase(env, partners['klimaparts'], [
        (spare['pump'], 6), (spare['ntc'], 12), (spare['filter'], 20),
    ], wks.in_type_id, days_ago=36, receive=True, location_dest=shelf)
    # Printed circuit boards on order, out of stock (a repair is waiting)
    _purchase(env, partners['nordklima'], [(spare['pcb'], 3)], wks.in_type_id, days_ago=2,
              location_dest=shelf)

    # Each service van carries a basic set
    for van in ('van_1', 'van_2'):
        _transfer(env, wks.int_type_id, shelf, locations[van], [
            (spare['pump'], 2), (spare['ntc'], 4), (spare['filter'], 4), (spare['remote'], 1),
        ], days_ago=34)

    # Colleague installer buying spare parts from the workshop
    _sell(env, partners['verhaegen'], [(spare['fan_motor'], 1), (spare['ntc'], 2)], wks,
          days_ago=11, deliver=True)
    _sell(env, partners['verhaegen'], [(spare['eev'], 1), (spare['filter'], 4)], wks, days_ago=0)


# ---------------------------------------------------------------------------
# Installation packages sold and delivered by Stoqflow -> installations
# ---------------------------------------------------------------------------

def _create_installation(env, serviq, customer, package, lots, note=None):
    """Installation of a package at `customer`, with the delivered serial
    numbers on its outdoor and indoor unit."""
    Installation = env['serviq.installation']
    lines = Installation._bom_line_commands(package.product_tmpl_id)
    for _c, _i, vals in lines:
        lot = lots.filtered(lambda l: l.product_id.product_tmpl_id.id == vals['product_tmpl_id'])[:1]
        if lot:
            vals['lot_id'] = lot.id
    installation = Installation.create({
        'product_tmpl_id': package.product_tmpl_id.id,
        'category_id': serviq['category'].id,
        'customer_id': customer.id,
        'installer_id': serviq['installer'].id,
        'contact_person_name': customer.name,
        'contact_person_phone': customer.phone,
        'note': note or False,
        'line_ids': lines,
    })
    # Unit serials point back to the installation (lookup from the serial)
    installation.line_ids.lot_id.serviq_installation_id = installation
    return installation


def _run_package_sales(env, partners, products, serviq, sqf):
    """Packages sold to end customers and delivered by Stoqflow on the
    installation day. Each delivered package becomes an installation with
    the serials of the delivery, and gets its commissioning: done for the
    older ones, planned or still to plan for the most recent ones."""
    packages, installation_service = products['packages'], products['services']['installation']
    installations = {}
    # key, customer, package power, quantity, days ago, commissioning
    # (days relative to today, None: not planned yet)
    for key, customer, power, qty, days_ago, commissioning in [
        ('claes', 'claes', '35', 1, 27, -26),
        ('vandenbroeck', 'vandenbroeck', '25', 2, 24, -23),
        ('vanhoof', 'vanhoof', '50', 1, 21, -20),
        ('wouters', 'wouters', '35', 1, 17, -16),
        ('delinde', 'delinde', '35', 1, 13, -12),
        ('janssens', 'janssens', '25', 1, 9, -8),
        ('maes', 'maes', '50', 1, 5, 3),
        ('peeters', 'peeters', '35', 1, 2, None),
    ]:
        package = packages[power]
        so = _sell(env, partners[customer], [(package, qty), (installation_service, qty)], sqf,
                   days_ago=days_ago, deliver=True)
        lots = so.picking_ids.move_line_ids.lot_id
        for unit in range(qty):
            unit_lots = env['stock.lot']
            for product in lots.product_id:
                unit_lots |= lots.filtered(lambda l: l.product_id == product)[unit]
            installation = _create_installation(env, serviq, partners[customer], package, unit_lots)
            done = commissioning is not None and commissioning < 0
            _task(env, serviq, installation, serviq['commissioning'], commissioning, done=done)
            installations[key if not unit else '%s_%s' % (key, unit + 1)] = installation
    return installations


def _setup_older_installations(env, partners, products, serviq):
    """Installations placed before the demo history (no documents): their
    units are at the customer with a serial number, out of warranty."""
    Lot = env['stock.lot']
    Quant = env['stock.quant']
    customers_location = env.ref('stock.stock_location_customers')
    installations = {}
    for key, power, year in [('mertens', '35', 2021), ('lena', '25', 2020),
                             ('wuyts', '50', 2022), ('garage', '25', 2019)]:
        lots = Lot
        for side in ('out', 'in'):
            product = products['units']['%s_%s' % (side, power)]
            lot = Lot.create({
                'name': _next_serial(product, fields.Date.from_string('%s-05-01' % year)),
                'product_id': product.id,
            })
            Quant._update_available_quantity(product, customers_location, 1.0, lot_id=lot)
            lots |= lot
        installation = _create_installation(
            env, serviq, partners[key], products['packages'][power], lots,
            note='<p>Geplaatst in %s, voor de overstap naar Odoo. Garantie verlopen.</p>' % year)
        installation.state = 'active'
        installations[key] = installation

    # Periodic maintenance on the older installations
    _task(env, serviq, installations['garage'], serviq['maintenance'], -40, done=True,
          description='<p>Jaarlijks onderhoud: filters gereinigd, lekdichtheid gecontroleerd.</p>')
    _task(env, serviq, installations['lena'], serviq['maintenance'], 10,
          description='<p>Jaarlijks onderhoud en controle koudemiddel.</p>')
    _task(env, serviq, installations['wuyts'], serviq['maintenance'], 25)
    return installations


# ---------------------------------------------------------------------------
# Open orders, still waiting to be delivered by Stoqflow
# ---------------------------------------------------------------------------

def _run_open_orders(env, partners, products, sqf):
    packages, units = products['packages'], products['units']
    installation_service = products['services']['installation']
    _sell(env, partners['verbruggen'], [(packages['35'], 1), (installation_service, 1)], sqf, days_ago=1)
    _sell(env, partners['goossens'], [
        (packages['50'], 1), (packages['25'], 1), (installation_service, 2),
    ], sqf, days_ago=0)
    # Loose units for a colleague installer, shipped by Stoqflow
    _sell(env, partners['verhaegen'], [(units['out_35'], 2), (units['in_35'], 2)], sqf, days_ago=0)
    # Quotation not yet confirmed
    _sell(env, partners['desmet'], [(packages['35'], 1), (installation_service, 1)], sqf,
          confirm=False)


# ---------------------------------------------------------------------------
# Repairs on installed units, found by serial number
# ---------------------------------------------------------------------------

def _run_repairs(env, partners, products, serviq, wks, locations, installations):
    spare, services = products['spare'], products['services']
    admin = env.ref('base.user_admin')
    Tag = env['repair.tags']
    tags = {key: Tag.create({'name': name}) for key, name in [
        ('warranty', 'Garantie'), ('paid', 'Betalend'), ('on_site', 'Op locatie')]}

    def unit_lot(installation, side):
        """Serial of the outdoor ('out') or indoor ('in') unit."""
        role = serviq['roles']['outdoor' if side == 'out' else 'indoor']
        return installation.line_ids.filtered(lambda l: l.role_id == role).lot_id

    def repair(key, installation, side, description, days_ago, warranty, parts_location,
               add=(), remove=(), priority='0'):
        lot = unit_lot(installation, side)
        ro = env['repair.order'].create({
            'product_id': lot.product_id.id,
            'lot_id': lot.id,
            'partner_id': installation.customer_id.id,
            'user_id': admin.id,
            # On-site repair (see the operation type): the unit stays at
            # the customer, the parts come from `parts_location`.
            'picking_type_id': wks.repair_type_id.id,
            'location_id': parts_location.id,
            'under_warranty': warranty,
            'priority': priority,
            'schedule_date': _days_ago(days_ago),
            'internal_notes': description,
            'tag_ids': [Command.set((tags['warranty' if warranty else 'paid'] | tags['on_site']).ids)],
            'move_ids': [Command.create({
                'product_id': product.id, 'product_uom_qty': qty, 'repair_line_type': 'add',
            }) for product, qty in add] + [Command.create({
                'product_id': product.id, 'product_uom_qty': qty, 'repair_line_type': 'remove',
            }) for product, qty in remove],
        })
        return _xmlid(ro, 'repair_%s' % key)

    def quotation(ro, hours, confirm=False):
        """Sales order of a paid repair: the parts plus labour and travel."""
        ro.action_create_sale_order()
        so = ro.sale_order_id
        so.user_id = admin
        so.write({'order_line': [
            Command.create({'product_id': services['labour'].id, 'product_uom_qty': hours}),
            Command.create({'product_id': services['travel'].id, 'product_uom_qty': 1}),
        ]})
        if confirm:
            so.action_confirm()
        return so

    def finish(ro, days_ago):
        ro.action_validate()
        ro.action_repair_start()
        for move in ro.move_ids:
            move.quantity = move.product_uom_qty
        ro.move_ids.picked = True
        ro.action_repair_end()
        ro.move_ids.date = _days_ago(days_ago)
        ro.move_id.date = _days_ago(days_ago)

    def activity(ro, xmlid, days, summary, note=''):
        ro.activity_schedule(xmlid, date_deadline=fields.Date.today() + timedelta(days=days),
                             summary=summary, note=note, user_id=admin.id)

    # 1. Warranty, repaired: leaking indoor unit, condensate pump replaced
    #    with one from the van.
    claes = installations['claes']
    ro = repair('claes_pump', claes, 'in',
                '<p>Binnenunit lekt condenswater langs de muur. Condenspomp defect, vervangen '
                'uit servicewagen 1.</p>', 7, True, locations['van_1'], add=[(spare['pump'], 1)])
    finish(ro, 6)
    _task(env, serviq, claes, serviq['repair'], -6, done=True,
          description='<p>Herstelling %s: condenspomp vervangen onder garantie.</p>' % ro.name)

    # 2. Warranty, under repair: outdoor unit trips with error E7, fan motor
    #    swapped from the workshop shelf; the defective motor goes to scrap.
    vanhoof = installations['vanhoof']
    ro = repair('vanhoof_fan', vanhoof, 'out',
                '<p>Buitenunit valt uit met foutcode E7 (ventilator). Ventilatormotor vervangen, '
                'defecte motor terug naar Nordklima voor garantieclaim.</p>', 1, True,
                locations['spare'], add=[(spare['fan_motor'], 1)], remove=[(spare['fan_motor'], 1)],
                priority='1')
    ro.action_validate()
    ro.action_repair_start()
    activity(ro, 'mail.mail_activity_data_call', 1, 'Klant bellen na testrun',
             'Werking koeling controleren met de bakker na een volle productiedag.')
    activity(ro, 'mail.mail_activity_data_todo', 5, 'Garantieclaim indienen bij Nordklima',
             'Serienummer van de unit en foto van de defecte motor meesturen.')
    _task(env, serviq, vanhoof, serviq['repair'], 1,
          description='<p>Herstelling %s: testrun na vervanging ventilatormotor.</p>' % ro.name)

    # 3. Paid, confirmed: printed circuit board of an older indoor unit,
    #    accepted by the customer, waiting for the board on order.
    mertens = installations['mertens']
    ro = repair('mertens_pcb', mertens, 'in',
                '<p>Binnenunit start niet meer, display knippert. Printplaat defect. Buiten '
                'garantie (2021): offerte aanvaard door de klant.</p>', 0, False,
                locations['spare'], add=[(spare['pcb'], 1)])
    quotation(ro, 1.5, confirm=True)
    ro.action_validate()
    ro.schedule_date = fields.Datetime.now() + timedelta(days=13)
    activity(ro, 'mail.mail_activity_data_todo', 3, 'Levering printplaat opvolgen',
             'Printplaat besteld bij Nordklima; bij ontvangst het bezoek bevestigen.')
    _task(env, serviq, mertens, serviq['repair'], 13,
          description='<p>Herstelling %s: printplaat binnenunit vervangen.</p>' % ro.name)

    # 4. Paid, repaired: faulty temperature sensor, replaced from van 2,
    #    invoiced through the sales order.
    lena = installations['lena']
    ro = repair('lena_ntc', lena, 'in',
                '<p>Binnenunit koelt onregelmatig. Temperatuursensor (NTC) defect, vervangen uit '
                'servicewagen 2.</p>', 9, False, locations['van_2'], add=[(spare['ntc'], 1)])
    quotation(ro, 1.0, confirm=True)
    finish(ro, 8)
    _task(env, serviq, lena, serviq['repair'], -8, done=True,
          description='<p>Herstelling %s: temperatuursensor vervangen.</p>' % ro.name)

    # 5. Paid, new: noisy outdoor unit, quotation sent and to follow up.
    wuyts = installations['wuyts']
    ro = repair('wuyts_noise', wuyts, 'out',
                '<p>Buitenunit maakt veel lawaai bij opstart. Vermoedelijk versleten '
                'expansieventiel. Offerte verstuurd.</p>', 0, False,
                locations['spare'], add=[(spare['eev'], 1)])
    quotation(ro, 2.5).action_quotation_sent()
    activity(ro, 'mail.mail_activity_data_call', 3, 'Offerte opvolgen',
             'Klant bellen als de offerte nog niet aanvaard is.')

    # 6. Warranty, new: remote control not responding, visit to be planned.
    janssens = installations['janssens']
    ro = repair('janssens_remote', janssens, 'in',
                '<p>Afstandsbediening reageert niet meer, ook niet met nieuwe batterijen.</p>', 0,
                True, locations['van_1'], add=[(spare['remote'], 1)])
    activity(ro, 'mail.mail_activity_data_todo', 0, 'Bezoek inplannen',
             'Combineren met een andere interventie in de buurt.')
    _task(env, serviq, janssens, serviq['repair'], None,
          description='<p>Herstelling %s: afstandsbediening.</p>' % ro.name)

    # 7. Paid, cancelled: the customer chose a new unit over repairing the
    #    old one.
    garage = installations['garage']
    ro = repair('garage_compressor', garage, 'out',
                '<p>Compressor buitenunit defect (2019). Herstelling niet rendabel: klant kiest '
                'voor een nieuw installatiepakket.</p>', 12, False, locations['spare'])
    ro.action_repair_cancel()
    _task(env, serviq, garage, serviq['replacement'], 9,
          description='<p>Vervanging van de installatie na herstelling %s (geannuleerd).</p>'
          % ro.name)


# ---------------------------------------------------------------------------
# Replenishment rules
# ---------------------------------------------------------------------------

def _setup_orderpoints(env, products, wks, sqf):
    """Replenishment rules with a manual trigger: they show up in the
    replenishment report but do not create orders by themselves."""
    Orderpoint = env['stock.warehouse.orderpoint']
    route_buy = env.ref('purchase_stock.route_warehouse0_buy')
    for product in products['units'].values():
        Orderpoint.create({
            'product_id': product.id, 'warehouse_id': sqf.id, 'location_id': sqf.lot_stock_id.id,
            'product_min_qty': 3, 'product_max_qty': 10, 'trigger': 'manual',
            'route_id': route_buy.id,
        })
    for product in products['kits'].values():
        Orderpoint.create({
            'product_id': product.id, 'warehouse_id': sqf.id, 'location_id': sqf.lot_stock_id.id,
            'product_min_qty': 4, 'product_max_qty': 12, 'trigger': 'manual',
            'route_id': products['route_resupply'].id,
        })
    for product in list(products['parts'].values()) + list(products['spare'].values()):
        Orderpoint.create({
            'product_id': product.id, 'warehouse_id': wks.id, 'location_id': wks.lot_stock_id.id,
            'product_min_qty': 2, 'product_max_qty': 10, 'trigger': 'manual',
            'route_id': route_buy.id,
        })
