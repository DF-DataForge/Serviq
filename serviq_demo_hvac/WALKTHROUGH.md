# Demo-walkthrough: een dag bij Frisair Klimaattechniek

Een rondleiding langs de dagelijkse werking van een airco-installateur in
Odoo met Serviq en Stoqflow, op de data van `serviq_demo_hvac`. De
scenario's volgen één werkdag en wisselen tussen vier rollen:

| Rol | Werkt in |
|---|---|
| **Planner / dispatcher** | Installaties, Reparaties |
| **Technieker** | Interventies, Reparaties |
| **Verkoop** | Verkoop, Stoqflow |
| **Magazijn / werkplaats** | Voorraad, Productie, Logistiek |

Elk scenario staat op zichzelf; kies wat bij het publiek past. Een volledige
demo duurt zo'n 60 à 75 minuten, de kern (scenario's 1, 2, 3, 6 en 8)
ongeveer 30 minuten.

## Voorbereiding

1. Installeer de demo op een lege database (zie `README.md`) en log in als
   **admin**.
2. **Maak een kopie** van de database om mee te demonstreren (database
   manager > *Duplicate*). Vink daarbij **Neutralize** aan: dan kan je in
   scenario 7 een levering van Stoqflow nabootsen zonder Stoqflow-account.
   De originele database blijft zo een schone uitgangssituatie voor de
   volgende demo.
3. Zet de **ontwikkelaarsmodus** aan (Settings > *Activate the developer
   mode*); die is alleen nodig voor scenario 7.
4. Optioneel: installeer het Nederlands (Settings > Languages) voor een
   volledig Nederlandstalige interface. Deze gids gebruikt de Engelse namen
   van de standaardmenu's van Odoo; de Serviq-menu's zijn altijd Nederlands.

Over de verwijzingen in deze gids:

* De **documentnummers** tussen haakjes (bv. `FRW/RO/00002`) gelden voor een
  verse installatie; zoek anders op de klantnaam.
* **Serienummers** hebben de vorm `AO35-2609-0001`: `AO`/`AI` voor buiten- of
  binnenunit, het vermogen, jaar en maand van ontvangst, volgnummer. Jaar en
  maand hangen af van de installatiedatum van de demo; kopieer ze uit het
  scherm.
* Alle datums zijn relatief tot de dag van installatie: "vandaag" in de data
  is de dag waarop je de demo installeerde.

---

## 1. Ochtendoverzicht (planner, 5 min)

**Verhaal:** de dag begint met de vraag *wat loopt er, wat moet er vandaag
gebeuren?*

1. **Installaties > Overzicht.**
   * Bovenaan de tellers: 13 installaties, waarvan een deel *Actief*, één
     *Inbedrijfstelling gepland* en enkele in *Service* (er is binnen 14
     dagen een interventie gepland).
   * Tegel **Interventies**: open, deze week gepland, niet ingepland,
     afgerond deze maand. Klik op *Niet ingepland*: de herstelling bij
     Pieter Janssens en de inbedrijfstelling bij Thomas Peeters wachten
     op een datum.
   * Tegel **Producten in reparatie**: de open herstelorders uit de app
     Reparaties per fase (nieuw, bevestigd, in reparatie).
   * **Planning**: maand-, week- of dagkalender van de interventies, te
     filteren per installateur.
2. **Logistiek > Overzicht**: de stand van voorraad, serienummers,
   inkomende en uitgaande goederen en reserveonderdelen in één scherm.

**Toon vooral:** één startscherm voor planning, service en logistiek, zonder
zelf lijsten te moeten samenstellen.

---

## 2. Een klant belt met een storing: opzoeken op serienummer (planner, 10 min)

**Verhaal:** Sofie Wouters belt: haar buitenunit maakt een ratelend geluid.
Ze leest het serienummer af van het typeplaatje.

1. Haal het serienummer op: **Installaties > Installaties**, open de
   installatie van *Sofie Wouters* en noteer het serienummer van de
   buitenunit (`AO35-…`). In de demo speel je de klant die het voorleest.
2. **Inventory > Products > Lots / Serial Numbers**, zoek het serienummer.
   Op het serienummer:
   * smart button **Installatie**: bij welke klant en in welke installatie
     de unit staat, met de andere componenten (binnenunit, montagekit) en de
     interventies;
   * smart button met de moersleutel (**To Do / Done**): de herstellingen op
     deze unit.
3. Open die smart button en klik **New**: product en serienummer zijn
   ingevuld.
   * **Customer**: Sofie Wouters.
   * **Under Warranty** aanvinken: de installatie is enkele weken oud (zie
     de leverdatum op de installatie of de verkooporder).
   * Het type is *Herstellingen op locatie*: de unit blijft bij de klant
     (*Product Source/Destination Location* = Customers), onderdelen komen
     standaard van de plank *Reserveonderdelen*. Zet **Component Source
     Location** op *Servicewagen 1* als de technieker het onderdeel in de
     wagen heeft.
   * Tab **Parts**: voeg bv. *Temperatuursensor NTC 10k* toe (of laat leeg
     tot na de diagnose).
   * Schrijf de klacht in **Internal Notes** en klik **Confirm Repair**.
