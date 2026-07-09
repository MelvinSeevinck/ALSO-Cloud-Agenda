# ALSO Cloud Events - V15.1 Restored Tracking & Logo

Volledige herstelversie.

## Teruggezet

- Publieke pagina vraagt verplicht om naam, organisatie en e-mailadres.
- Abonneren en eventknoppen zijn geblokkeerd totdat de gegevens zijn opgeslagen.
- Tracking stuurt userName, organization en email mee naar de bestaande Power Automate tracking-flow.
- ALSO-logo staat op publieke en adminpagina.
- Power Automate URL's blijven intact in `data/config.json`.
- `tracking-schema.json` is verwijderd.

## Structuur

- `data/events-source.json` is de bron.
- `docs/events-admin.json` bevat alle events voor admin.
- `docs/events.json` bevat alleen published events.
- `docs/calendar.ics` bevat alleen published events.
