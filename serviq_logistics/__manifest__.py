{
    'name': 'Serviq Logistiek',
    'version': '19.0.1.0.0',
    'summary': 'Logistieke dashboards: voorraad, serienummers, inkomende en uitgaande goederen, reserveonderdelen',
    'description': """
        Operational dashboards for the logistics of installations:

        - Overzicht: landing page with the KPI tiles of every dashboard
        - Voorraadoverzicht: own, consignment and customer stock tabs
          (per product type, product or location), with Excel export
        - Beschikbare voorraad: own stock as cards per product type, live
          or at the end of a past month
        - Serienummers: serial-tracked products split over ordered items,
          in-house stock and customer stock, with reservation and
          installation status
        - Inkomende goederen: POs grouped by supplier with reception status
        - Uitgaande goederen: SOs grouped by customer with delivery status
        - Reserveonderdelen: deliveries of spare parts (component role
          "Reserveonderdeel") per client, with shipping-list Excel export,
          optionally limited to some suppliers (Voorraad > Instellingen)

        Segments (installation categories) and product types (component
        roles) come from Serviq Installaties. Access per dashboard is set
        per user with the checkboxes on the user form.
    """,
    'category': 'Inventory',
    'author': 'Data Forge',
    'website': 'https://www.data-forge.be',
    'depends': ['stock', 'stock_account', 'stock_delivery', 'purchase', 'sale_management',
                'serviq_installation'],
    'data': [
        'security/dashboard_groups.xml',
        'security/ir.model.access.csv',
        'views/dashboard_views.xml',
        'views/res_users_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'serviq_logistics/static/src/css/stock_dashboard.css',
            'serviq_logistics/static/src/css/goods_dashboard.css',
            'serviq_logistics/static/src/css/sn_tracking_dashboard.css',
            'serviq_logistics/static/src/css/home_dashboard.css',
            'serviq_logistics/static/src/css/stock_cards.css',
            'serviq_logistics/static/src/js/filter_options.js',
            'serviq_logistics/static/src/js/subgroup_filter.js',
            'serviq_logistics/static/src/js/period_filter.js',
            'serviq_logistics/static/src/js/product_types.js',
            'serviq_logistics/static/src/js/home_dashboard.js',
            'serviq_logistics/static/src/js/stock_cards.js',
            'serviq_logistics/static/src/js/stock_dashboard.js',
            'serviq_logistics/static/src/js/sn_tracking_dashboard.js',
            'serviq_logistics/static/src/js/incoming_dashboard.js',
            'serviq_logistics/static/src/js/outgoing_dashboard.js',
            'serviq_logistics/static/src/js/spare_parts_dashboard.js',
            'serviq_logistics/static/src/xml/product_types.xml',
            'serviq_logistics/static/src/xml/home_dashboard.xml',
            'serviq_logistics/static/src/xml/stock_dashboard.xml',
            'serviq_logistics/static/src/xml/stock_cards.xml',
            'serviq_logistics/static/src/xml/sn_tracking_dashboard.xml',
            'serviq_logistics/static/src/xml/incoming_dashboard.xml',
            'serviq_logistics/static/src/xml/outgoing_dashboard.xml',
            'serviq_logistics/static/src/xml/spare_parts_dashboard.xml',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
