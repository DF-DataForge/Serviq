# Serviq

Generieke Odoo 19-modules voor bedrijven die **installaties** plaatsen en
onderhouden bij klanten (batterijsystemen, warmtepompen, laadpalen, ...),
met hun logistiek en een portaal voor installateurs en distributeurs.
Geëxtraheerd uit de klantspecifieke GridSync-modules (`DF-DataForge/GridSync19`),
zonder klantnamen, logo's of hardgecodeerde producten.

## Modules

| Module | Verplicht | Inhoud |
|---|---|---|
| `serviq_installation` | ja | Installaties met componenten en serienummers, categorieën, componentrollen, types interventie, automatische aanmaak bij levering, status volgens interventies, overzichtsdashboard, planningskalender, slot picker, urenoverzicht |
| `serviq_installation_map` | automatisch, uit te schakelen | Locatie en kaart: op de installatie (klikken / marker verslepen), paneel op het overzicht, volledige kaart, geolocatie van het adres; Leaflet + OpenStreetMap (Community) |
| `serviq_logistics` | optioneel | Logistieke dashboards: overzicht, voorraad (met Excel-export), beschikbare voorraad, serienummers, inkomende en uitgaande goederen, reserveonderdelen |
| `serviq_portal` | optioneel | Portaal voor installateurs en distributeurs + het **flow-framework** |
| `serviq_flow_first_installation` | optioneel | Flow: installatie registreren bij de eerste installatie |
| `serviq_flow_commissioning` | optioneel | Flow: componentgegevens aanvullen en inbedrijfstelling afronden |
| `serviq_flow_replacement` | optioneel | Flow: component vervangen met historiek |
| `serviq_flow_refrigerant` | optioneel | Flow: registratie van een koeltechnisch systeem en zijn koudemiddellogboek (F-gassenverordening): ton CO2-eq, logboek- en lekcontroleplicht, gecertificeerde technicus/bedrijf, flesbalans, PDF-logboek |
| `serviq_demo_hvac` | nee, alleen demo | Demobedrijf: Belgische airco-installateur, alleen de installatieflows: units met serienummers, montagekits, reserveonderdelen, installatiepakketten, installaties met inbedrijfstelling, onderhoud en herstellingen, enkele weken historiek. Zie `serviq_demo_hvac/README.md` en de demo-walkthrough `serviq_demo_hvac/WALKTHROUGH.md` |

Alle optionele modules zijn aan of uit te zetten via
**Installaties > Configuratie > Instellingen** (aanvinken installeert de
module, uitvinken verwijdert ze). Geïnstalleerde flows kunnen daarnaast
per flow geactiveerd/gedeactiveerd en aan types interventie gekoppeld worden
in **Installaties > Configuratie > Flows**.

## Configureerbaar in plaats van hardgecodeerd

| GridSync (hardgecodeerd) | Serviq (data) |
|---|---|
| `battery.system` / "Batterijsysteem" | `serviq.installation` / "Installatie" |
| `df_battery_type` residential / industrial | `serviq.installation.category` (inbedrijfstelling vereist, actief na eerste installatie, aanmaken bij levering, installatieproduct, interventie na levering) |
| `df_product_type` battery_system / battery / inverter / ems / spare_part | `serviq.component.role` (installatieproduct, vervangbaar, reserveonderdeel) |
| `df_product_subgroup` | `product.template.serviq_category_id` |
| `df_type_of_intervention` (selection) | `serviq.intervention.type` (groep, telt als service, eerste installatie, inbedrijfstelling) |
| C&I-systeem aanmaken bij levering met vast product "Battery System C&I" | per categorie: één installatie met installatieproduct, of één installatie per geleverde eenheid |
| Leverancier "Poweroad" voor reservevoorraad | componentrol "Reserveonderdeel" + optionele leveranciersfilter |
| Portaalflows vast in één controller | `serviq.portal.flow` + handler per flow-module |

## Een nieuwe flow toevoegen

Zie `serviq_portal/README.md`: een flow is een kleine module die afhangt van
`serviq_portal`, een handler-model, een QWeb-sectie en een
`serviq.portal.flow`-record levert.

## Niet meegenomen (GridSync-specifiek)

Technische batterijparameters (AC/DC, EMS, dongles, koeling, netnormen),
GDPR-toestemming en de batterij-atlas, de registratiewizard met vaste
residentiële productconfiguraties, verkooporder op de distributeur
(Field Service-specifiek), financiële en cashflow-dashboards, en de overige
GridSync-modules (facturatie, documenten, FedEx, rapporten, ...).
Deze kunnen als aparte uitbreidingsmodules op Serviq gebouwd worden.
