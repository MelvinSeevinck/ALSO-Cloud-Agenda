# ALSO Cloud Partner Calendar

GitHub Pages agenda-abonnement voor Cloud partners van ALSO Nederland B.V.

Deze kalender publiceert automatisch:

- een publieke website met geplande events;
- een `calendar.ics` bestand voor agenda-abonnementen;
- een Event Builder om nieuwe events makkelijker aan te maken;
- een JSON-export van de events.

## Beheer

Je beheert events in één bestand:

```text
events.yml
```

Na iedere wijziging draait GitHub Actions automatisch en worden deze bestanden opnieuw opgebouwd:

```text
docs/index.html
docs/calendar.ics
docs/admin.html
docs/events.json
```

## GitHub Pages

Gebruik deze instelling:

```text
Source: Deploy from a branch
Branch: main
Folder: /docs
```

## Nieuwe events toevoegen

Open de gepubliceerde website en ga naar:

```text
/admin.html
```

Vul het formulier in, kopieer het YAML-blok en plak dit onder `events:` in `events.yml`.

## Event wijzigen

Open `events.yml`, pas het bestaande event aan en commit de wijziging.

## Event verwijderen

Open `events.yml`, verwijder het volledige event-blok en commit de wijziging.

## Let op

Ieder event moet een unieke `id` hebben. Verander deze `id` niet nadat een event gepubliceerd is, tenzij het echt een nieuw event moet worden. Agenda-apps gebruiken deze `id` om wijzigingen te herkennen.
