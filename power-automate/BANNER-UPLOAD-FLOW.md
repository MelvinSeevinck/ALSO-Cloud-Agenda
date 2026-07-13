# Power Automate: events publiceren en banners uploaden

V16.1 gebruikt dezelfde HTTP-trigger voor twee acties:

- eventlijst publiceren;
- banner uploaden.

## Trigger-schema

Vervang het schema van `When an HTTP request is received` door:

```text
power-automate/github-update-events-and-banner-schema.json
```

## Nieuwe Condition

Plaats binnen de `True`-tak van de adminKey-controle een Condition:

```text
triggerBody()?['action']
```

is gelijk aan:

```text
uploadBanner
```

## True: banner uploaden

HTTP URI:

```text
https://api.github.com/repos/MelvinSeevinck/ALSO-Cloud-Agenda/contents/@{triggerBody()?['folderPath']}/@{triggerBody()?['fileName']}
```

Methode:

```text
PUT
```

Headers:

```text
Authorization: Bearer JOUW_GITHUB_TOKEN
Accept: application/vnd.github+json
X-GitHub-Api-Version: 2022-11-28
Content-Type: application/json
```

Body:

```json
{
  "message": "Upload event banner",
  "content": "@{triggerBody()?['contentBase64']}",
  "branch": "@{coalesce(triggerBody()?['branch'], 'main')}"
}
```

Response statuscode:

```text
200
```

Response body:

```json
{
  "success": true,
  "bannerUrl": "@{concat('https://melvinseevinck.github.io/ALSO-Cloud-Agenda/assets/banners/', triggerBody()?['fileName'])}"
}
```

## False: bestaande event-publicatie

Laat hier de bestaande stappen staan:

1. GET `data/events-source.json`
2. Parse JSON
3. Compose JSON
4. Compose Base64
5. PUT `data/events-source.json`
6. Response

## Resultaat

De adminpagina:
1. verkleint de afbeelding naar maximaal 1600 × 900;
2. maakt een JPG met unieke bestandsnaam;
3. stuurt Base64 naar Power Automate;
4. Power Automate schrijft naar `docs/assets/banners/`;
5. Power Automate retourneert de publieke URL;
6. `bannerUrl` wordt automatisch gevuld.
