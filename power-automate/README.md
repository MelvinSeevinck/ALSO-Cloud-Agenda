# Power Automate stappen

## 1. SharePoint-lijst maken

Maak een SharePoint-lijst aan, bijvoorbeeld:

ALSO Cloud Events Usage

Kolommen:

- TimestampUtc — Date and Time
- Source — Single line of text
- Action — Single line of text
- CalendarType — Single line of text
- EventId — Single line of text
- EventTitle — Single line of text
- PartnerCode — Single line of text
- Campaign — Single line of text
- PageUrl — Multiple lines of text
- Referrer — Multiple lines of text
- UserAgent — Multiple lines of text
- Language — Single line of text
- SessionId — Single line of text

Gebruik de standaardkolom Title als korte omschrijving, bijvoorbeeld:

Action - CalendarType

## 2. Flow maken

Maak een nieuwe Power Automate cloud flow.

Kies:

When a HTTP request is received

Gebruik het schema uit:

power-automate/request-schema.json

## 3. SharePoint item aanmaken

Voeg actie toe:

Create item

Koppel de velden uit de HTTP body aan de SharePoint-kolommen.

Voor Title kun je gebruiken:

Action CalendarType

## 4. Response toevoegen

Voeg actie toe:

Response

Status code:

200

Body:

{
  "status": "ok"
}

## 5. URL kopiëren

Sla de flow op.

Kopieer de HTTP POST URL uit de trigger.

Plak die in:

events.yml

bij:

tracking.endpoint_url

## 6. Testen

Open de GitHub Pages website.

Klik op Outlook Calendar.

Controleer of er een nieuwe regel in de SharePoint-lijst verschijnt.
