# Serviq demo: Frisair Klimaattechniek

Demodatabase voor Serviq met de Stoqflow-koppeling (`webship`): een
fictieve Belgische airco-installateur, **Frisair Klimaattechniek BV** uit
Mechelen. Alles wordt bij de installatie van de module aangemaakt door
`hooks.py` (geen XML-data), naar het voorbeeld van `webship_demo_skateshop`.

Niet installeren op een productiedatabase: de module wijzigt het
hoofdbedrijf en maakt magazijnen, producten, partners en orders aan.

## Installeren

Nodig in het addons-pad: de Serviq-modules, `webship` (Stoqflow-koppeling,
`DF-DataForge/webship`, map `19.0`) en Odoo 19 met `l10n_be`. Op een
lege database zonder Odoo-demodata:

```bash
odoo-bin -d frisair_demo --without-demo=True -i serviq_demo_hvac
```

De Stoqflow-API-gegevens blijven leeg en de sync-crons staan uit; vul een
sandbox-sleutel in bij de Stoqflow-instellingen om echt te synchroniseren.

## Wat zit erin

| Onderdeel | Inhoud |
|---|---|
| Magazijnen | **Frisair Werkplaats** (FRW): eigen magazijn en werkplaats, plank *Reserveonderdelen* (locatie reserveonderdelen) en twee servicewagens als locatie. **Stoqflow Fulfilment** (SQF): fulfilmentmagazijn, voorraadlocatie gemarkeerd als Stoqflow-locatie, bevoorraad vanuit FRW |
| Airco-units | Nordklima Aero buiten- en binnenunits van 2,5 / 3,5 / 5,0 kW; serienummer per stuk en *Serial numbers*-controle van Stoqflow aan, dus serienummers op ontvangsten en leveringen. Ingekocht rechtstreeks in SQF |
| Montagekits | Twee kits (2,5-3,5 kW en 5,0 kW) met stuklijst van koperleiding, muurbeugel, trillingsdempers, condensafvoer, kabel en leidinggoot; onderdelen ingekocht in FRW, kits samengesteld in de werkplaats en naar SQF gestuurd |
| Reserveonderdelen | Printplaat, ventilatormotor, expansieventiel, afstandsbediening, condenspomp, sensor, filters; componentrol *Reserveonderdeel*, nooit naar Stoqflow |
| Installatiepakketten | Kit-stuklijst (phantom) van buitenunit + binnenunit + montagekit per vermogen, componentrol *Installatiepakket*, categorie *Split airco* |
| Installaties | 13 installaties: 9 uit de geleverde pakketten met de serienummers van de levering, 4 oudere (2019-2022) zonder documenten; inbedrijfstellingen (afgerond, ingepland, nog in te plannen), onderhoud, herstellingen en een vervanging |
| Herstellingen | 7 herstelorders (app Reparaties) op geïnstalleerde units, gekozen op serienummer: garantie en betalend, met verbruikte reserveonderdelen uit de werkplaats of een servicewagen, in elke fase (nieuw, bevestigd, in reparatie, hersteld, geannuleerd), offertes / verkooporders voor de betalende en opvolgactiviteiten |
| Historiek | Zo'n 6 weken documenten: inkopen, productieorders, bevoorrading naar Stoqflow, verkopen en leveringen, interne transfers naar de servicewagens |
| Open orders | Inkoop en bevoorrading die Stoqflow nog moet ontvangen en verkopen die Stoqflow nog moet leveren (procescode *Pending*), plus een offerte |

Een herstelling opzoeken op serienummer: *Reparaties* > zoeken op
*Lot/Serienummer*, of vanuit het serienummer (smart button
*Reparaties*); het serienummer toont ook de installatie waarop het
geplaatst is.

Historische transfers krijgen procescode *Manual* (buiten de koppeling
verwerkt), transfers zonder Stoqflow-locatie *Not Applicable*; alleen de
open documenten staan op *Pending* voor Stoqflow.
