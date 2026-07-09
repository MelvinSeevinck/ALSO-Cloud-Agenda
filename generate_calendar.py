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
        registration = f'<a class="small-button tracked-link requires-identity" href="{url}" data-action="registration_click" data-calendar-type="registration" data-event-id="{event_id}" data-event-title="{event_title}">Aanmelden</a>'

    google_event_url = html.escape(event_google_link(event))
    site_url = (data.get("calendar", {}).get("site_url", "")).rstrip("/") + "/"
    calendar_url = site_url + "calendar.ics"
    webcal_url = calendar_url.replace("https://", "webcal://").replace("http://", "webcal://")
    outlook_event_url = html.escape(webcal_url)
    apple_event_url = html.escape(webcal_url)

    calendar_buttons = f"""
      <div class="event-actions">
        <a class="small-button tracked-link requires-identity" href="{outlook_event_url}" data-action="event_calendar_click" data-calendar-type="outlook" data-event-id="{event_id}" data-event-title="{event_title}">Outlook</a>
        <a class="small-button secondary tracked-link requires-identity" href="{apple_event_url}" data-action="event_calendar_click" data-calendar-type="apple" data-event-id="{event_id}" data-event-title="{event_title}">Apple</a>
        <a class="small-button light tracked-link requires-identity" href="{google_event_url}" target="_blank" rel="noopener" data-action="event_calendar_click" data-calendar-type="google" data-event-id="{event_id}" data-event-title="{event_title}">Google</a>
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
        "storageKey": (data.get("identity") or {}).get("storage_key", "alsoCloudEventsUser"),
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
    .logo {{ height:56px; width:auto; display:block; margin-bottom:28px; }}
    .eyebrow {{ color:#bfdbfe; font-weight:bold; letter-spacing:.04em; text-transform:uppercase; font-size:13px; }}
    h1 {{ font-size:42px; margin:8px 0 12px; }}
    header p {{ max-width:850px; font-size:18px; }}
    .panel {{ background:var(--card); border:1px solid var(--border); border-radius:18px; padding:24px; margin-bottom:24px; box-shadow:0 1px 3px rgba(0,0,0,.04); }}
    .button-row {{ display:flex; flex-wrap:wrap; gap:12px; margin:18px 0; }}
    .button {{ display:inline-block; background:var(--dark); color:white; padding:12px 18px; border-radius:10px; text-decoration:none; font-weight:bold; }}
    .button.secondary {{ background:#374151; }}
    .button.light {{ background:#eef2ff; color:#111827; }}
    .button.disabled, .small-button.disabled {{ opacity:.45; cursor:not-allowed; pointer-events:auto; }}
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
    .identity-box {{ background:#f8fbff; border:1px solid #dbeafe; border-radius:14px; padding:16px; margin-top:16px; }}
    .identity-grid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:12px; }}
    .identity-grid label {{ font-weight:bold; font-size:13px; }}
    .identity-grid input {{ width:100%; padding:10px; border:1px solid var(--border); border-radius:8px; margin-top:6px; font:inherit; }}
    #identityStatus {{ display:none; color:#065f46; font-weight:bold; }}
    footer {{ color:var(--muted); font-size:14px; padding-top:8px; }}
    @media (max-width:720px) {{ h1 {{ font-size:32px; }} .event-card {{ grid-template-columns:1fr; gap:8px; }} .identity-grid {{ grid-template-columns:1fr; }} }}
  </style>
</head>
<body>
  <header>
    <div class="wrap">
      <img class="logo" src="assets/also-logo.png" alt="ALSO logo">
      <div class="eyebrow">ALSO Nederland B.V.</div>
      <h1>{html.escape(calendar.get("name", "ALSO Cloud Events"))}</h1>
      <p>{html.escape(calendar.get("description", ""))}</p>
    </div>
  </header>
  <main>
    <section class="panel">
      <h2>Abonneer op de agenda</h2>
      <p>Voeg deze agenda één keer toe aan je eigen agenda-app. Nieuwe events, wijzigingen en verwijderingen worden daarna automatisch verwerkt zodra de agenda-app synchroniseert.</p>
      <div class="identity-box">
        <h3>Gegevens voor gebruiksregistratie</h3>
        <p class="hint">Vul deze gegevens één keer in. We gebruiken dit om te zien welke partners de agenda gebruiken en welke events relevant zijn.</p>
        <div class="identity-grid">
          <label>Naam<input id="userName" autocomplete="name" placeholder="Voor- en achternaam"></label>
          <label>Organisatie<input id="organization" autocomplete="organization" placeholder="Partnerorganisatie"></label>
          <label>E-mailadres<input id="email" autocomplete="email" type="email" placeholder="naam@organisatie.nl"></label>
        </div>
        <div class="button-row">
          <button class="button" onclick="saveIdentity()">Gegevens opslaan</button>
          <button class="button light" onclick="clearIdentity()">Gegevens wissen</button>
        </div>
        <div id="identityStatus">Gegevens opgeslagen. Je kunt de agenda nu toevoegen.</div>
      </div>
      <div class="button-row">
        <a class="button tracked-link requires-identity" href="{html.escape(webcal_url)}" data-action="subscribe_click" data-calendar-type="outlook" data-event-id="none" data-event-title="none">Outlook Calendar</a>
        <a class="button secondary tracked-link requires-identity" href="{html.escape(webcal_url)}" data-action="subscribe_click" data-calendar-type="apple" data-event-id="none" data-event-title="none">Apple Calendar</a>
        <a class="button light tracked-link requires-identity" href="{html.escape(google_url)}" target="_blank" rel="noopener" data-action="subscribe_click" data-calendar-type="google" data-event-id="none" data-event-title="none">Google Calendar</a>
      </div>
      <p class="hint">Voor Outlook gebruiken we de abonnementslink via <strong>webcal://</strong>. Als Windows vraagt welke app je wilt gebruiken, kies dan Outlook Desktop. Plak anders de webcal-link handmatig via Outlook → Agenda toevoegen → Abonneren vanaf internet.</p>
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


    function normalize(value, fallback) {{
      const v = (value || "").trim();
      return v || fallback || "unknown";
    }}
    function storageKey() {{ return (window.ALSO_TRACKING_CONFIG || {{}}).storageKey || "alsoCloudEventsUser"; }}
    function getIdentity() {{
      try {{ return JSON.parse(localStorage.getItem(storageKey()) || "{{}}"); }} catch(e) {{ return {{}}; }}
    }}
    function setIdentity(identity) {{ localStorage.setItem(storageKey(), JSON.stringify(identity)); }}
    function hasValidIdentity() {{
      const identity = getIdentity();
      return !!(identity.userName && identity.organization && identity.email && identity.userName !== "unknown" && identity.organization !== "unknown" && identity.email !== "unknown");
    }}
    function updateCalendarButtons() {{
      const enabled = hasValidIdentity();
      document.querySelectorAll(".requires-identity").forEach(btn => {{
        btn.classList.toggle("disabled", !enabled);
        btn.setAttribute("aria-disabled", enabled ? "false" : "true");
        btn.title = enabled ? "" : "Vul eerst naam, organisatie en e-mailadres in.";
      }});
    }}
    function loadIdentity() {{
      const identity = getIdentity();
      const n = document.getElementById("userName"), o = document.getElementById("organization"), e = document.getElementById("email"), s = document.getElementById("identityStatus");
      if (!n || !o || !e) return;
      n.value = identity.userName || ""; o.value = identity.organization || ""; e.value = identity.email || "";
      if (hasValidIdentity() && s) s.style.display = "block";
      updateCalendarButtons();
    }}
    function saveIdentity() {{
      const identity = {{ userName: normalize(document.getElementById("userName").value, ""), organization: normalize(document.getElementById("organization").value, ""), email: normalize(document.getElementById("email").value, "") }};
      const emailOk = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(identity.email);
      if (!identity.userName || !identity.organization || !identity.email || identity.userName === "unknown" || identity.organization === "unknown" || identity.email === "unknown" || !emailOk) {{
        alert("Vul eerst een naam, organisatie en geldig e-mailadres in voordat je de agenda toevoegt.");
        return false;
      }}
      setIdentity(identity);
      document.getElementById("identityStatus").style.display = "block";
      updateCalendarButtons();
      trackUsage({{ action: "identity_saved", calendarType: "identity", eventId: "none", eventTitle: "none" }});
      return true;
    }}
    function clearIdentity() {{
      localStorage.removeItem(storageKey());
      document.getElementById("identityStatus").style.display = "none";
      loadIdentity();
      updateCalendarButtons();
    }}
    function ensureIdentity() {{
      if (hasValidIdentity()) return true;
      alert("Vul eerst je naam, organisatie en e-mailadres in en klik op 'Gegevens opslaan'. Daarna kun je de agenda toevoegen.");
      document.getElementById("userName").focus();
      return false;
    }}

    async function trackUsage(payload) {{
      const config = window.ALSO_TRACKING_CONFIG || {{}};
      if (!config.enabled || !config.endpointUrl) return;

      const body = {{
        timestampUtc: new Date().toISOString(),
        source: config.source || "ALSO Cloud Events",
        action: normalize(payload.action, "unknown"),
        calendarType: normalize(payload.calendarType, "none"),
        eventId: normalize(payload.eventId, "none"),
        eventTitle: normalize(payload.eventTitle, "none"),
        partnerCode: normalize(getQueryParam("partner") || getQueryParam("partnerCode"), "direct"),
        campaign: normalize(getQueryParam("campaign") || getQueryParam("utm_campaign"), "direct"),
        pageUrl: window.location.href,
        referrer: normalize(document.referrer, "direct"),
        userAgent: normalize(navigator.userAgent, "unknown"),
        language: normalize(navigator.language, "unknown"),
        sessionId: getSessionId(),
        userName: normalize(getIdentity().userName, "anonymous"),
        organization: normalize(getIdentity().organization, "unknown"),
        email: normalize(getIdentity().email, "unknown")
      }};

      try {{
        const blob = new Blob([JSON.stringify(body)], {{ type: "application/json" }});
        if (navigator.sendBeacon) {{
          navigator.sendBeacon(config.endpointUrl, blob);
        }} else {{
          fetch(config.endpointUrl, {{
            method: "POST",
            headers: {{ "Content-Type": "application/json" }},
            body: JSON.stringify(body),
            keepalive: true
          }}).catch(() => {{}});
        }}
      }} catch (e) {{
        console.warn("Tracking failed", e);
      }}
    }}

    document.querySelectorAll(".tracked-link").forEach(link => {{
      link.addEventListener("click", (event) => {{
        if (link.classList.contains("requires-identity") && !ensureIdentity()) {{ event.preventDefault(); return; }}
        trackUsage({{
          action: link.dataset.action,
          calendarType: link.dataset.calendarType,
          eventId: link.dataset.eventId,
          eventTitle: link.dataset.eventTitle
        }});
      }});
    }});

    loadIdentity();
    trackUsage({{ action: "page_view", calendarType: "none", eventId: "none", eventTitle: "none" }});

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

def build_outlook_page(data: dict) -> str:
    calendar = data.get("calendar", {})
    site_url = calendar.get("site_url", "").rstrip("/") + "/"
    https_ics_url = site_url + "calendar.ics"
    outlook_add_url = "https://outlook.office.com/calendar/0/addfromweb"

    return f"""<!doctype html>
