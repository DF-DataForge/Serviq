# Demo-walkthrough: een dag bij Frisair Klimaattechniek

Een rondleiding langs de dagelijkse installatieflows van een
airco-installateur in Odoo met Serviq, op de data van `serviq_demo_hvac`:
installaties met hun serienummers, inbedrijfstelling, onderhoud en
herstellingen. De scenario's volgen één werkdag en wisselen tussen drie
rollen:

| Rol | Werkt in |
|---|---|
| **Planner / dispatcher** | Installaties, Reparaties |
| **Technieker** | Interventies, Reparaties, het installateursportaal |
| **Verkoop** | Verkoop, Installaties |

Elk scenario staat op zichzelf; kies wat bij het publiek past. Een volledige
demo duurt zo'n 50 à 60 minuten, de kern (scenario's 1, 2, 3, 7 en 8)
ongeveer 30 minuten.

## Voorbereiding

1. Installeer de demo op een lege database (zie `README.md`) en log in als
   **admin**.
2. **Maak een kopie** van de database om mee te demonstreren (database
   manager > *Duplicate*). De originele database blijft zo een schone
   uitgangssituatie voor de volgende demo.
3. Optioneel: installeer het Nederlands (Settings > Languages) voor een
   volledig Nederlandstalige interface. Deze gids gebruikt de Engelse namen
   van de standaardmenu's van Odoo; de Serviq-menu's zijn altijd Nederlands.

Over de verwijzingen in deze gids:

* De **documentnummers** tussen haakjes (bv. `FRW/RO/00002`) gelden voor een
  verse installatie; zoek anders op de klantnaam.
* **Serienummers** hebben de vorm `AO35-2609-0001`: `AO`/`AI` voor buiten- of
  binnenunit, het vermogen, jaar en maand, volgnummer. Jaar en maand hangen
  af van de installatiedatum van de demo; kopieer ze uit het scherm.
* Alle datums zijn relatief tot de dag van installatie: "vandaag" in de data
  is de dag waarop je de demo installeerde.

---

## 1. Ochtendoverzicht (planner, 5 min)

**Verhaal:** de dag begint met de vraag *wat loopt er, wat moet er vandaag
gebeuren?*

**Installaties > Overzicht**

* Bovenaan de tellers: 13 installaties, waarvan een deel *Actief*, één
  *Inbedrijfstelling gepland* en enkele in *Service* (er is binnen 14 dagen
  een interventie gepland).
* Tegel **Interventies**: open, deze week gepland, niet ingepland, afgerond
  deze maand. Klik op *Niet ingepland*: de herstelling bij Pieter Janssens
  en de inbedrijfstelling bij Thomas Peeters wachten op een datum.
* Tegel **Producten in reparatie**: de open herstelorders uit de app
  Reparaties per fase (nieuw, bevestigd, in reparatie).
* **Planning**: maand-, week- of dagkalender van de interventies, te
  filteren per installateur.

**Toon vooral:** één startscherm voor installaties, planning en service,
zonder zelf lijsten te moeten samenstellen.

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
     de leverdatum op de verkooporder).
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
herstelling in een paar klikken.

---

## 3. Een herstelling op locatie afwerken (technieker, 5 min)

**Verhaal:** de technieker heeft bij Bakkerij Van Hoof de ventilatormotor
van de buitenunit vervangen (foutcode E7, onder garantie).

1. **Repairs > Orders**, open de herstelling van *Bakkerij Van Hoof*
   (`FRW/RO/00002`, fase *Under Repair*, prioriteit urgent).
2. Tab **Parts**: een lijn *Add* (nieuwe motor van de plank
   Reserveonderdelen) en een lijn *Remove* (de defecte motor gaat naar
   Scrap, voor de garantieclaim bij de fabrikant).
3. Klik **End Repair**: het onderdeel is verbruikt.
4. In de chatter de geplande activiteiten: *Klant bellen na testrun* (morgen)
   en *Garantieclaim indienen bij Nordklima*. Markeer de eerste als gedaan
   met een korte notitie.
5. **Installaties > Interventies**: open *Herstelling - Bakkerij Van Hoof* en
   zet de status van de taak op **Done** (het rondje met het vinkje naast de
   titel). De installatie gaat terug van *Service* naar **Actief**.

**Toon vooral:** verbruikte onderdelen en defecte stukken zijn traceerbaar
per serienummer; de status van de installatie volgt de interventies vanzelf.

---

## 4. Een garantieherstelling inplannen en uitvoeren (planner + technieker, 5 min)

**Verhaal:** de afstandsbediening van Pieter Janssens reageert niet meer.
De melding staat al in het systeem, met een activiteit *Bezoek inplannen*.

