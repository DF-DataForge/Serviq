# -*- coding: utf-8 -*-
{
    'name': 'DF Connects: Van Marcke',
    'version': '19.0.1.0.0',
    'summary': 'Koppeling met de API van Van Marcke: producten, nettoprijzen '
               'en voorraad (centraal magazijn en winkels)',
    'description': """
Van Marcke connector for DF Connects, on the Van Marcke APIs
(https://vanmarcke.atlassian.net/wiki/spaces/VMI):

* OAuth 2.0 against https://api.vanmarcke.com/v1/oauth/token (test:
  https://api-test.vanmarcke.com): Resource Owner Password with a service
  user (customer specific net prices) or Client Credentials (generic
  prices), client id / secret as basic authentication; tokens are cached
  and refreshed, the Application Key is sent as "x-api-key" on every call.
* Products API v2: product ids from the vendor pricelist of Van Marcke,
  from a list, or from the catalog listing (GET /v2/products); details
  (POST /bulk/detail) and net price and central stock
  (POST /bulk/pricesAndStock) per 50 products; optionally the stock of
  selected stores (GET /{productId}/stock/{storeId}).
* Stores API v1: store list to create the entities (stores) whose stock is
  fetched.
* Respects the rate limit (1 call per 20 ms) and retries on 429.

The field paths in the JSON responses are configurable on the connection:
check them against the API specification in the Van Marcke developer
portal and with "Ruwe gegevens bewaren".
""",
    'category': 'Supply Chain',
    'author': 'Data Forge',
    'website': 'https://www.data-forge.be',
    'depends': ['df_connects'],
    'data': [
        'views/connection_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