<html lang="nl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Outlook Calendar - ALSO Cloud Events</title>
  <style>
    :root {{ --bg:#f4f6fb; --card:#fff; --text:#1f2937; --muted:#6b7280; --dark:#111827; --border:#e5e7eb; --accent:#2563eb; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font-family:Arial,sans-serif; background:var(--bg); color:var(--text); line-height:1.55; }}
    header {{ background:linear-gradient(135deg,#111827,#1f2937); color:white; padding:44px 24px; }}
    main, .wrap {{ max-width:920px; margin:0 auto; }}
    main {{ padding:32px 24px 48px; }}
    .panel {{ background:white; border:1px solid var(--border); border-radius:18px; padding:24px; margin-bottom:24px; box-shadow:0 1px 3px rgba(0,0,0,.04); }}
    .button-row {{ display:flex; flex-wrap:wrap; gap:12px; margin:18px 0; }}
    .button {{ display:inline-block; background:var(--dark); color:white; padding:12px 18px; border-radius:10px; text-decoration:none; font-weight:bold; border:0; cursor:pointer; font:inherit; }}
    .button.light {{ background:#eef2ff; color:#111827; }}
    .button.disabled, .small-button.disabled {{ opacity:.45; cursor:not-allowed; pointer-events:auto; }}
    code {{ display:block; background:#f3f4f6; padding:12px; border-radius:10px; word-break:break-all; margin:12px 0; }}
    .step {{ display:grid; grid-template-columns:42px 1fr; gap:14px; padding:16px 0; border-top:1px solid var(--border); }}
    .step:first-of-type {{ border-top:0; }}
    .num {{ width:32px; height:32px; border-radius:999px; background:#111827; color:white; display:flex; align-items:center; justify-content:center; font-weight:bold; }}
    .hint {{ color:var(--muted); font-size:14px; }}
    .success {{ display:none; background:#ecfdf5; color:#065f46; border:1px solid #a7f3d0; border-radius:12px; padding:12px; margin-top:12px; }}
  </style>
</head>
<body>
  <header>
    <div class="wrap">
      <h1>Outlook Calendar toevoegen</h1>
      <p>Voeg de ALSO Cloud Agenda toe als abonnement. Zo blijven nieuwe events en wijzigingen automatisch bijgewerkt.</p>
    </div>
  </header>

  <main>
    <section class="panel">
      <h2>Snelle route</h2>
      <p>De abonnementslink wordt automatisch gekopieerd. Daarna opent Outlook Web. Plak de link daar met <strong>Ctrl+V</strong> en klik op <strong>Import</strong>.</p>

      <div class="button-row">
        <button class="button" onclick="copyAndOpenOutlook()">Kopieer link en open Outlook</button>
        <button class="button light" onclick="copyCalendarUrl()">Alleen link kopiëren</button>
        <a class="button light" href="index.html">Terug naar agenda</a>
      </div>

      <div id="copySuccess" class="success">De agenda-URL is gekopieerd. Plak deze in Outlook met Ctrl+V.</div>

      <p class="hint">Outlook ondersteunt helaas niet betrouwbaar dat websites de abonnementslink automatisch in het veld plaatsen. Deze route voorkomt dat je per ongeluk een statische .ics-import doet.</p>

      <h3>Agenda-abonnementslink</h3>
      <code id="calendarUrl">{html.escape(https_ics_url)}</code>
    </section>

    <section class="panel">
      <h2>Handmatige stappen in Outlook</h2>

      <div class="step">
        <div class="num">1</div>
        <div>
          <strong>Open Outlook Agenda</strong>
          <p>Ga naar <em>Agenda toevoegen</em> en kies <em>Abonneren vanaf internet</em>.</p>
        </div>
      </div>

      <div class="step">
        <div class="num">2</div>
        <div>
          <strong>Plak de URL</strong>
          <p>Plak de gekopieerde link met <strong>Ctrl+V</strong>.</p>
        </div>
      </div>

      <div class="step">
        <div class="num">3</div>
        <div>
          <strong>Noem de agenda: ALSO Cloud Agenda</strong>
          <p>Als Outlook om een naam vraagt, gebruik dan <strong>ALSO Cloud Agenda</strong>.</p>
        </div>
      </div>

      <div class="step">
        <div class="num">4</div>
        <div>
          <strong>Klik op Import</strong>
          <p>De agenda is daarna als abonnement toegevoegd en wordt automatisch bijgewerkt.</p>
        </div>
      </div>
    </section>
  </main>

  <script>
    const calendarUrl = {json.dumps(https_ics_url)};
    const outlookUrl = {json.dumps(outlook_add_url)};

    async function copyCalendarUrl() {{
      try {{
        await navigator.clipboard.writeText(calendarUrl);
        document.getElementById("copySuccess").style.display = "block";
      }} catch (e) {{
        const text = document.createElement("textarea");
        text.value = calendarUrl;
        document.body.appendChild(text);
        text.select();
        document.execCommand("copy");
        document.body.removeChild(text);
        document.getElementById("copySuccess").style.display = "block";
      }}
    }}

    async function copyAndOpenOutlook() {{
      await copyCalendarUrl();
      window.open(outlookUrl, "_blank", "noopener");
    }}
  </script>
</body>
</html>
"""


def build_admin(data: dict) -> str:
    categories = data.get("categories", {})
    options = "\\n".join(f'<option value="{html.escape(k)}">{html.escape(v.get("label", k))}</option>' for k, v in categories.items())
    category_json = json.dumps(categories, ensure_ascii=False)
    publish = data.get("admin_publish", {}) or {}
    publish_json = json.dumps({
        "enabled": bool(publish.get("enabled", False)),
        "endpointUrl": publish.get("endpoint_url", ""),
        "adminKey": publish.get("admin_key", ""),
        "repository": publish.get("repository", ""),
        "branch": publish.get("branch", "main"),
        "filePath": publish.get("file_path", "events.yml")
    }, ensure_ascii=False)
    return f"""<!doctype html>
<html lang="nl">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Admin - ALSO Cloud Events</title>
<style>
body{{font-family:Arial,sans-serif;margin:0;background:#f4f6fb;color:#1f2937;line-height:1.5}}header{{background:#111827;color:white;padding:32px 24px}}main,.wrap{{max-width:1100px;margin:0 auto}}main{{padding:32px 24px}}.logo{{height:50px;width:auto;margin-bottom:18px}}.grid{{display:grid;grid-template-columns:320px 1fr;gap:24px}}.panel{{background:white;border:1px solid #e5e7eb;border-radius:16px;padding:24px;margin-bottom:24px}}label{{display:block;font-weight:bold;margin-top:14px}}input,select,textarea{{width:100%;padding:10px;border:1px solid #d1d5db;border-radius:8px;margin-top:6px;font:inherit}}textarea{{min-height:120px}}button,.button{{background:#111827;color:white;padding:12px 18px;border:0;border-radius:8px;font-weight:bold;margin-top:16px;cursor:pointer;text-decoration:none;display:inline-block}}button.secondary,.button.secondary{{background:#374151}}button.light,.button.light{{background:#eef2ff;color:#111827}}button.danger{{background:#b91c1c}}pre{{white-space:pre-wrap;background:#111827;color:white;padding:18px;border-radius:12px;overflow:auto}}code{{background:#f3f4f6;padding:3px 6px;border-radius:6px}}.hint{{color:#6b7280}}.event-list{{display:flex;flex-direction:column;gap:8px}}.event-item{{border:1px solid #e5e7eb;border-radius:10px;padding:10px;background:#fafafa;cursor:pointer}}.event-item.active{{border-color:#2563eb;background:#eff6ff}}.event-item strong{{display:block}}.event-item span{{font-size:13px;color:#6b7280}}.button-row{{display:flex;flex-wrap:wrap;gap:10px}}.status{{margin-top:12px;padding:12px;border-radius:10px;display:none}}.status.ok{{display:block;background:#ecfdf5;color:#065f46;border:1px solid #a7f3d0}}.status.error{{display:block;background:#fef2f2;color:#991b1b;border:1px solid #fecaca}}@media(max-width:850px){{.grid{{grid-template-columns:1fr}}}}
</style></head>
<body>
<header><div class="wrap"><img class="logo" src="assets/also-logo.png" alt="ALSO logo"><h1>ALSO Cloud Events Admin</h1><p>Interne beheerpagina voor ALSO-medewerkers. Deel deze pagina niet met partners.</p></div></header>
<main>
<section class="panel">
  <h2>Beheer events</h2>
  <p class="hint">Laad bestaande events uit <code>events.json</code>, wijzig of verwijder ze en genereer daarna YAML voor <code>events.yml</code>.</p>
  <div class="button-row"><button onclick="loadEvents()">Events laden</button><button class="light" onclick="newEvent()">Nieuw event</button><button class="secondary" onclick="publishToGitHub()">Publiceer naar GitHub</button><a class="button light" href="index.html">Publieke pagina bekijken</a></div><div id="publishStatus" class="status"></div>
</section>
<div class="grid">
<section class="panel"><h2>Events</h2><div id="eventList" class="event-list"><p class="hint">Klik op “Events laden”.</p></div></section>
<section class="panel">
<h2 id="formTitle">Event aanmaken of wijzigen</h2>
<label>Titel</label><input id="title" placeholder="🟦 Webinar - Azure Backup">
<label>Unieke ID</label><input id="id" placeholder="webinar-azure-backup-2026-10-15">
<label>Categorie</label><select id="category">{options}</select>
<label>Featured event?</label><select id="featured"><option value="false">Nee</option><option value="true">Ja</option></select>
<label>Hele dag?</label><select id="allDay" onchange="toggleTimeFields()"><option value="false">Nee, met start- en eindtijd</option><option value="true">Ja, hele dag</option></select>
<label>Datum</label><input id="date" type="date">
<div id="timeFields"><label>Starttijd</label><input id="startTime" type="time" value="10:00"><label>Eindtijd</label><input id="endTime" type="time" value="11:00"></div>
<label>Locatie</label><input id="location" placeholder="Microsoft Teams">
<label>Registratie URL</label><input id="registration" placeholder="https://...">
<label>Tags, gescheiden met komma's</label><input id="tags" placeholder="Azure, Security, AI">
<label>Beschrijving</label><textarea id="description" placeholder="Korte beschrijving van het event."></textarea>
<div class="button-row"><button onclick="saveEvent()">Event opslaan in lijst</button><button class="secondary" onclick="generateYaml()">Genereer events YAML</button><button class="danger" onclick="deleteSelectedEvent()">Geselecteerd event verwijderen</button><button class="light" onclick="copyYaml()">Kopieer YAML</button></div>
</section>
</div>
<section class="panel"><h2>Resultaat voor events.yml</h2><p class="hint">Kopieer dit resultaat naar de <code>events:</code>-sectie in <code>events.yml</code>.</p><pre id="output">Laad events of maak een nieuw event aan.</pre></section>
</main>
<script>
const categories = {category_json};
const publishConfig = {publish_json};
let events = [];
let selectedId = null;
function slugify(text){{return text.toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-+|-+$/g,'')}}
function escapeYaml(value){{return String(value ?? '').replace(/"/g,'\\\\\\"')}}
function datePart(value){{return (value || '').split('T')[0] || ''}}
function timePart(value, fallback){{const t=(value || '').split('T')[1] || fallback; return (t || fallback).substring(0,5)}}
function getSelectedEvent(){{return events.find(e=>e.id===selectedId)}}
async function loadEvents(){{
  try {{
    const res = await fetch('events.json?ts=' + Date.now());
    events = await res.json();
    renderList();
    if(events.length) selectEvent(events[0].id);
    generateYaml();
  }} catch(e) {{
    document.getElementById('eventList').innerHTML = '<p class="hint">Kon events.json niet laden. Controleer of de GitHub Action al heeft gedraaid.</p>';
  }}
}}
function renderList(){{
  const container = document.getElementById('eventList');
  if(!events.length){{container.innerHTML='<p class="hint">Geen events gevonden.</p>';return;}}
  container.innerHTML = events.map(e => `<div class="event-item ${{e.id===selectedId?'active':''}}" onclick="selectEvent('${{e.id}}')"><strong>${{e.title || e.id}}</strong><span>${{e.date || (e.start || '').substring(0,10) || 'geen datum'}} · ${{e.category || 'geen categorie'}}</span></div>`).join('');
}}
function selectEvent(id){{
  selectedId=id; const e=getSelectedEvent(); if(!e)return;
  document.getElementById('formTitle').textContent='Event wijzigen';
  document.getElementById('title').value=e.title||''; document.getElementById('id').value=e.id||''; document.getElementById('category').value=e.category||Object.keys(categories)[0]||'';
  document.getElementById('featured').value=String(!!e.featured); document.getElementById('allDay').value=String(!!e.all_day);
  document.getElementById('date').value=e.all_day ? (e.date||'') : datePart(e.start);
  document.getElementById('startTime').value=e.all_day ? '10:00' : timePart(e.start,'10:00'); document.getElementById('endTime').value=e.all_day ? '11:00' : timePart(e.end,'11:00');
  document.getElementById('location').value=e.location||''; document.getElementById('registration').value=e.registration_url||''; document.getElementById('tags').value=(e.tags||[]).join(', '); document.getElementById('description').value=e.description||'';
  toggleTimeFields(); renderList();
}}
function newEvent(){{
  selectedId=null; document.getElementById('formTitle').textContent='Nieuw event aanmaken';
  ['title','id','date','location','registration','tags','description'].forEach(id=>document.getElementById(id).value='');
  document.getElementById('category').value=Object.keys(categories)[0]||''; document.getElementById('featured').value='false'; document.getElementById('allDay').value='false'; document.getElementById('startTime').value='10:00'; document.getElementById('endTime').value='11:00';
  toggleTimeFields(); renderList();
}}
function toggleTimeFields(){{document.getElementById('timeFields').style.display = document.getElementById('allDay').value === 'true' ? 'none' : 'block';}}
function readFormEvent(){{
  const title=document.getElementById('title').value.trim()||'Titel van het event'; const id=document.getElementById('id').value.trim()||slugify(title); const allDay=document.getElementById('allDay').value==='true'; const date=document.getElementById('date').value||'2026-01-01';
  const event={{id,title,location:document.getElementById('location').value.trim(),category:document.getElementById('category').value,featured:document.getElementById('featured').value==='true',tags:document.getElementById('tags').value.split(',').map(t=>t.trim()).filter(Boolean),registration_url:document.getElementById('registration').value.trim(),description:document.getElementById('description').value.trim()||'Meer informatie volgt binnenkort.'}};
  if(allDay){{event.date=date;event.all_day=true;}} else {{event.start=`${{date}}T${{document.getElementById('startTime').value||'10:00'}}:00`;event.end=`${{date}}T${{document.getElementById('endTime').value||'11:00'}}:00`;event.all_day=false;}}
  return event;
}}
function saveEvent(){{
  const event=readFormEvent(); const idx=events.findIndex(e=>e.id===event.id || e.id===selectedId);
  if(idx>=0) events[idx]=event; else events.push(event);
  events.sort((a,b)=>(a.date||a.start||'').localeCompare(b.date||b.start||'')); selectedId=event.id; renderList(); generateYaml(false);
}}
function deleteSelectedEvent(){{
  if(!selectedId){{alert('Selecteer eerst een event.');return;}} const e=getSelectedEvent(); if(!confirm(`Event verwijderen: ${{e?.title || selectedId}}?`))return;
  events=events.filter(e=>e.id!==selectedId); selectedId=null; renderList(); newEvent(); generateYaml(false);
}}
function yamlEvent(e){{
  let y=`  - id: "${{escapeYaml(e.id)}}"
    title: "${{escapeYaml(e.title)}}"
`;
  if(e.all_day) y+=`    date: "${{e.date}}"
    all_day: true
`; else y+=`    start: "${{e.start}}"
    end: "${{e.end}}"
    all_day: false
`;
  y+=`    location: "${{escapeYaml(e.location||'')}}"
    category: "${{escapeYaml(e.category||'')}}"
    featured: ${{!!e.featured}}
`;
  if(e.tags && e.tags.length) y+=`    tags:\\n${{e.tags.map(t=>'      - '+escapeYaml(t)).join('\\n')}}\\n`; else y+=`    tags: []\\n`;
  y+=`    registration_url: "${{escapeYaml(e.registration_url||'')}}"
    description: |
${{String(e.description||'Meer informatie volgt binnenkort.').split('\\n').map(line=>'      '+line).join('\\n')}}`;
  return y;
}}
function generateYaml(update=true){{ if(update && selectedId) saveEvent(); document.getElementById('output').textContent=`events:\\n${{events.map(yamlEvent).join('\\n')}}`; }}
function currentEventsYaml(){{return `events:\n${{events.map(yamlEvent).join('\n')}}`;}}
function setPublishStatus(message, type){{const el=document.getElementById('publishStatus'); el.textContent=message; el.className='status '+type;}}
async function publishToGitHub(){{
  if(selectedId) saveEvent();
  const yaml=currentEventsYaml();
  document.getElementById('output').textContent=yaml;
  if(!publishConfig.enabled || !publishConfig.endpointUrl){{setPublishStatus('Publicatie is nog niet ingesteld. Vul admin_publish.endpoint_url in events.yml.', 'error'); return;}}
  if(!publishConfig.adminKey){{setPublishStatus('Admin key ontbreekt. Vul admin_publish.admin_key in events.yml en controleer dezelfde key in Power Automate.', 'error'); return;}}
  if(!confirm('Weet je zeker dat je deze events naar GitHub wilt publiceren?')) return;
  setPublishStatus('Publiceren naar GitHub gestart...', 'ok');
  try {{
    const response = await fetch(publishConfig.endpointUrl, {{
      method:'POST',
      headers:{{'Content-Type':'application/json'}},
      body:JSON.stringify({{
        adminKey: publishConfig.adminKey,
        repository: publishConfig.repository,
        branch: publishConfig.branch,
        filePath: publishConfig.filePath,
        eventsYaml: yaml,
        commitMessage: 'Update events from admin portal',
        timestampUtc: new Date().toISOString()
      }})
    }});
    if(!response.ok) throw new Error('HTTP '+response.status);
    setPublishStatus('Publicatie verzonden. Controleer GitHub Actions; de agenda wordt opnieuw opgebouwd.', 'ok');
  }} catch(e) {{
    setPublishStatus('Publiceren mislukt: '+e.message, 'error');
  }}
}}
function copyYaml(){{navigator.clipboard.writeText(document.getElementById('output').textContent)}}
toggleTimeFields();
</script></body></html>"""


def main():
    DOCS.mkdir(exist_ok=True)
    data = load_data()
    validate(data)
    (DOCS / "calendar.ics").write_text(build_ics(data), encoding="utf-8")
    (DOCS / "index.html").write_text(build_index(data), encoding="utf-8")
    (DOCS / "admin.html").write_text(build_admin(data), encoding="utf-8")
    (DOCS / "outlook.html").write_text(build_outlook_page(data), encoding="utf-8")
    (DOCS / "events.json").write_text(json.dumps(data.get("events", []), ensure_ascii=False, indent=2), encoding="utf-8")
    print("Generated docs/calendar.ics")
    print("Generated docs/index.html")
    print("Generated docs/admin.html")
    print("Generated docs/events.json")

if __name__ == "__main__":
    main()
