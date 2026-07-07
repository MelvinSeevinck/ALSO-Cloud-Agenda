from pathlib import Path
from datetime import datetime, timedelta, timezone, date
import html
import json
import sys
import urllib.parse
import yaml

ROOT = Path(__file__).resolve().parent
DOCS = ROOT / "docs"
EVENTS_FILE = ROOT / "events.yml"

def fail(message: str):
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)

def esc_ics(value: str) -> str:
    value = str(value or "")
    return value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\r\n", "\\n").replace("\n", "\\n")

def fold_ics_line(line: str) -> str:
    result, current = [], ""
    for char in line:
        test = current + char
        if len(test.encode("utf-8")) > 72:
            result.append(current)
            current = " " + char
        else:
            current = test
    result.append(current)
    return "\r\n".join(result)

def load_data():
    with EVENTS_FILE.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        fail("events.yml heeft geen geldige structuur.")
    return data

def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()

def event_start_date(event: dict) -> date:
    if event.get("all_day", False):
        return parse_date(event["date"])
    return datetime.fromisoformat(event["start"]).date()

def validate(data: dict):
    ids = set()
    categories = set((data.get("categories") or {}).keys())
    for event in data.get("events", []):
        event_id = event.get("id")
        if not event_id:
            fail("Een event mist een id.")
        if event_id in ids:
            fail(f"Dubbele event-id gevonden: {event_id}")
        ids.add(event_id)
        if not event.get("title"):
            fail(f"Event {event_id} mist een title.")
        if event.get("category") and event["category"] not in categories:
            fail(f"Event {event_id} gebruikt onbekende category: {event['category']}")
        if event.get("all_day", False):
            if not event.get("date"):
                fail(f"Event {event_id} heeft all_day: true maar mist date.")
            parse_date(event["date"])
        else:
            if not event.get("start") or not event.get("end"):
                fail(f"Event {event_id} heeft all_day: false maar mist start of end.")
            start = datetime.fromisoformat(event["start"])
            end = datetime.fromisoformat(event["end"])
            if end <= start:
                fail(f"Event {event_id} heeft een end die niet na start ligt.")

def category_label(data: dict, key: str) -> str:
    categories = data.get("categories") or {}
    return categories.get(key, {}).get("label", key or "ALSO Cloud")

def build_description(event: dict) -> str:
    description = event.get("description", "")
    if event.get("registration_url"):
        description = f"{description}\n\nAanmelden / meer informatie: {event['registration_url']}".strip()
    return description

def build_ics(data: dict) -> str:
    calendar = data.get("calendar", {})
    events = sorted(data.get("events", []), key=event_start_date)
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    timezone_name = calendar.get("timezone", "Europe/Amsterdam")
    agenda_name = calendar.get("agenda_name", calendar.get("name", "ALSO Cloud Agenda"))

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//ALSO Nederland B.V.//ALSO Cloud Agenda//NL",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{esc_ics(agenda_name)}",
        f"NAME:{esc_ics(agenda_name)}",
        f"X-WR-CALDESC:{esc_ics(calendar.get('description', ''))}",
        f"X-WR-TIMEZONE:{esc_ics(timezone_name)}",
        "REFRESH-INTERVAL;VALUE=DURATION:PT12H",
        "X-PUBLISHED-TTL:PT12H",
    ]

    for event in events:
        uid = f"{event['id']}@also-cloud-agenda"
        lines += [
            "BEGIN:VEVENT",
            f"UID:{esc_ics(uid)}",
            f"DTSTAMP:{now}",
            f"SUMMARY:{esc_ics(event.get('title', ''))}",
            f"LOCATION:{esc_ics(event.get('location', ''))}",
            f"DESCRIPTION:{esc_ics(build_description(event))}",
            f"CATEGORIES:{esc_ics(category_label(data, event.get('category', '')))}",
        ]
        if event.get("registration_url"):
            lines.append(f"URL:{esc_ics(event['registration_url'])}")
        if event.get("all_day", False):
            start = parse_date(event["date"])
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
    return "\r\n".join(fold_ics_line(line) for line in lines) + "\r\n"

