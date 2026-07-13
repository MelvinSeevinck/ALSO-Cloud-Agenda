
from pathlib import Path
from datetime import datetime, timedelta, timezone
import json

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
DOCS = ROOT / "docs"

def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))

def parse_dt(event):
    if event.get("allDay"):
        return datetime.strptime(event["date"], "%Y-%m-%d")
    return datetime.fromisoformat(event["start"])

def validate(events):
    if not isinstance(events, list):
        raise SystemExit("data/events-source.json must be a JSON array.")

    ids = set()
    for event in events:
        for field in ["id", "title", "status", "location", "category", "registrationUrl", "description"]:
            if not str(event.get(field, "")).strip():
                raise SystemExit(f"Missing required field '{field}' in event: {event.get('id', 'unknown')}")

        if event["id"] in ids:
            raise SystemExit(f"Duplicate event id: {event['id']}")
        ids.add(event["id"])

        if event["status"] not in ["published", "draft", "archived"]:
            raise SystemExit(f"Invalid status for {event['id']}: {event['status']}")

        if not isinstance(event.get("tags"), list) or not event["tags"]:
            raise SystemExit(f"Event {event['id']} must have at least one tag.")

        if event.get("allDay"):
            datetime.strptime(event["date"], "%Y-%m-%d")
        else:
            start = datetime.fromisoformat(event["start"])
            end = datetime.fromisoformat(event["end"])
            if end <= start:
                raise SystemExit(f"Event {event['id']} has end before start.")

def escape_ics(value):
    return str(value or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")

def fold_ics(line):
    parts = []
    current = ""
    for char in line:
        if len((current + char).encode("utf-8")) > 72:
            parts.append(current)
            current = " " + char
        else:
            current += char
    parts.append(current)
    return "\r\n".join(parts)

def category_label(config, key):
    return config.get("categories", {}).get(key, {}).get("label", key or "")

def description_with_url(event):
    description = event.get("description", "").strip()
    url = event.get("registrationUrl", "").strip()
    if url:
        description += "\n\nAanmelden / meer informatie: " + url
    return description.strip()

def build_ics(config, events):
    timezone_name = config["calendar"].get("timezone", "Europe/Amsterdam")
    calendar_name = config["calendar"].get("agendaName", "ALSO Cloud Agenda")
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//ALSO Nederland B.V.//ALSO Cloud Agenda//NL",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{escape_ics(calendar_name)}",
        f"NAME:{escape_ics(calendar_name)}",
        f"X-WR-TIMEZONE:{escape_ics(timezone_name)}",
        "REFRESH-INTERVAL;VALUE=DURATION:PT12H",
        "X-PUBLISHED-TTL:PT12H",
    ]

    for event in sorted(events, key=parse_dt):
        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{escape_ics(event['id'])}@also-cloud-agenda",
            f"DTSTAMP:{now}",
            f"SUMMARY:{escape_ics(event['title'])}",
            f"LOCATION:{escape_ics(event['location'])}",
            f"DESCRIPTION:{escape_ics(description_with_url(event))}",
            f"CATEGORIES:{escape_ics(category_label(config, event.get('category')))}",
        ])

        if event.get("registrationUrl"):
            lines.append(f"URL:{escape_ics(event['registrationUrl'])}")

        if event.get("allDay"):
            start = datetime.strptime(event["date"], "%Y-%m-%d")
            end = start + timedelta(days=1)
            lines.append(f"DTSTART;VALUE=DATE:{start.strftime('%Y%m%d')}")
            lines.append(f"DTEND;VALUE=DATE:{end.strftime('%Y%m%d')}")
        else:
            start = datetime.fromisoformat(event["start"])
            end = datetime.fromisoformat(event["end"])
            lines.append(f"DTSTART;TZID={timezone_name}:{start.strftime('%Y%m%dT%H%M%S')}")
            lines.append(f"DTEND;TZID={timezone_name}:{end.strftime('%Y%m%dT%H%M%S')}")

        lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")
    return "\r\n".join(fold_ics(line) for line in lines) + "\r\n"

def main():
    config = load_json(DATA / "config.json")
    all_events = load_json(DATA / "events-source.json")
    validate(all_events)

    public_events = [event for event in all_events if event.get("status") == "published"]

    DOCS.mkdir(exist_ok=True)
    (DOCS / "config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    (DOCS / "events-admin.json").write_text(json.dumps(all_events, ensure_ascii=False, indent=2), encoding="utf-8")
    (DOCS / "events.json").write_text(json.dumps(public_events, ensure_ascii=False, indent=2), encoding="utf-8")
    (DOCS / "calendar.ics").write_text(build_ics(config, public_events), encoding="utf-8")

    print("Generated config.json, events-admin.json, events.json and calendar.ics")

if __name__ == "__main__":
    main()