1. **Repairs > Orders**, open de herstelling van *Pieter Janssens*
   (`FRW/RO/00006`, *New*, garantie). Onderdelen komen uit
   *Servicewagen 1*.
2. **Installaties > Interventies** > *Herstelling - Pieter Janssens* (nog
   zonder datum) > **Inplannen via kalender**. Combineer met een ander bezoek
   in de buurt (Sint-Katelijne-Waver) door in de weekkalender te kijken.
3. Terug naar de herstelling: **Confirm Repair**, ter plaatse **Start
   Repair**, na de vervanging **End Repair**.
4. Markeer de activiteit *Bezoek inplannen* als gedaan.

---

## 5. Betalende herstellingen: offerte en wachten op een onderdeel (planner, 10 min)

**Verhaal:** twee oudere installaties, buiten garantie.

**Familie Wuyts: offerte aanvaard**

1. Open de herstelling van *Familie Wuyts* (`FRW/RO/00005`, *New*): de
   buitenunit maakt lawaai, er is een offerte verstuurd en een activiteit
   *Offerte opvolgen*.
2. Smart button **Sale Order** (`S00014`, *Quotation Sent*): het
   expansieventiel uit de herstelling plus arbeid en verplaatsing. De klant
   belt om te aanvaarden: **Confirm**.
3. Terug naar de herstelling (smart button op de verkooporder) en **Confirm
   Repair**. Markeer *Offerte opvolgen* als gedaan.

**Familie Mertens: wachten op een printplaat**

1. Open de herstelling van *Familie Mertens* (`FRW/RO/00003`, *Confirmed*):
   offerte aanvaard, maar **Component Status** staat op *Not Available*: de
   printplaat is niet op voorraad en besteld bij de fabrikant (activiteit
   *Levering printplaat opvolgen*). Het bezoek staat al gepland.
2. De printplaat is binnen: **Inventory > Operations > Physical Inventory**,
   lijn voor *Printplaat binnenunit Aero* op **FRW/Stock/Reserveonderdelen**
   met *Counted Quantity* 2, **Apply**.
3. Terug naar de herstelling: **Check availability**, **Component Status**
   wordt *Available*. Op het bezoek: **Start Repair** en **End Repair**.

**Toon vooral:** garantie of niet bepaalt de prijs op de offerte; de
planner ziet meteen welke herstellingen op een onderdeel wachten.

---

## 6. Een installatiepakket verkopen (verkoop, 5 min)

**Verhaal:** Jan De Smet beslist om de offerte voor een airco van 3,5 kW te
aanvaarden.

1. **Sales > Orders > Quotations**, open de offerte van *Jan De Smet*
   (`S00011`): *Installatiepakket split airco 3,5 kW* plus de plaatsing.
2. Toon op het product (**Sales > Products > Products**) de stuklijst van het
   pakket: buitenunit, binnenunit en montagekit (type *Kit*). Het pakket
   heeft zelf de componentrol *Installatiepakket* en de categorie *Split
   airco*.
3. **Confirm**. Smart button **Delivery**: de levering bevat de drie
   onderdelen; Odoo heeft al een **serienummer** gereserveerd voor de
   buiten- en de binnenunit.

**Toon vooral:** verkoop werkt met één pakketlijn; welke units (en welke
serienummers) er naar de klant gaan, volgt uit de stuklijst.

---

## 7. Levering en installatie registreren (verkoop + planner, 10 min)

**Verhaal:** de airco van Ann Verbruggen is vandaag geleverd en geplaatst.

1. **Inventory > Operations > Transfers > Deliveries**, open de levering van
   *Ann Verbruggen* (`FRW/OUT/00009`).
2. Controleer de **serienummers** van buiten- en binnenunit (pas ze aan als
   de technieker andere units meenam) en klik **Validate** (vraagt Odoo de
   eerste keer of klanten een sms krijgen bij levering, kies naar wens).
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

**Toon vooral:** het serienummer loopt door van de voorraad via de levering
tot op de installatie bij de klant, en elk serienummer kan maar op één
installatie staan.

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

In plaats van stap 2 kan de technieker de inbedrijfstelling ook zelf
afronden in het portaal, zie scenario 11.

**Toon vooral:** niemand hoeft de status van een installatie bij te houden:
die volgt uit de geplande en afgewerkte interventies.

---

## 9. Onderhoud en vervanging (planner, 5 min)

**Kapsalon Lena: jaarlijks onderhoud**

1. Open de installatie van *Kapsalon Lena* (geplaatst in 2020): status
   **Service**, want het jaarlijks onderhoud staat binnen 14 dagen gepland.
   De smart button **Herstellingen** toont ook de afgewerkte herstelling van
   de temperatuursensor.