def display_date(event: dict) -> str:
    if event.get("all_day", False):
        d = datetime.strptime(event["date"], "%Y-%m-%d")
        return d.strftime("%d-%m-%Y")
    start = datetime.fromisoformat(event["start"])
    end = datetime.fromisoformat(event["end"])
    return f"{start.strftime('%d-%m-%Y %H:%M')} - {end.strftime('%H:%M')}"

def tag_html(event: dict) -> str:
    tags = event.get("tags") or []
    return "".join(f"<span>{html.escape(str(tag))}</span>" for tag in tags)

def event_datetime_for_links(event: dict):
    if event.get("all_day", False):
        start = datetime.strptime(event["date"], "%Y-%m-%d")
        end = start + timedelta(days=1)
        return start.strftime("%Y%m%d"), end.strftime("%Y%m%d")
    start = datetime.fromisoformat(event["start"])
    end = datetime.fromisoformat(event["end"])
    return start.strftime("%Y%m%dT%H%M%S"), end.strftime("%Y%m%dT%H%M%S")

def event_google_link(event: dict) -> str:
    start, end = event_datetime_for_links(event)
    description = build_description(event)
    params = {
        "action": "TEMPLATE",
        "text": event.get("title", ""),
        "dates": f"{start}/{end}",
        "details": description,
        "location": event.get("location", ""),
    }
    return "https://calendar.google.com/calendar/render?" + urllib.parse.urlencode(params)

def single_event_ics_url(event: dict) -> str:
    # We still use the complete calendar feed for Outlook/Apple, because static GitHub Pages cannot generate
    # unique .ics files per event without adding more generated output files.
    return "calendar.ics"

def build_event_card(data: dict, event: dict) -> str:
    label = html.escape(category_label(data, event.get("category", "")))
    description = html.escape(event.get("description", "")).replace("\n", "<br>")
    event_id = html.escape(event.get("id", ""))
    event_title = html.escape(event.get("title", ""))

    registration = ""
    if event.get("registration_url"):
        url = html.escape(event["registration_url"])
        registration = f'<a class="small-button tracked-link" href="{url}" data-action="registration_click" data-calendar-type="registration" data-event-id="{event_id}" data-event-title="{event_title}">Aanmelden</a>'

    google_event_url = html.escape(event_google_link(event))
    outlook_event_url = html.escape(single_event_ics_url(event))
    apple_event_url = html.escape(single_event_ics_url(event))

    calendar_buttons = f"""
      <div class="event-actions">
        <a class="small-button tracked-link" href="{outlook_event_url}" data-action="event_calendar_click" data-calendar-type="outlook" data-event-id="{event_id}" data-event-title="{event_title}">Outlook</a>
        <a class="small-button secondary tracked-link" href="{apple_event_url}" data-action="event_calendar_click" data-calendar-type="apple" data-event-id="{event_id}" data-event-title="{event_title}">Apple</a>
        <a class="small-button light tracked-link" href="{google_event_url}" target="_blank" rel="noopener" data-action="event_calendar_click" data-calendar-type="google" data-event-id="{event_id}" data-event-title="{event_title}">Google</a>
        {registration}
      </div>
    """

    featured = " featured" if event.get("featured") else ""
    return f"""
    <article class="event-card{featured}" data-category="{html.escape(event.get('category', ''))}" data-search="{html.escape((event.get('title','') + ' ' + event.get('description','') + ' ' + ' '.join(event.get('tags') or [])).lower())}">
      <div class="event-date">{html.escape(display_date(event))}</div>
      <div class="event-content">
        <div class="event-category">{label}</div>
        <h3>{event_title}</h3>
        <p class="location">{html.escape(event.get("location", ""))}</p>
        <div class="tags">{tag_html(event)}</div>
        <p>{description}</p>
        {calendar_buttons}
      </div>
    </article>
    """

