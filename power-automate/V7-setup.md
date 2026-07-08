# V7 setup

Voeg in SharePoint drie kolommen toe als één regel tekst:

- UserName
- Organization
- Email

Vervang daarna in Power Automate het JSON-schema door `power-automate/request-schema-v7.json`.

Koppel in Create item ook:

- UserName -> userName
- Organization -> organization
- Email -> email

Response mag verwijderd blijven voor deze analytics-flow.
