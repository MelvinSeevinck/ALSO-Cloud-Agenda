# Pilot testplan V16.2

## Publieke pagina
1. Open in privévenster.
2. Controleer dat abonnementsknoppen, links en Outlook-uitleg niet zichtbaar zijn.
3. Vul naam, organisatie en e-mailadres in.
4. Controleer dat alle opties zichtbaar worden.
5. Test Outlook Web: link wordt gekopieerd en Outlook Web opent.
6. Test Outlook Desktop: webcal-link wordt gekopieerd en handleiding klopt.
7. Test Apple en Google.
8. Controleer tracking in Power Automate/SharePoint.

## Admin
1. Log in met admin key.
2. Upload banner.
3. Controleer bestand in `docs/assets/banners/`.
4. Sla event lokaal op.
5. Publiceer naar GitHub.
6. Controleer `data/events-source.json`, Actions en publieke pagina.

## Agenda-abonnement
1. Controleer dat de URL exact `https://melvinseevinck.github.io/ALSO-Cloud-Agenda/calendar.ics` blijft.
2. Wijzig een bestaand event.
3. Controleer dat de wijziging na Outlook-refresh verschijnt.


## Trackingtest V16.3
1. Open de publieke pagina met Ctrl + F5.
2. Sla naam, organisatie en e-mailadres op.
3. Controleer de run history van `agenda registraties`.
4. Controleer het SharePoint-item met actie `identity_saved`.
5. Klik op een filter en abonnementsknop.
6. Controleer `filter_click` en `subscribe_click`.
7. In de browserconsole mag geen CORS-fout voor de trackingflow staan.