def build_index(data: dict) -> str:
    calendar = data.get("calendar", {})
    settings = data.get("settings", {})
    tracking = data.get("tracking", {})
    site_url = calendar.get("site_url", "").rstrip("/") + "/"
    https_ics_url = site_url + "calendar.ics"
    webcal_url = https_ics_url.replace("https://", "webcal://").replace("http://", "webcal://")
    google_url = "https://calendar.google.com/calendar/render?cid=" + urllib.parse.quote(webcal_url, safe="")
    outlook_desktop_url = https_ics_url

    today = datetime.now().date()
    events = sorted(data.get("events", []), key=event_start_date)
    if not settings.get("show_past_events", False):
        events = [event for event in events if event_start_date(event) >= today]

    featured_events = [event for event in events if event.get("featured")]
    normal_events = [event for event in events if not event.get("featured")]
    if not featured_events and events:
        featured_events = [events[0]]
        normal_events = events[1:]

    featured_cards = "".join(build_event_card(data, event) for event in featured_events) or "<p>Er staat momenteel geen featured event gepland.</p>"
    event_cards = "".join(build_event_card(data, event) for event in normal_events) or "<p>Er staan momenteel geen overige events gepland.</p>"

    category_buttons = ['<button class="filter active" data-filter="all">Alle events</button>']
    for key, value in (data.get("categories") or {}).items():
        category_buttons.append(f'<button class="filter" data-filter="{html.escape(key)}">{html.escape(value.get("label", key))}</button>')

    tracking_config_json = json.dumps({
        "enabled": bool(tracking.get("enabled", False)),
        "endpointUrl": tracking.get("endpoint_url", ""),
        "source": tracking.get("source", "ALSO Cloud Events"),
    }, ensure_ascii=False)

    privacy_notice = tracking.get("privacy_notice", "")
    privacy_html = f'<p class="hint">{html.escape(privacy_notice)}</p>' if privacy_notice else ""

    return f"""<!doctype html>
<html lang="nl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(calendar.get("name", "ALSO Cloud Events"))}</title>
  <style>
    :root {{ --bg:#f4f6fb; --card:#fff; --text:#1f2937; --muted:#6b7280; --dark:#111827; --border:#e5e7eb; --accent:#2563eb; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font-family:Arial,sans-serif; background:var(--bg); color:var(--text); line-height:1.55; }}
    header {{ background:linear-gradient(135deg,#111827,#1f2937); color:white; padding:56px 24px; }}
    .wrap, main {{ max-width:1120px; margin:0 auto; }}
    main {{ padding:32px 24px 48px; }}
    .eyebrow {{ color:#bfdbfe; font-weight:bold; letter-spacing:.04em; text-transform:uppercase; font-size:13px; }}
    h1 {{ font-size:42px; margin:8px 0 12px; }}
    header p {{ max-width:850px; font-size:18px; }}
    .panel {{ background:var(--card); border:1px solid var(--border); border-radius:18px; padding:24px; margin-bottom:24px; box-shadow:0 1px 3px rgba(0,0,0,.04); }}
    .button-row {{ display:flex; flex-wrap:wrap; gap:12px; margin:18px 0; }}
    .button {{ display:inline-block; background:var(--dark); color:white; padding:12px 18px; border-radius:10px; text-decoration:none; font-weight:bold; }}
    .button.secondary {{ background:#374151; }}
    .button.light {{ background:#eef2ff; color:#111827; }}
    .small-button {{ display:inline-block; background:#111827; color:white; padding:9px 13px; border-radius:8px; text-decoration:none; font-weight:bold; margin:4px 6px 4px 0; }}
    .small-button.secondary {{ background:#374151; }}
    .small-button.light {{ background:#eef2ff; color:#111827; }}
    .event-actions {{ display:flex; flex-wrap:wrap; gap:6px; margin-top:14px; }}
    code {{ background:#f3f4f6; padding:3px 6px; border-radius:6px; word-break:break-all; }}
    .hint {{ color:var(--muted); font-size:14px; margin-top:8px; }}
    .toolbar {{ display:flex; flex-wrap:wrap; gap:12px; align-items:center; margin-bottom:18px; }}
    .toolbar input {{ flex:1; min-width:240px; padding:12px; border:1px solid var(--border); border-radius:10px; font:inherit; }}
    .filter {{ border:1px solid var(--border); background:white; padding:10px 12px; border-radius:999px; cursor:pointer; }}
    .filter.active {{ background:#111827; color:white; border-color:#111827; }}
    .event-card {{ display:grid; grid-template-columns:170px 1fr; gap:24px; border-top:1px solid var(--border); padding:24px 0; }}
    .event-card:first-child {{ border-top:none; padding-top:0; }}
    .event-card.featured {{ border:1px solid #dbeafe; background:#f8fbff; border-radius:16px; padding:22px; }}
    .event-date {{ font-weight:bold; color:var(--dark); }}
    .event-category {{ color:var(--accent); font-size:14px; font-weight:bold; margin-bottom:4px; }}
    .event-content h3 {{ margin:0 0 4px; }}
    .location {{ color:var(--muted); margin-top:0; }}
    .tags {{ display:flex; flex-wrap:wrap; gap:6px; margin:10px 0; }}
    .tags span {{ background:#eef2ff; color:#1f2937; border-radius:999px; padding:4px 8px; font-size:12px; }}
    footer {{ color:var(--muted); font-size:14px; padding-top:8px; }}
    @media (max-width:720px) {{ h1 {{ font-size:32px; }} .event-card {{ grid-template-columns:1fr; gap:8px; }} }}
  </style>
</head>
<body>
  <header>
    <div class="wrap">
      <div class="eyebrow">ALSO Nederland B.V.</div>
      <h1>{html.escape(calendar.get("name", "ALSO Cloud Events"))}</h1>
      <p>{html.escape(calendar.get("description", ""))}</p>
    </div>
  </header>
  <main>
    <section class="panel">
      <h2>Abonneer op de agenda</h2>
      <p>Voeg deze agenda één keer toe aan je eigen agenda-app. Nieuwe events, wijzigingen en verwijderingen worden daarna automatisch verwerkt zodra de agenda-app synchroniseert.</p>
      <div class="button-row">
        <a class="button tracked-link" href="{html.escape(outlook_desktop_url)}" data-action="subscribe_click" data-calendar-type="outlook" data-event-id="" data-event-title="">Outlook Calendar</a>
        <a class="button secondary tracked-link" href="{html.escape(webcal_url)}" data-action="subscribe_click" data-calendar-type="apple" data-event-id="" data-event-title="">Apple Calendar</a>
        <a class="button light tracked-link" href="{html.escape(google_url)}" target="_blank" rel="noopener" data-action="subscribe_click" data-calendar-type="google" data-event-id="" data-event-title="">Google Calendar</a>
        <a class="button light" href="admin.html">Event Builder</a>
      </div>
      <p class="hint">Outlook Calendar downloadt het kalenderbestand. Als Outlook Desktop gekoppeld is aan .ics-bestanden, opent Outlook automatisch. Outlook Web kan alsnog om een naam vragen; gebruik dan <strong>ALSO Cloud Agenda</strong>.</p>
      {privacy_html}
      <p>Directe abonnementslink:</p>
      <p><code>{html.escape(https_ics_url)}</code></p>
      <p>Webcal-link:</p>
      <p><code>{html.escape(webcal_url)}</code></p>
    </section>

    <section class="panel">
      <h2>Featured event</h2>
      {featured_cards}
    </section>

    <section class="panel">
      <h2>Alle geplande events</h2>
      <div class="toolbar">
        <input id="search" type="search" placeholder="Zoek op titel, onderwerp of tag...">
      </div>
      <div class="button-row">{''.join(category_buttons)}</div>
      <div id="events">{event_cards}</div>
    </section>
    <footer>Deze kalender wordt automatisch gepubliceerd vanuit GitHub Pages.</footer>
  </main>
  <script>
    window.ALSO_TRACKING_CONFIG = {tracking_config_json};

    function getQueryParam(name) {{
      const params = new URLSearchParams(window.location.search);
      return params.get(name) || "";
    }}

    function getSessionId() {{
      const key = "alsoCloudEventsSessionId";
      let value = sessionStorage.getItem(key);
      if (!value) {{
        value = (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random());
        sessionStorage.setItem(key, value);
      }}
      return value;
    }}

    async function trackUsage(payload) {{
      const config = window.ALSO_TRACKING_CONFIG || {{}};
      if (!config.enabled || !config.endpointUrl) return;

      const body = {{
        timestampUtc: new Date().toISOString(),
        source: config.source || "ALSO Cloud Events",
        action: payload.action || "",
        calendarType: payload.calendarType || "",
        eventId: payload.eventId || "",
        eventTitle: payload.eventTitle || "",
        partnerCode: getQueryParam("partner") || getQueryParam("partnerCode") || "",
        campaign: getQueryParam("campaign") || getQueryParam("utm_campaign") || "",
        pageUrl: window.location.href,
        referrer: document.referrer || "",
        userAgent: navigator.userAgent || "",
        language: navigator.language || "",
        sessionId: getSessionId()
      }};

      try {{
        const blob = new Blob([JSON.stringify(body)], {{ type: "application/json" }});
        if (navigator.sendBeacon) {{
          navigator.sendBeacon(config.endpointUrl, blob);
        }} else {{
          await fetch(config.endpointUrl, {{
            method: "POST",
            headers: {{ "Content-Type": "application/json" }},
            body: JSON.stringify(body),
            keepalive: true
          }});
        }}
      }} catch (e) {{
        console.warn("Tracking failed", e);
      }}
    }}

    document.querySelectorAll(".tracked-link").forEach(link => {{
      link.addEventListener("click", () => {{
        trackUsage({{
          action: link.dataset.action,
          calendarType: link.dataset.calendarType,
          eventId: link.dataset.eventId,
          eventTitle: link.dataset.eventTitle
        }});
      }});
    }});

    trackUsage({{ action: "page_view", calendarType: "", eventId: "", eventTitle: "" }});

    const filters = document.querySelectorAll('.filter');
    const cards = document.querySelectorAll('.event-card');
    const search = document.getElementById('search');
    let activeFilter = 'all';

    function applyFilters() {{
      const q = (search.value || '').toLowerCase();
      cards.forEach(card => {{
        const categoryMatch = activeFilter === 'all' || card.dataset.category === activeFilter;
        const searchMatch = !q || card.dataset.search.includes(q);
        card.style.display = categoryMatch && searchMatch ? '' : 'none';
      }});
    }}

    filters.forEach(btn => {{
      btn.addEventListener('click', () => {{
        filters.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        activeFilter = btn.dataset.filter;
        applyFilters();
        trackUsage({{ action: "filter_click", calendarType: btn.dataset.filter, eventId: "", eventTitle: "" }});
      }});
    }});
    search.addEventListener('input', applyFilters);
  </script>
</body>
</html>
"""

