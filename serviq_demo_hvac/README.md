# Serviq demo: Frisair Klimaattechniek

Demodatabase voor Serviq: een fictieve Belgische airco-installateur,
**Frisair Klimaattechniek BV** uit Mechelen, die zijn airco-units laat
opslaan in een fulfilmentmagazijn van Stoqflow. Dat magazijn is een gewoon
Odoo-magazijn: de Stoqflow-koppeling (`webship`) wordt niet gebruikt. Alles
wordt bij de installatie van de module aangemaakt door `hooks.py` (geen
XML-data).

Niet installeren op een productiedatabase: de module wijzigt het
hoofdbedrijf en maakt magazijnen, producten, partners en orders aan.

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
| Magazijnen | **Frisair Werkplaats** (FRW): eigen magazijn en werkplaats, plank *Reserveonderdelen* (locatie reserveonderdelen) en twee servicewagens als locatie. **Stoqflow Fulfilment** (SQF): fulfilmentmagazijn voor de units en kits, bevoorraad vanuit FRW |
| Airco-units | Nordklima Aero buiten- en binnenunits van 2,5 / 3,5 / 5,0 kW; serienummer per stuk, op ontvangsten en leveringen. Ingekocht rechtstreeks in SQF |
| Montagekits | Twee kits (2,5-3,5 kW en 5,0 kW) met stuklijst van koperleiding, muurbeugel, trillingsdempers, condensafvoer, kabel en leidinggoot; onderdelen ingekocht in FRW, kits samengesteld in de werkplaats en naar SQF gestuurd |
| Reserveonderdelen | Printplaat, ventilatormotor, expansieventiel, afstandsbediening, condenspomp, sensor, filters; componentrol *Reserveonderdeel*, blijven in de werkplaats en de servicewagens |
| Installatiepakketten | Kit-stuklijst (phantom) van buitenunit + binnenunit + montagekit per vermogen, componentrol *Installatiepakket*, categorie *Split airco* |
| Installaties | 13 installaties: 9 uit de geleverde pakketten met de serienummers van de levering, 4 oudere (2019-2022) zonder documenten; inbedrijfstellingen (afgerond, ingepland, nog in te plannen), onderhoud, herstellingen en een vervanging |
| Herstellingen | Type *Herstellingen op locatie*: de unit blijft bij de klant, onderdelen van de plank of een servicewagen. 7 herstelorders (app Reparaties) op geïnstalleerde units, gekozen op serienummer: garantie en betalend, met verbruikte reserveonderdelen uit de werkplaats of een servicewagen, in elke fase (nieuw, bevestigd, in reparatie, hersteld, geannuleerd), offertes / verkooporders voor de betalende en opvolgactiviteiten |
| Historiek | Zo'n 6 weken documenten: inkopen, productieorders, bevoorrading naar Stoqflow, verkopen en leveringen, interne transfers naar de servicewagens |
| Open orders | Inkoop en bevoorrading die nog in SQF ontvangen moeten worden, verkopen die SQF nog moet leveren, een productieorder en een offerte |

Een herstelling opzoeken op serienummer: *Reparaties* > zoeken op
*Lot/Serienummer*, of vanuit het serienummer (smart button
*Reparaties*); het serienummer toont ook de installatie waarop het
geplaatst is.
