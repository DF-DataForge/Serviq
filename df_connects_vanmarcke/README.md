# DF Connects: Van Marcke

Koppeling van `df_connects` met de API's van Van Marcke
([documentatie](https://vanmarcke.atlassian.net/wiki/spaces/VMI/overview)).

## Toegang aanvragen

1. Registreer je op de developer portal (https://developer.vanmarcke.com,
   test: https://developer-test.vanmarcke.com).
2. Vul het *Van Marcke API – Application Request Form* in en stuur het naar
   api-support@vanmarcke.com. Je krijgt een **client ID** en **client secret**;
   de **Application Key** (header `x-api-key`) staat in *My Workspace* van de
   portal.
3. Voor nettoprijzen van jullie klantnummer: maak een **service user** aan
   (Service Users API, na aanmelden met een Van Marcke-account) en gebruik
   die gebruikersnaam en dat wachtwoord. Met *client credentials* zijn de
   antwoorden algemeen, zonder klantprijzen.

## Instellen

Nieuwe koppeling, type **Van Marcke**: de URL's, de paginering en de
veldkoppeling worden ingevuld. Vul aan:

| Veld | Waarde |
|---|---|
| Omgeving | Productie (`https://api.vanmarcke.com`) of Test (`https://api-test.vanmarcke.com`) |
| Aanmelden als | Service user (OAuth *password grant*) of client credentials |
| Client ID / secret | uit de registratie, als basic auth naar `/v1/oauth/token` |
| Application Key | header `x-api-key` bij elke oproep |
| Extra parameters | standaard `{"country": "BE", "language": "nl"}` |
| Op te halen producten | de productnummers uit de leveranciersprijslijst van Van Marcke (standaard), een lijst van productnummers, of de volledige catalogus |

Het token wordt bewaard en vernieuwd met het refresh token (365 dagen
geldig); bij een 401 wordt één keer een nieuw token gevraagd.

## Wat wordt opgehaald

Per 50 producten (het maximum van de bulkoproepen):

- `POST /v2/products/bulk/detail`: EAN (`supplierBarcode`) en omschrijving;
- `POST /v2/products/bulk/pricesAndStock`: nettoprijs en voorraad van het
  centrale magazijn (entiteit *Centraal magazijn*);
- optioneel `GET /v2/products/{productId}/stock/{storeId}` voor de winkels
  waarbij *Winkelvoorraad ophalen* aangevinkt is (entiteit = winkel).
  **Winkels ophalen** (Stores API `GET /v1/stores`) maakt de winkels aan.

Het Van Marcke-productnummer is de leveranciersproductcode; de EAN wordt de
UUID als ze geldig is. Productnummers die Van Marcke niet (meer) kent, worden
gearchiveerd.

## Limieten

50.000 oproepen per dag en 1 oproep per 20 ms (API Security Policies). De
koppeling wacht tussen de oproepen en probeert opnieuw bij 429. Reken per
synchronisatie op 2 oproepen per 50 producten, plus 1 per product en
winkel met winkelvoorraad.

## Na te kijken bij de eerste koppeling

De JSON-schema's van de Products API staan enkel in de developer portal
(na aanmelden). De paden in de veldkoppeling proberen daarom meerdere
veldnamen (bv. `netPrice|price.netPrice|...`). Zet bij de eerste
synchronisatie **Ruwe gegevens bewaren** aan, kijk de JSON na op een
leveranciersproduct en pas zo nodig aan op de koppeling:

- *Veldkoppeling*: EAN, omschrijving, prijs, munt;
- *Van Marcke*: sleutel van de productnummers in de body (`productIds`), pad
  van de lijst in het bulkantwoord, veld productnummer, voorraad centraal
  magazijn en winkel;
- *Paginering* (enkel volledige catalogus): parameters pagina en
  paginagrootte.