def build_admin(data: dict) -> str:
    categories = data.get("categories", {})
    options = "\\n".join(f'<option value="{html.escape(k)}">{html.escape(v.get("label", k))}</option>' for k, v in categories.items())
    return f"""<!doctype html>
<html lang="nl">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Event Builder - ALSO Cloud Events</title>
<style>
body{{font-family:Arial,sans-serif;margin:0;background:#f4f6fb;color:#1f2937;line-height:1.5}}main{{max-width:900px;margin:0 auto;padding:32px 24px}}.panel{{background:white;border:1px solid #e5e7eb;border-radius:16px;padding:24px;margin-bottom:24px}}label{{display:block;font-weight:bold;margin-top:14px}}input,select,textarea{{width:100%;padding:10px;border:1px solid #d1d5db;border-radius:8px;margin-top:6px;font:inherit}}textarea{{min-height:120px}}button{{background:#111827;color:white;padding:12px 18px;border:0;border-radius:8px;font-weight:bold;margin-top:16px;cursor:pointer}}pre{{white-space:pre-wrap;background:#111827;color:white;padding:18px;border-radius:12px;overflow:auto}}code{{background:#f3f4f6;padding:3px 6px;border-radius:6px}}
</style></head>
<body><main><section class="panel"><h1>Event Builder</h1><p>Vul hieronder een event in. Deze pagina maakt automatisch een correct YAML-blok. Kopieer het resultaat naar <code>events.yml</code> onder <code>events:</code>.</p>
<label>Titel</label><input id="title" placeholder="🟦 Webinar - Azure Backup">
<label>Unieke ID</label><input id="id" placeholder="webinar-azure-backup-2026-10-15">
<label>Categorie</label><select id="category">{options}</select>
<label>Featured event?</label><select id="featured"><option value="false">Nee</option><option value="true">Ja</option></select>
<label>Hele dag?</label><select id="allDay"><option value="false">Nee, met start- en eindtijd</option><option value="true">Ja, hele dag</option></select>
<label>Datum</label><input id="date" type="date">
<label>Starttijd</label><input id="startTime" type="time" value="10:00">
<label>Eindtijd</label><input id="endTime" type="time" value="11:00">
<label>Locatie</label><input id="location" placeholder="Microsoft Teams">
<label>Registratie URL</label><input id="registration" placeholder="https://...">
<label>Tags, gescheiden met komma's</label><input id="tags" placeholder="Azure, Security, AI">
<label>Beschrijving</label><textarea id="description" placeholder="Korte beschrijving van het event."></textarea>
<button onclick="generateYaml()">Genereer YAML</button> <button onclick="copyYaml()">Kopieer resultaat</button></section>
<section class="panel"><h2>Resultaat</h2><pre id="output">Vul de velden in en klik op “Genereer YAML”.</pre></section></main>
<script>
function slugify(text){{return text.toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-+|-+$/g,'')}}
function indentDescription(text){{if(!text.trim()) return "      Meer informatie volgt binnenkort."; return text.split("\\n").map(line=>"      "+line).join("\\n")}}
function tagBlock(text){{const tags=text.split(',').map(t=>t.trim()).filter(Boolean); if(!tags.length)return "    tags: []\\n"; return "    tags:\\n"+tags.map(t=>"      - "+t).join("\\n")+"\\n"}}
function generateYaml(){{
 const title=document.getElementById('title').value||"Titel van het event";
 const id=document.getElementById('id').value||slugify(title);
 const category=document.getElementById('category').value;
 const featured=document.getElementById('featured').value==="true";
 const allDay=document.getElementById('allDay').value==="true";
 const date=document.getElementById('date').value||"2026-01-01";
 const startTime=document.getElementById('startTime').value||"10:00";
 const endTime=document.getElementById('endTime').value||"11:00";
 const location=document.getElementById('location').value||"Microsoft Teams";
 const registration=document.getElementById('registration').value||"";
 const tags=document.getElementById('tags').value||"";
 const description=document.getElementById('description').value||"Meer informatie volgt binnenkort.";
 let yaml=`  - id: "${{id}}"
    title: "${{title}}"
`;
 if(allDay){{yaml+=`    date: "${{date}}"
    all_day: true
`;}}else{{yaml+=`    start: "${{date}}T${{startTime}}:00"
    end: "${{date}}T${{endTime}}:00"
    all_day: false
`;}}
 yaml+=`    location: "${{location}}"
    category: "${{category}}"
    featured: ${{featured}}
${{tagBlock(tags)}}    registration_url: "${{registration}}"
    description: |
${{indentDescription(description)}}`;
 document.getElementById('output').textContent=yaml;
}}
function copyYaml(){{navigator.clipboard.writeText(document.getElementById('output').textContent)}}
</script></body></html>"""

def main():
    DOCS.mkdir(exist_ok=True)
    data = load_data()
    validate(data)
    (DOCS / "calendar.ics").write_text(build_ics(data), encoding="utf-8")
    (DOCS / "index.html").write_text(build_index(data), encoding="utf-8")
    (DOCS / "admin.html").write_text(build_admin(data), encoding="utf-8")
    (DOCS / "events.json").write_text(json.dumps(data.get("events", []), ensure_ascii=False, indent=2), encoding="utf-8")
    print("Generated docs/calendar.ics")
    print("Generated docs/index.html")
    print("Generated docs/admin.html")
    print("Generated docs/events.json")

if __name__ == "__main__":
    main()