2. Na het bezoek: open *Periodiek onderhoud - Kapsalon Lena* en zet het op
   **Done**: de installatie gaat terug naar **Actief**.

**Garage Peeters & Zn: vervangen in plaats van herstellen**

1. **Repairs > Orders**, filter op *Cancelled*: de herstelling van de
   compressor (`FRW/RO/00007`) is geannuleerd omdat herstellen niet rendabel
   was.
2. Op de installatie van *Garage Peeters & Zn* staat een interventie
   *Vervanging* gepland (smart button **Vervangingen**).

---

## 10. Dagafsluiting (planner, 5 min)

1. **Installaties > Overzicht**: de tellers zijn bijgewerkt met het werk van
   vandaag.
2. **Repairs > Reporting > Repairs**: herstellingen per fase, garantie of
   betalend (tags *Garantie* / *Betalend*).
3. Op een serienummer (**Inventory > Products > Lots / Serial Numbers**) de
   knop **Traceability**: de volledige historiek van de unit, van voorraad
   via levering tot de herstellingen.

---

## 11. De technieker in het portaal (technieker, 10 min)

**Verhaal:** de technieker werkt onderweg, op zijn gsm. Hij heeft geen
backend-gebruiker nodig: in het installateursportaal ziet hij de
interventies van Frisair, zijn planning en de installaties, en werkt hij ze
af.

1. Open een privévenster en log in op `/web/login` als **technieker**
   (wachtwoord `technieker`): Jens Verlinden, technieker bij Frisair, met
   een portaalgebruiker.
2. **My Account** (`/my`): de tegels **Installaties** en **Open
   interventies**.
3. **Open interventies**: één tab per type interventie (inbedrijfstelling,
   herstelling, onderhoud, vervanging) met hun aantal; met **Open**,
   **Afgerond** en **Alle** wissel je tussen open en afgeronde
   interventies.
4. **Planning**: maand-, week- of dagkalender van de interventies, dezelfde
   als in de backend.
5. Open *Inbedrijfstelling - Elke Maes*:
   * de gegevens van de klant, met de knop **Route** (Google Maps);
   * het blok **Inbedrijfstelling**: de componenten van de installatie met
     hun serienummer. Vul een opmerking in bij de buitenunit (bv.
     *Gemonteerd op muurbeugel achtergevel*) en klik **Inbedrijfstelling
     afronden**.
   * De interventie is afgerond; in de backend staat de installatie van
     Elke Maes op **Actief**, met in de chatter *Inbedrijfstelling afgerond
     door Jens Verlinden via het portaal*.
6. Open *Periodiek onderhoud - Kapsalon Lena*: vul het **Rapport** in
   (bv. *Filters gereinigd, koudemiddeldruk in orde*), klik **Opslaan** en
   onderaan **Afronden**. De installatie gaat terug naar **Actief**.

**Toon vooral:** de technieker werkt de interventies af waar hij is; de
planner ziet het resultaat meteen in de backend. Installateurs en
distributeurs van buiten het bedrijf krijgen hetzelfde portaal, beperkt tot
hun eigen installaties en interventies.

---

## Overzicht van de demodata

| Klant | Situatie | Gebruikt in |
|---|---|---|
| Familie Claes | Actief; garantieherstelling (condenspomp) afgerond | - |
| Lien Van den Broeck | Twee installaties (twee kamers), actief | - |
| Bakkerij Van Hoof | Garantieherstelling in uitvoering (ventilatormotor), in service | 3 |
| Sofie Wouters | Actief | 2 |
| Dokterspraktijk De Linde | Actief | - |
| Pieter Janssens | Garantieherstelling nieuw (afstandsbediening) | 4 |
| Elke Maes | Inbedrijfstelling gepland | 8, 11 |
| Thomas Peeters | Geleverd, inbedrijfstelling nog in te plannen | 8 |
| Familie Mertens | Oudere installatie; betalende herstelling wacht op printplaat | 5 |
| Kapsalon Lena | Oudere installatie; betalende herstelling afgerond, onderhoud gepland | 9, 11 |
| Familie Wuyts | Oudere installatie; offerte voor herstelling verstuurd | 5 |
| Garage Peeters & Zn | Oudere installatie; herstelling geannuleerd, vervanging gepland | 9 |
| Ann Verbruggen | Pakket verkocht, levering en plaatsing vandaag | 7 |
| Notariskantoor Goossens | Twee pakketten verkocht, nog te leveren en te plaatsen | - |
| Jan De Smet | Offerte | 6 |
