# ALSO Cloud Events

GitHub Pages eventkalender en agenda-abonnement voor Cloud partners van ALSO Nederland B.V.

## Wat zit hierin?

- GitHub Pages website
- iCalendar agenda-abonnement
- Event Builder
- Zoekfunctie en filters
- Featured event
- Trackinglaag voor Power Automate + SharePoint
- JSON-export

## Tracking instellen

Maak in SharePoint een lijst met deze kolommen:

| Kolom | Type |
|---|---|
| Title | Single line of text |
| TimestampUtc | Date and Time |
| Source | Single line of text |
| Action | Single line of text |
| CalendarType | Single line of text |
| EventId | Single line of text |
| EventTitle | Single line of text |
| PartnerCode | Single line of text |
| Campaign | Single line of text |
| PageUrl | Multiple lines of text |
| Referrer | Multiple lines of text |
| UserAgent | Multiple lines of text |
| Language | Single line of text |
| SessionId | Single line of text |

Maak daarna een Power Automate flow:

1. Trigger: When a HTTP request is received
2. JSON schema gebruiken uit `power-automate/request-schema.json`
3. Actie: Create item in SharePoint
4. Response: status 200

Plak de HTTP POST URL in `events.yml`:

```yaml
tracking:
  enabled: true
  endpoint_url: "PASTE_POWER_AUTOMATE_URL_HERE"
```

Commit daarna `events.yml`. GitHub Actions publiceert de site opnieuw.

## GitHub Pages

Gebruik:

```text
Source: Deploy from a branch
Branch: main
Folder: /docs
```
