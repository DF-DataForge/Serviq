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
   met de knop **Service user aanmaken** op de koppeling (zie hieronder).
   Met *client credentials* zijn de antwoorden algemeen, zonder klantprijzen.

## Service user aanmaken

Registreer bij Van Marcke als *Redirect URL / Callback URL* per omgeving:

| Omgeving | Redirect URL |
|---|---|
| Test (staging) | `https://staging.platsr.be/df_connects_vanmarcke/oauth/callback` |
| Productie | `https://platsr.be/df_connects_vanmarcke/oauth/callback` |

Standaard gebruikt de koppeling `<web.base.url>/df_connects_vanmarcke/oauth/callback`
(zichtbaar als *Redirect URL (gebruikt)*); vul *Redirect URL* in als die
afwijkt van wat bij Van Marcke geregistreerd is: ze moet exact gelijk zijn.

1. Vul client ID, client secret en Application Key in en sla op.
2. Klik **Service user aanmaken**: je gaat naar de aanmeldpagina van Van
   Marcke. Meld aan met een Van Marcke-account (myblue) van het klantnummer
   waarvoor de nettoprijzen gelden.
3. Van Marcke stuurt je terug naar Odoo (OAuth *Authorization Code*): de
   koppeling ruilt de code voor een token van die gebruiker, maakt met
   `POST /v1/serviceusers` de service user aan en bewaart gebruikersnaam en
   wachtwoord op de koppeling ("Aanmelden als" wordt *Service user*). Het
   persoonlijke account en zijn token worden niet bewaard. Het resultaat
   verschijnt in de chatter; Van Marcke mailt de gegevens ook naar wie
   aanmeldde.
4. Bestaat er al een service user voor dit klantnummer en deze applicatie,
   gebruik dan **Wachtwoord service user vernieuwen** (`GET /v1/serviceusers`
   en `POST /{userId}/resetpassword`).

Een aanmelding is 15 minuten geldig en kan maar één keer gebruikt worden.
Enkel beheerders van de leverancierskoppelingen kunnen dit.

## Instellen

Nieuwe koppeling, type **Van Marcke**. Vul aan:

| Veld | Waarde |
|---|---|
| Omgeving | Productie (`https://api.vanmarcke.com`) of Test (`https://api-test.vanmarcke.com`) |
| Aanmelden als | Service user (OAuth *password grant*) of client credentials |
| Client ID / secret | uit de registratie, als basic auth naar `/v1/oauth/token` |
| Application Key | header `x-api-key` bij elke oproep |
| Catalogusland, kanaal, taal | `catalogCountry` (be, fr, lu), `channel` (b2b, b2c, diy), `language` (nl, fr, de, en) |
| Prijs | nettoprijs (`NET`) of brutoprijs (`LIST`); ontbreekt de ene, dan de andere |
| Op te halen producten | de productnummers uit de leveranciersprijslijst van Van Marcke (standaard), een lijst van productnummers, of de volledige catalogus |

Het token wordt bewaard en vernieuwd met het refresh token (365 dagen
geldig); bij een 401 wordt één keer een nieuw token gevraagd.

## Wat wordt opgehaald

Volgens de OpenAPI-specificatie *Products - v2* van de developer portal,
per 50 producten (het maximum van de bulkoproepen):

| Gegeven | Bron |
|---|---|
| Leveranciersproductcode | `productId` (Van Marcke-productnummer) |
| EAN / UUID | `supplierBarcode`, anders `barcode`, als het een geldige EAN is; anders wordt het productnummer de UUID |
| Omschrijving | `descriptions` in de taal van de koppeling (de korte bij voorkeur) |
| Prijs | `prices[]` met `priceType` NET of LIST, `value`, `currencyIso` |
| Voorraad centraal magazijn | `stock.stockAvailable`: Van Marcke geeft hier **enkel aan of er voorraad is, geen hoeveelheid**. De entiteit *Centraal magazijn* krijgt "Op voorraad" aan/uit met hoeveelheid 0. |
| Voorraad winkel | `GET /v2/products/{productId}/stock/{storeId}`: `stockLevel` (hoeveelheid) en `stockAvailable`, voor de winkels met *Winkelvoorraad ophalen* |

Oproepen:

- leveranciersprijslijst of lijst: `POST /v2/products/bulk/detail?includePriceAndStock=true`
  (details, prijzen en voorraad in één oproep) met `{"productIds": [...]}`;
  zonder *Productdetails ophalen* enkel `POST /bulk/pricesAndStock` (sneller,
  maar zonder EAN);
- volledige catalogus: `GET /v2/products` met `limit` / `offset`
  (`excludeArchived` instelbaar), daarna `POST /bulk/pricesAndStock`;
- **Winkels ophalen**: `GET /v1/stores` (pagina's met `currentPage` en
  `pageSize`), winkelnummer `name`, naam `displayName`.

Productnummers die Van Marcke niet (meer) kent, worden gearchiveerd.

## Limieten

50.000 oproepen per dag en 1 oproep per 20 ms (API Security Policies). De
koppeling wacht tussen de oproepen en probeert opnieuw bij 429. Reken per
synchronisatie op 1 oproep per 50 producten, plus 1 per product en winkel
met winkelvoorraad.