4. Plan het bezoek: **Installaties > Interventies** > **New**: installatie
   van Sofie Wouters, *Type interventie* = *Herstelling*. Klik **Inplannen
   via kalender**, kies een dag en een vrij tijdslot.
5. Terug op de installatie: de status is naar **Service** gegaan (er staat
   een interventie gepland binnen 14 dagen) en de smart button
   **Herstellingen** telt de nieuwe interventie.

**Toon vooral:** van serienummer naar klant, installatie, garantie en
herstelling in een paar klikken, zonder te zoeken in mappen of mails.

---

## 3. Een herstelling op locatie afwerken (technieker, 5 min)

**Verhaal:** de technieker heeft bij Bakkerij Van Hoof de ventilatormotor
van de buitenunit vervangen (foutcode E7, onder garantie).

1. **Repairs > Orders**, open de herstelling van *Bakkerij Van Hoof*
   (`FRW/RO/00002`, fase *Under Repair*, prioriteit urgent).
2. Tab **Parts**: een lijn *Add* (nieuwe motor van de plank
   Reserveonderdelen) en een lijn *Remove* (de defecte motor gaat naar
   Scrap, voor de garantieclaim bij de leverancier).
3. Klik **End Repair**: het onderdeel is verbruikt, de voorraad van de plank
   daalt met één.
4. In de chatter de geplande activiteiten: *Klant bellen na testrun* (morgen)
   en *Garantieclaim indienen bij Nordklima*. Markeer de eerste als gedaan
   met een korte notitie.
5. **Installaties > Interventies**: open *Herstelling - Bakkerij Van Hoof* en
   zet de status van de taak op **Done** (het rondje met het vinkje naast de
   titel). De installatie gaat terug
   van *Service* naar **Actief**.

**Toon vooral:** verbruikte onderdelen en defecte stukken zijn traceerbaar
per serienummer; de status van de installatie volgt de interventies vanzelf.

---

## 4. Een garantieherstelling inplannen en uitvoeren (planner + technieker, 5 min)

**Verhaal:** de afstandsbediening van Pieter Janssens reageert niet meer.
De melding staat al in het systeem, met een activiteit *Bezoek inplannen*.

1. **Repairs > Orders**, filter op de activiteiten van vandaag of open de
   herstelling van *Pieter Janssens* (`FRW/RO/00006`, *New*, garantie).
   Onderdelen komen uit *Servicewagen 1*.
2. **Installaties > Interventies** > *Herstelling - Pieter Janssens* (nog
   zonder datum) > **Inplannen via kalender**. Combineer met een ander bezoek
   in de buurt (Sint-Katelijne-Waver) door in de weekkalender te kijken.
3. Terug naar de herstelling: **Confirm Repair**, ter plaatse **Start
   Repair**, na de vervanging **End Repair**. De voorraad van de wagen daalt.
4. Markeer de activiteit *Bezoek inplannen* als gedaan.

---

## 5. Betalende herstellingen: offerte en wachten op een onderdeel (planner, 10 min)

**Verhaal:** twee oudere installaties, buiten garantie.

**Familie Wuyts: offerte aanvaard**

1. Open de herstelling van *Familie Wuyts* (`FRW/RO/00005`, *New*): de
   buitenunit maakt lawaai, er is een offerte verstuurd en een activiteit
   *Offerte opvolgen*.
2. Smart button **Sale Order** (`S00017`, *Quotation Sent*): het
   expansieventiel uit de herstelling plus arbeid en verplaatsing. De klant
   belt om te aanvaarden: **Confirm**.
3. Terug naar de herstelling (smart button op de verkooporder) en **Confirm
   Repair**. Markeer *Offerte opvolgen* als gedaan.

**Familie Mertens: wachten op een printplaat**

1. Open de herstelling van *Familie Mertens* (`FRW/RO/00003`, *Confirmed*):
   offerte aanvaard, maar **Component Status** toont een verwachte datum:
   de printplaat is niet op voorraad en besteld bij Nordklima.
2. Het bijhorende bezoek staat al gepland (*Herstelling - Familie Mertens*),
   na de verwachte levering. De ontvangst volgt in scenario 9a.

**Toon vooral:** garantie of niet bepaalt de prijs op de offerte; de
planner ziet meteen welke herstellingen op een onderdeel wachten.

---

## 6. Een installatiepakket verkopen (verkoop, 5 min)

**Verhaal:** Jan De Smet beslist om de offerte voor een airco van 3,5 kW te
aanvaarden.

