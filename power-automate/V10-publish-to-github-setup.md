# V10 - Publiceer events automatisch naar GitHub

Doel: de adminpagina kan via Power Automate `events.yml` aanpassen.

## Flow

```text
When an HTTP request is received
↓
Condition: adminKey klopt
↓
HTTP GET GitHub file
↓
Compose: decode bestaande events.yml
↓
Compose: vervang events:-sectie
↓
HTTP PUT GitHub file
```

## Trigger schema

Gebruik `power-automate/publish-to-github-schema.json`.

## GitHub token

Maak een fine-grained GitHub token met:
- Repository: ALSO-Cloud-Agenda
- Contents: Read and write

Zet deze token alleen in Power Automate, nooit in GitHub Pages.

## GitHub GET

Method: `GET`

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

## Nieuwe YAML samenstellen

Logica:

```text
existingYaml = base64ToString(body('HTTP_GET')?['content'])
prefix = substring(existingYaml, 0, indexOf(existingYaml, 'events:'))
newYaml = concat(prefix, triggerBody()?['eventsYaml'])
```

Daarna gebruik je:

```text
base64(newYaml)
```

## GitHub PUT

Method: `PUT`

URI:

```text
https://api.github.com/repos/@{triggerBody()?['repository']}/contents/@{triggerBody()?['filePath']}
```

Body:

```json
{
  "message": "@{triggerBody()?['commitMessage']}",
  "content": "<base64(newYaml)>",
  "sha": "<sha uit GET>",
  "branch": "@{triggerBody()?['branch']}"
}
```

## In events.yml invullen

```yaml
admin_publish:
  enabled: true
  endpoint_url: "POWER_AUTOMATE_URL"
  admin_key: "DEZELFDE_GEHEIME_KEY"
  repository: "MelvinSeevinck/ALSO-Cloud-Agenda"
  branch: "main"
  file_path: "events.yml"
```
