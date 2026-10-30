from odoo import models, api
from .labels import product_type, segment_domain
from .dashboard_access import check_dashboard_access


class StockDashboard(models.AbstractModel):
    _name = 'serviq.logistics.stock'
    _description = 'Logistiek: voorraadoverzicht'

    @api.model
    def get_dashboard_data(self, stock_type, search_term=None, subgroup=None):
        """Return stock data grouped by product for the given stock type.

        Args:
            stock_type: 'own', 'consignment', or 'customer'
            search_term: optional product name filter
            subgroup: segment (installation category code) or 'all'

        Returns:
            list of dicts with product info and serial number details
        """
        check_dashboard_access(self.env, 'stock')
        Quant = self.env['stock.quant'].sudo()
        domain = [('quantity', '>', 0)]

        company = self.env.company

        if stock_type == 'own':
            # Stock in internal locations with no external owner
            domain += [
                ('location_id.usage', '=', 'internal'),
                '|',
                ('owner_id', '=', False),
                ('owner_id', '=', company.partner_id.id),
            ]
        elif stock_type == 'consignment':
            # Stock in internal locations owned by an external partner
            domain += [
                ('location_id.usage', '=', 'internal'),
                ('owner_id', '!=', False),
                ('owner_id', '!=', company.partner_id.id),
            ]
        elif stock_type == 'customer':
            # Stock in customer locations (allocated to distributors)
            domain += [
                ('location_id.usage', '=', 'customer'),
            ]

        if search_term:
            domain += [('product_id.name', 'ilike', search_term)]
        domain += segment_domain(subgroup)

        quants = Quant.search(domain)

        # Group by product
        product_map = {}
        for quant in quants:
            product = quant.product_id
            pid = product.id
            if pid not in product_map:
                product_map[pid] = {
                    'product_id': pid,
                    'product_name': product.display_name,
                    'product_type': product_type(product),
                    'default_code': product.default_code or '',
                    'uom': product.uom_id.name,
                    'total_qty': 0.0,
                    'reserved_qty': 0.0,
                    'serial_numbers': [],
                    'locations': {},
                }
            entry = product_map[pid]
            entry['total_qty'] += quant.quantity
            entry['reserved_qty'] += quant.reserved_quantity

            # Track location breakdown
            loc_name = quant.location_id.complete_name
            if stock_type == 'customer' and quant.location_id.partner_id:
                loc_name = quant.location_id.partner_id.name
            if loc_name not in entry['locations']:
                entry['locations'][loc_name] = 0.0
            entry['locations'][loc_name] += quant.quantity

            # Collect serial numbers if tracked
            if quant.lot_id:
                owner_name = quant.owner_id.name if quant.owner_id else ''
                entry['serial_numbers'].append({
                    'lot_id': quant.lot_id.id,
                    'lot_name': quant.lot_id.name,
                    'quantity': quant.quantity,
                    'location': quant.location_id.complete_name,
                    'location_id': quant.location_id.id,
                    'owner': owner_name,
                    'partner': quant.location_id.partner_id.name if quant.location_id.partner_id else '',
                })

        # Convert locations dict to list and sort results
        result = []
        for entry in product_map.values():
            entry['locations'] = [
                {'name': k, 'qty': v}
                for k, v in sorted(entry['locations'].items())
            ]
            entry['serial_count'] = len(entry['serial_numbers'])
            result.append(entry)

        result.sort(key=lambda x: x['product_name'])
        return result

    @api.model
    def get_dashboard_data_by_location(self, stock_type, search_term=None, subgroup=None):
        """Return stock data grouped by location for the given stock type.

        Args:
            stock_type: 'own', 'consignment', or 'customer'
            search_term: optional location/product name filter

        Returns:
            list of dicts with location info, products and serial numbers
        """
        check_dashboard_access(self.env, 'stock')
        Quant = self.env['stock.quant'].sudo()
        domain = [('quantity', '>', 0)]

        company = self.env.company

        if stock_type == 'own':
            domain += [
                ('location_id.usage', '=', 'internal'),
                '|',
                ('owner_id', '=', False),
                ('owner_id', '=', company.partner_id.id),
            ]
        elif stock_type == 'consignment':
            domain += [
                ('location_id.usage', '=', 'internal'),
                ('owner_id', '!=', False),
                ('owner_id', '!=', company.partner_id.id),
            ]
        elif stock_type == 'customer':
            domain += [
                ('location_id.usage', '=', 'customer'),
            ]

        if search_term:
            domain += [
                '|',
                ('product_id.name', 'ilike', search_term),
                ('location_id.complete_name', 'ilike', search_term),
            ]
        domain += segment_domain(subgroup)

        quants = Quant.search(domain)
        main_warehouse = self.env['stock.warehouse'].sudo().search(
            [('company_id', '=', company.id)], order='sequence, id', limit=1)

        # Group by location
        location_map = {}
        for quant in quants:
            loc = quant.location_id
            lid = loc.id
            if lid not in location_map:
                loc_label = loc.complete_name
                if stock_type == 'customer' and loc.partner_id:
                    loc_label = loc.partner_id.name
                location_map[lid] = {
                    'location_id': lid,
                    'location_name': loc_label,
                    'location_full': loc.complete_name,
                    'partner': loc.partner_id.name if loc.partner_id else '',
                    **self._location_grouping(loc, main_warehouse),
                    'total_qty': 0.0,
                    'product_count': 0,
                    'serial_count': 0,
                    'products': {},
                }
            entry = location_map[lid]
            entry['total_qty'] += quant.quantity

            # Group products within location
            product = quant.product_id
            pid = product.id
            if pid not in entry['products']:
                entry['products'][pid] = {
                    'product_id': pid,
                    'product_name': product.display_name,
                    'product_type': product_type(product),
                    'default_code': product.default_code or '',
                    'uom': product.uom_id.name,
                    'qty': 0.0,
                    'serial_numbers': [],
                }
            prod_entry = entry['products'][pid]
            prod_entry['qty'] += quant.quantity

            if quant.lot_id:
                prod_entry['serial_numbers'].append({
                    'lot_id': quant.lot_id.id,
                    'lot_name': quant.lot_id.name,
                    'quantity': quant.quantity,
                    'owner': quant.owner_id.name if quant.owner_id else '',
                })

        # Convert products dict to sorted list
        result = []
        for entry in location_map.values():
            products_list = sorted(
                entry['products'].values(),
                key=lambda x: x['product_name']
            )
            entry['product_count'] = len(products_list)
            entry['serial_count'] = sum(
                len(p['serial_numbers']) for p in products_list
            )
            entry['products'] = products_list
            result.append(entry)

        result.sort(key=lambda x: x['location_name'])
        return result

    @staticmethod
    def _location_grouping(loc, main_warehouse):
        """Warehouse and aisle ("gang") of a location, for the location
        cards. The aisle is the location directly under the warehouse's
        stock location (WH/Stock/G1 for WH/Stock/G1/A/M1-1/1); the stock
        location itself and the locations outside it (WH/Input,
        WH/Repair/...) are grouped under their own first level below the
        warehouse. Locations without a warehouse (customers) stand alone."""
        warehouse = loc.warehouse_id
        path = [int(x) for x in (loc.parent_path or '').split('/') if x]
        group_id, is_aisle, is_stock = loc.id, False, False
        if warehouse:
            stock_id = warehouse.lot_stock_id.id
            view_id = warehouse.view_location_id.id
            if stock_id in path and loc.id != stock_id:
                group_id, is_aisle = path[path.index(stock_id) + 1], True
            elif view_id in path and loc.id != view_id:
                group_id = path[path.index(view_id) + 1]
            is_stock = group_id == stock_id
        group = loc.browse(group_id) if group_id != loc.id else loc
        return {
            'warehouse_id': warehouse.id or False,
            'warehouse_name': warehouse.name or '',
            'warehouse_code': warehouse.code or '',
            'is_main_warehouse': bool(warehouse) and warehouse == main_warehouse,
            'group_id': group.id,
            'group_name': group.complete_name,
            'group_short': group.name,
            'group_is_aisle': is_aisle,
            'group_is_stock': is_stock,
        }

    @api.model
    def get_dashboard_summary(self, subgroup=None):
        """Return summary counts for all three stock types."""
        check_dashboard_access(self.env, 'stock')
        Quant = self.env['stock.quant'].sudo()
        company = self.env.company

        own_domain = [
            ('quantity', '>', 0),
            ('location_id.usage', '=', 'internal'),
            '|',
            ('owner_id', '=', False),
            ('owner_id', '=', company.partner_id.id),
        ]
        consignment_domain = [
            ('quantity', '>', 0),
            ('location_id.usage', '=', 'internal'),
            ('owner_id', '!=', False),
            ('owner_id', '!=', company.partner_id.id),
        ]
        customer_domain = [
            ('quantity', '>', 0),
            ('location_id.usage', '=', 'customer'),
        ]

        subgroup_domain = segment_domain(subgroup)
        own_domain += subgroup_domain
        consignment_domain += subgroup_domain
        customer_domain += subgroup_domain

        own_quants = Quant.search(own_domain)
        consignment_quants = Quant.search(consignment_domain)
        customer_quants = Quant.search(customer_domain)

        return {
            'own': {
                'total_qty': sum(own_quants.mapped('quantity')),
                'product_count': len(set(own_quants.mapped('product_id.id'))),
                'serial_count': len(set(own_quants.filtered('lot_id').mapped('lot_id.id'))),
            },
            'consignment': {
                'total_qty': sum(consignment_quants.mapped('quantity')),
                'product_count': len(set(consignment_quants.mapped('product_id.id'))),
                'serial_count': len(set(consignment_quants.filtered('lot_id').mapped('lot_id.id'))),
            },
            'customer': {
                'total_qty': sum(customer_quants.mapped('quantity')),
                'product_count': len(set(customer_quants.mapped('product_id.id'))),
                'serial_count': len(set(customer_quants.filtered('lot_id').mapped('lot_id.id'))),
            },
        }