1. **Sales > Orders > Quotations**, open de offerte van *Jan De Smet*
   (`S00014`): *Installatiepakket split airco 3,5 kW* plus de plaatsing.
2. Toon op het product (**Sales > Products > Products**) de stuklijst van het
   pakket: buitenunit, binnenunit en montagekit (type *Kit*). Het pakket zelf
   heeft geen voorraad; de onderdelen liggen bij Stoqflow.
3. **Confirm**. Smart button **Delivery**: de levering vertrekt uit
   **SQF/Stock** (Stoqflow) en bevat de drie onderdelen.
4. Tab **Stoqflow** op de levering: dit wordt een Stoqflow-order. De
   procescode is *Pending*: de koppeling stuurt de order naar Stoqflow,
   Stoqflow pickt de units en meldt de **serienummers** terug bij de
   levering (de serienummercontrole staat aan op de units).
5. **Stoqflow > Dashboard** / **Stoqflow > Orders**: de openstaande en
   afgewerkte Stoqflow-orders.

**Toon vooral:** verkoop werkt met één pakketlijn; de logistieke
afhandeling (en de serienummers) komt van Stoqflow.

---

## 7. Stoqflow levert: installatie registreren (verkoop + planner, 10 min)

**Verhaal:** Stoqflow heeft de airco van Ann Verbruggen geleverd op de
werf. In productie meldt de koppeling dit vanzelf; in de demo bootsen we
het na.

> Alleen op een **geneutraliseerde kopie** met de **ontwikkelaarsmodus** aan
> (zie Voorbereiding). Op een gewone database weigert Odoo terecht om een
> Stoqflow-levering met de hand af te werken.

1. **Inventory > Operations > Transfers > Deliveries**, open de levering van
   *Ann Verbruggen* (`SQF/OUT/00009`).
2. Tab **Debug** > *Set process code / status*: **Process code** = *Manual*,
   opslaan. Klik **Validate** (vraagt Odoo de eerste keer of klanten een
   sms krijgen bij levering, kies naar wens). De serienummers van buiten- en binnenunit
   staan op de levering (ze werden bij de bevestiging gereserveerd, zoals
   Stoqflow ze zou melden).
3. **Installaties > Installaties** > **New**:
   * **Product**: *Installatiepakket split airco 3,5 kW*: categorie en
     componenten (buitenunit, binnenunit, montagekit) komen uit de stuklijst;
   * **Klant**: Ann Verbruggen, **Installateur**: Frisair Klimaattechniek BV;
   * vul op de componentlijnen de **serienummers van de levering** in.
     Probeer een serienummer dat al op een andere installatie staat: Serviq
     weigert het.
   * Opslaan: status **Geleverd**. De montagekit wordt een
     sub-installatie met zijn onderdelen.
4. Smart button **Interventie plannen**: *Inbedrijfstelling*, en plan via
   **Inplannen via kalender** (zie scenario 8).

**Toon vooral:** het serienummer loopt door van ontvangst bij Stoqflow via
de levering tot op de installatie bij de klant.

---

## 8. Inbedrijfstelling (planner + technieker, 5 min)

**Thomas Peeters: inbedrijfstelling inplannen**

1. **Installaties > Installaties**, open de installatie van *Thomas Peeters*:
   status **Geleverd** (2 dagen geleden geleverd).
2. Smart button **Interventies** > *Inbedrijfstelling - Thomas Peeters*
   (nog geen datum) > **Inplannen via kalender**: kies een slot in de
   komende dagen.
3. Terug naar de installatie: status **Inbedrijfstelling gepland**.

**Elke Maes: inbedrijfstelling uitgevoerd**

1. Open de installatie van *Elke Maes*: **Inbedrijfstelling gepland**.
2. Smart button **Interventies**, open de inbedrijfstelling en zet ze op
   **Done**.
3. De installatie staat op **Actief**.

**Toon vooral:** niemand hoeft de status van een installatie bij te houden:
die volgt uit de geplande en afgewerkte interventies.

---

## 9. Magazijn en werkplaats (magazijn, 15 min)

**a. Printplaten ontvangen (vervolg scenario 5)**

1. **Inventory > Operations > Transfers > Receipts**, open de ontvangst van
   Nordklima met de printplaten (`FRW/IN/00005`, aankoop `P00009`): ze komen
   binnen op **FRW/Stock/Reserveonderdelen**, niet bij Stoqflow.
2. **Validate**.
3. Open de herstelling van *Familie Mertens* en klik **Check availability**:
   **Component Status** wordt *Available*. De technieker kan op het geplande
   bezoek de herstelling starten en afronden.

**b. Montagekits samenstellen**

1. **Manufacturing > Operations > Manufacturing Orders**, open de open
   productieorder voor 6 × *Montagekit split 2,5-3,5 kW* (`FRW/MO/00003`).
