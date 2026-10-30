# Serviq demo: Frisair Klimaattechniek

Demodatabase voor Serviq: een fictieve Belgische airco-installateur,
**Frisair Klimaattechniek BV** uit Mechelen. De demo gaat alleen over de
installatieflows (installaties, serienummers, inbedrijfstelling, onderhoud,
herstellingen); de logistiek erachter (inkoop, assemblage, fulfilment) is
weggelaten en de voorraad start vanuit een beginvoorraad. Alles wordt bij
de installatie van de module aangemaakt door `hooks.py` (geen XML-data).

Niet installeren op een productiedatabase: de module wijzigt het
hoofdbedrijf en maakt een magazijn, producten, partners en orders aan.

## Installeren

Nodig in het addons-pad: de Serviq-modules en Odoo 19 (Community volstaat)
met `l10n_be`. Op een lege database zonder Odoo-demodata:

```bash
odoo-bin -d frisair_demo --without-demo=True -i serviq_demo_hvac
```

Een rondleiding langs de dagelijkse workflows voor een demo staat in
[`WALKTHROUGH.md`](WALKTHROUGH.md).

## Wat zit erin

| Onderdeel | Inhoud |
|---|---|
| Magazijn | **Frisair Werkplaats** (FRW): voorraad van units en montagekits, plank *Reserveonderdelen* (locatie reserveonderdelen) en twee servicewagens als locatie; beginvoorraad via een voorraadtelling |
| Airco-units | Nordklima Aero buiten- en binnenunits van 2,5 / 3,5 / 5,0 kW, met een serienummer per stuk |
| Montagekits | Twee kits (2,5-3,5 kW en 5,0 kW) met een stuklijst van koperleiding, muurbeugel, trillingsdempers, condensafvoer, kabel en leidinggoot; in een installatie een sub-installatie |
| Reserveonderdelen | Printplaat, ventilatormotor, expansieventiel, afstandsbediening, condenspomp, sensor, filters; componentrol *Reserveonderdeel* |
| Installatiepakketten | Kit-stuklijst (phantom) van buitenunit + binnenunit + montagekit per vermogen, componentrol *Installatiepakket*, categorie *Split airco* |
| Installaties | 13 installaties: 9 uit de verkochte en geleverde pakketten met de serienummers van de levering, 4 oudere (2019-2022) zonder documenten; inbedrijfstellingen (afgerond, ingepland, nog in te plannen), onderhoud, herstellingen en een vervanging |
| Herstellingen | Type *Herstellingen op locatie*: de unit blijft bij de klant, onderdelen van de plank of een servicewagen. 7 herstelorders (app Reparaties) op geïnstalleerde units, gekozen op serienummer: garantie en betalend, in elke fase (nieuw, bevestigd, in reparatie, hersteld, geannuleerd), offertes / verkooporders voor de betalende en opvolgactiviteiten |
| Openstaand | Twee verkochte pakketten die nog geleverd en geplaatst moeten worden, en een offerte |
| Portaal | Installateursportaal (`serviq_portal`) met de flow *Inbedrijfstelling*: technieker **Jens Verlinden**, contact van Frisair met een portaalgebruiker (login `technieker`, wachtwoord `technieker`), ziet de interventies van Frisair onder `/my/installations`, met de planning, en werkt ze daar af |

Een herstelling opzoeken op serienummer: *Reparaties* > zoeken op
*Lot/Serienummer*, of vanuit het serienummer (smart button met de
moersleutel); het serienummer toont ook de installatie waarop het
geplaatst is.
