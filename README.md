# ALSO Cloud Events

ALSO Cloud Events is een statische GitHub Pages-oplossing waarmee ALSO Nederland events centraal kan beheren, publiceren en aanbieden als agenda-abonnement.

## Hoe werkt de tool?

1. Events worden beheerd via `docs/admin.html`.
2. De adminpagina leest alle events uit `docs/events-admin.json`.
3. Bij publiceren stuurt de adminpagina de volledige eventlijst naar Power Automate.
4. Power Automate schrijft de eventlijst naar `data/events-source.json` in GitHub.
5. GitHub Actions voert `generate_calendar.py` uit.
6. De generator valideert de brondata en maakt:
   - `docs/config.json`
   - `docs/events-admin.json`
   - `docs/events.json`
   - `docs/calendar.ics`
7. GitHub Pages publiceert de publieke pagina en het agenda-abonnement.
8. Bezoekers vullen naam, organisatie en e-mailadres in voordat ze kunnen abonneren.
9. Kliks en abonnementen worden via de tracking-flow naar SharePoint geschreven.

## Belangrijke bestanden

- `data/config.json` — configuratie, categorieën en Power Automate endpoints
- `data/events-source.json` — enige bron voor alle events
- `generate_calendar.py` — validatie en generatie van JSON/ICS
- `docs/index.html` — publieke pagina
- `docs/admin.html` — beheerpagina
- `docs/calendar.ics` — stabiele agenda-abonnementsfeed
- `.github/workflows/build-calendar.yml` — automatische validatie en generatie

## Statussen

- `Draft` — alleen zichtbaar in admin
- `Published` — zichtbaar op publieke pagina en in agenda
- `Archived` — bewaard in admin, niet publiek

## Featured

- `Ja` — event wordt bovenaan de publieke pagina uitgelicht
- `Nee` — event staat tussen de gewone events

## Stabiliteit van het agenda-abonnement

De abonnements-URL blijft altijd:

```text
https://melvinseevinck.github.io/ALSO-Cloud-Agenda/calendar.ics
```

Verander of verwijder dit pad nooit. Nieuwe versies mogen alleen de inhoud van het bestand wijzigen. De workflow controleert vóór iedere commit of `calendar.ics` geldig en niet leeg is.

## Versiehistorie

### V10
Eerste automatische publicatie vanuit de adminpagina via Power Automate naar GitHub.

### V11
Overgang naar `data/events-source.json` als centrale bron.

### V12
Uitgebreide CMS-functies: wijzigen, verwijderen, dupliceren en live preview.

### V12.1
Verplichte velden en verbeterde webcal-weergave.

### V13
Draft, Published en Archived toegevoegd, plus templates en uitgebreid dashboard.

### V14
Schone rebuild met validatie en aparte admin/public JSON-bestanden.

### V15
Volledige repositoryvervanging en stabielere GitHub Actions-opzet.

### V15.1
Gebruikersregistratie, tracking en ALSO-logo hersteld.

### V15.2
Categorie-dropdown hersteld en automatische unieke IDs toegevoegd.

### V16 Final
- Banner upload met automatische verkleining
- Uitleg-iconen bij Status en Featured
- Categorieën `ALSO Monthly Webinar` en `Overige`
- Adminomgeving pas zichtbaar na admin key
- Webcal-link pas zichtbaar na gebruikersregistratie
- Outlook direct via `webcal://`, met automatische kopieerfallback
- Filters boven Featured event
- Workflowcontrole om agenda-abonnement stabiel te houden
- Volledige README en versiehistorie


### V16.1 Final Banner Upload
- Banner upload via Power Automate en GitHub API
- Afbeeldingen als losse bestanden in `docs/assets/banners/`
- Geen Base64 meer in eventdata
- Automatische verkleining naar maximaal 1600 × 900
- Automatische unieke bestandsnaam op basis van eventtitel