2. Toon de onderdelen (koperleiding, muurbeugel, trillingsdempers, …) en de
   stuklijst; klik **Produce All**.

**c. Kits naar Stoqflow sturen**

1. **Inventory > Operations > Procurement > Replenishment**, verwijder de
   standaardfilter en zoek *Montagekit*: de regel voor
   **SQF/Stock** gebruikt de route *Stoqflow Fulfilment: Supply Product from
   Frisair Werkplaats*.
2. Vul een hoeveelheid in bij **To Order** en klik **Order**.
3. Er ontstaan twee transfers: een uitgaande uit de werkplaats
   (`FRW/OUT/…`, verzending naar Stoqflow) en een ontvangst bij Stoqflow
   (`SQF/IN/…`) met procescode **Pending**: de aankondiging van de inkomende
   goederen aan Stoqflow. Toon ook de oudere aankondiging (`SQF/IN/00006`)
   die nog op Stoqflow wacht.

**d. Units op komst bij Stoqflow**

1. **Logistiek > Inkomende goederen**: per leverancier de aankopen en hun
   ontvangststatus. De laatste aankoop van airco-units bij Nordklima
   (`P00003`) is nog niet ontvangen: Stoqflow meldt de serienummers bij de
   ontvangst.
2. Ter vergelijking een afgewerkte ontvangst (`SQF/IN/00001`): elke unit
   heeft zijn eigen serienummer.

---

## 10. Servicewagen aanvullen en reserveonderdelen leveren (magazijn, 5 min)

**Servicewagen 1 aanvullen**

1. **Logistiek > Voorraadoverzicht** (of **Inventory > Reporting >
   Stock**, gegroepeerd per locatie): *Servicewagen 1* heeft nog één
   condenspomp (de andere ging naar Familie Claes).
2. **Inventory > Operations > Transfers > Internal** > **New**: van
   **FRW/Stock/Reserveonderdelen** naar **FRW/Servicewagen 1 (1-ABC-123)**,
   1 × *Condenspomp mini*. **Mark as To Do**, **Validate**.

**Reserveonderdelen voor een collega-installateur**

1. **Logistiek > Reserveonderdelen**: de leveringen van reserveonderdelen
   per klant. Koeltechniek Verhaegen heeft een levering klaarstaan
   (`FRW/OUT/00005`): expansieventiel en filters.
2. Open de levering en **Validate**. Ze vertrekt uit de werkplaats, niet uit
   Stoqflow: reserveonderdelen gaan nooit naar Stoqflow (*Never send this
   product to Stoqflow* op het product).

---

## 11. Dagafsluiting (planner + magazijn, 5 min)

1. **Logistiek > Serienummers**: per product waar de serienummers zitten:
   besteld, in eigen voorraad (Stoqflow) of bij de klant, met reservatie- en
   installatiestatus.
2. **Logistiek > Uitgaande goederen**: de leveringen die Stoqflow nog moet
   uitvoeren (Notariskantoor Goossens, Koeltechniek Verhaegen, …).
3. **Repairs > Reporting > Repairs**: herstellingen per fase, garantie of
   betalend (tags *Garantie* / *Betalend*).
4. **Installaties > Overzicht**: de tellers zijn bijgewerkt met het werk van
   vandaag.

---

## Overzicht van de demodata

| Klant | Situatie | Gebruikt in |
|---|---|---|
| Familie Claes | Actief; garantieherstelling (condenspomp) afgerond | 10 |
| Lien Van den Broeck | Twee installaties (twee kamers), actief | - |
| Bakkerij Van Hoof | Garantieherstelling in uitvoering (ventilatormotor), in service | 3 |
| Sofie Wouters | Actief | 2 |
| Dokterspraktijk De Linde | Actief | - |
| Pieter Janssens | Garantieherstelling nieuw (afstandsbediening) | 4 |
| Elke Maes | Inbedrijfstelling gepland | 8 |
| Thomas Peeters | Geleverd, inbedrijfstelling nog in te plannen | 8 |
| Familie Mertens | Oudere installatie; betalende herstelling wacht op printplaat | 5, 9a |
| Kapsalon Lena | Oudere installatie; betalende herstelling afgerond, onderhoud gepland | - |
| Familie Wuyts | Oudere installatie; offerte voor herstelling verstuurd | 5 |
| Garage Peeters & Zn | Oudere installatie; herstelling geannuleerd, vervanging gepland | - |
| Ann Verbruggen | Pakket besteld, levering wacht op Stoqflow | 7 |
| Notariskantoor Goossens | Twee pakketten besteld, levering wacht op Stoqflow | 11 |
| Jan De Smet | Offerte | 6 |
| Koeltechniek Verhaegen | Collega-installateur: losse units (Stoqflow) en reserveonderdelen (werkplaats) | 10 |
