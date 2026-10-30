# -*- coding: utf-8 -*-
{
    'name': 'Serviq Installaties: kaart',
    'version': '19.0.1.0.0',
    'summary': 'Locatie en kaart van de installaties: op de installatie, '
               'op het overzicht en als volledige kaart',
    'description': """
Map of the Serviq installations, on Odoo Community (Leaflet, no Enterprise
map view needed).

* Location of an installation: an address of the customer (the customer by
  default) with its coordinates, looked up from the address (base
  geolocalize) or set by clicking on the map / dragging the marker.
* Map on the installation form.
* Map panel on the overview dashboard and a full page map
  (Installaties > Kaart): a marker per installation in the colour of its
  status, base information on hover, legend to filter on status, link to
  the installations without location.
* Tile server configurable in the settings (OpenStreetMap by default).

Installed automatically with Serviq Installaties; can be uninstalled.
""",
    'category': 'Services',
    'author': 'Data Forge',
    'website': 'https://www.data-forge.be',
    'depends': ['serviq_installation', 'base_geolocalize'],
    'auto_install': ['serviq_installation'],
    'data': [
        'views/installation_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'serviq_installation_map/static/src/css/installation_map.css',
            'serviq_installation_map/static/src/js/leaflet_loader.js',
            'serviq_installation_map/static/src/js/installation_map.js',
            'serviq_installation_map/static/src/js/location_widget.js',
            'serviq_installation_map/static/src/xml/installation_map.xml',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
