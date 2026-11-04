# DF Connects: leverancierskoppelingen

Onafhankelijke Odoo 19-module (hangt enkel af van `product` en `mail`) die
koppelingen met externe leveranciers opzet en via hun API de productgegevens
ophaalt. Werkt met of zonder de Serviq-modules.

## Wat wordt opgehaald

| Gegeven | Veld | Opmerking |
|---|---|---|
| UUID | `uuid` | De **EAN / GTIN** als de leverancier een geldige geeft (controlecijfer gecontroleerd, UPC-A en GTIN-14 met voorloopnul worden EAN-13). Anders de leveranciersproductcode, voorafgegaan door de leverancier: `S<partner id>-<code>`. Dezelfde EAN bij twee leveranciers geeft dus dezelfde UUID, zodat het aanbod van alle leveranciers van één artikel te vergelijken is. |
| Leveranciersproductcode | `supplier_code` | |
| Prijs | `price` + `currency_id` | Munt uit de API of die van de koppeling. Decimale komma en punt worden herkend. |
| Beschikbare hoeveelheid | `stock_ids` / `quantity_total` | Per **entiteit** van de leverancier (magazijn, vestiging of dochterbedrijf) en het totaal. Entiteiten worden automatisch aangemaakt uit de codes die de API teruggeeft. |

## Modellen

- `df.connects.connection`: de koppeling: leverancier, bedrijf, URL,
  authenticatie (API-sleutel in header of parameter, bearer-token, basic),
  paginering (geen, paginanummer, offset, link naar volgende pagina), extra
  parameters/headers/body en de **veldkoppeling** (paden in de JSON).
- `df.connects.supplier.product`: het product zoals de leverancier het aanbiedt.
- `df.connects.supplier.entity`: entiteit van de leverancier die voorraad heeft.
- `df.connects.supplier.stock`: beschikbare hoeveelheid per product en entiteit.
- `df.connects.sync.log`: historiek van de synchronisaties.

## Veldkoppeling

Paden in het JSON-antwoord: sleutels gescheiden door een punt, lijstindexen
tussen haken of als getal (`data.items`, `prices[0].amount`). Meerdere
alternatieven met `|` (`ean|gtin|barcode`): het eerste gevonden veld telt.

Voorraad per entiteit kan als lijst of als object:

```json
{"sku": "A-1", "ean": "5410013108009", "price": 12.5,
 "stock": [{"warehouse": "BE", "quantity": 4}, {"warehouse": "NL", "quantity": 6}]}
{"sku": "A-1", "stock": {"BE": 4, "NL": 6}}
{"sku": "A-1", "quantity": 10}
```

Het laatste geval (enkel een totaal) komt in een standaardentiteit met de
naam van de leverancier.

Naast de hoeveelheid heeft elke voorraadlijn **Op voorraad**: standaard
"hoeveelheid > 0", maar een koppeling kan het zelf zetten voor leveranciers
die enkel aangeven óf er voorraad is (zoals het centrale magazijn van Van
Marcke).

## Synchronisatie

- **Nu synchroniseren** op de koppeling, of automatisch: per koppeling een
  interval; een cron (elk uur) synchroniseert de koppelingen die aan de beurt
  zijn. Een fout wordt gelogd op de koppeling, de andere koppelingen gaan door.
- **Verbinding testen** leest de eerste producten en toont wat er gevonden
  werd, zonder iets op te slaan.
- Opties: koppelen aan Odoo-producten (barcode = EAN, of de
  leveranciersproductcode in de leveranciersprijslijst), de
  leveranciersprijslijst bijwerken (code en prijs), producten die de API niet
  meer teruggeeft archiveren, de ruwe JSON bewaren om de koppeling na te kijken.
- Op het productformulier toont een knop de hoeveelheid die bij de
  leveranciers beschikbaar is.

## Rechten

Groepen *Leverancierskoppelingen / Gebruiker* (raadplegen, synchronisatie
starten) en *Beheerder* (koppelingen en API-sleutels instellen). Multi-company
via het bedrijf van de koppeling.

## Een leverancierspecifieke koppeling toevoegen

Als de generieke veldkoppeling niet volstaat (eigen aanmelding, meerdere
oproepen per product, ...), maak een kleine module die afhangt van
`df_connects`, zoals `df_connects_vanmarcke`:

```python
class DfConnectsConnection(models.Model):
    _inherit = 'df.connects.connection'

    connector_type = fields.Selection(
        selection_add=[('mijnleverancier', 'Mijn leverancier')],
        ondelete={'mijnleverancier': 'set default'})

    def _fetch_records_mijnleverancier(self):
        # yield één dict per product
        ...

    # optioneel: eigen parsing in plaats van de veldkoppeling; geef
    # {'ean', 'code', 'name', 'price', 'currency',
    #  'stock': [(entiteitscode, entiteitsnaam, hoeveelheid[, op voorraad])]}
    def _parse_record_mijnleverancier(self, raw):
        ...
```

Haken: `_get_url`, `_get_request_auth` (headers, parameters, auth),
`_send_request` (opnieuw proberen bij verlopen token of rate limit) en
`_request(url, params, body, method)`.
