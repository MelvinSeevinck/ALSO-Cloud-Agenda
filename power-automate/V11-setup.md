# V11 - ALSO Cloud Events Portal

## Wat is anders?

Events worden beheerd in:

```text
data/events-source.json
```

Niet meer in YAML.

De adminpagina kan events toevoegen, wijzigen en verwijderen en publiceert de volledige JSON-lijst via Power Automate naar GitHub.

## Power Automate publish-flow

Trigger: `When an HTTP request is received`

Schema:

```text
power-automate/publish-json-to-github-schema.json
```

Flow:

```text
HTTP trigger
↓
Condition adminKey
↓
HTTP GET GitHub file data/events-source.json
↓
HTTP PUT GitHub file data/events-source.json
```

GitHub token:
- Fine-grained token
- Contents: Read and write
- Alleen voor repository ALSO-Cloud-Agenda

## GET GitHub file

Method:

```text
GET
```

URI:

```text
https://api.github.com/repos/@{triggerBody()?['repository']}/contents/@{triggerBody()?['filePath']}?ref=@{triggerBody()?['branch']}
```

Headers:

```text
Authorization: Bearer <GITHUB_TOKEN>
Accept: application/vnd.github+json
X-GitHub-Api-Version: 2022-11-28
```

## PUT GitHub file

Method:

```text
PUT
```

URI:

```text
https://api.github.com/repos/@{triggerBody()?['repository']}/contents/@{triggerBody()?['filePath']}
```

Headers:

```text
Authorization: Bearer <GITHUB_TOKEN>
Accept: application/vnd.github+json
X-GitHub-Api-Version: 2022-11-28
Content-Type: application/json
```

Body:

```json
{
  "message": "@{triggerBody()?['commitMessage']}",
  "content": "@{base64(string(triggerBody()?['events']))}",
  "sha": "@{body('HTTP_GET')?['sha']}",
  "branch": "@{triggerBody()?['branch']}"
}
```

Let op: in Power Automate kan jouw HTTP GET actie een andere naam hebben dan `HTTP_GET`.

## data/config.json invullen

Na het maken van de publish-flow vul je in `data/config.json`:

```json
"adminPublish": {
  "enabled": true,
  "endpointUrl": "POWER_AUTOMATE_URL",
  "adminKey": "DEZELFDE_GEHEIME_KEY",
  "repository": "MelvinSeevinck/ALSO-Cloud-Agenda",
  "branch": "main",
  "filePath": "data/events-source.json"
}
```

## Tracking-flow

De bestaande tracking-flow blijft werken. Gebruik schema:

```text
power-automate/tracking-schema.json
```
