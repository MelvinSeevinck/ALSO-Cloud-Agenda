
from pathlib import Path
from datetime import datetime, timedelta, timezone
import html
import json
import urllib.parse
import sys

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
DOCS = ROOT / "docs"

def load_json(path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def fail(message):
    print("ERROR:", message, file=sys.stderr)
    sys.exit(1)

def parse_event_date(event):
    if event.get("allDay"):
        return datetime.strptime(event["date"], "%Y-%m-%d")
    return datetime.fromisoformat(event["start"])

def validate_events(events):
    ids = set()
    for event in events:
        event_id = event.get("id")
        if not event_id:
            fail("Een event mist een id.")
        if event_id in ids:
            fail(f"Dubbele event-id gevonden: {event_id}")
        ids.add(event_id)
        if not event.get("title"):
            fail(f"Event {event_id} mist een title.")
        if event.get("allDay"):
            if not event.get("date"):
                fail(f"Event {event_id} heeft allDay=true maar mist date.")
            datetime.strptime(event["date"], "%Y-%m-%d")
        else:
            if not event.get("start") or not event.get("end"):
                fail(f"Event {event_id} mist start of end.")
            if datetime.fromisoformat(event["end"]) <= datetime.fromisoformat(event["start"]):
                fail(f"Event {event_id} heeft een eindtijd vóór starttijd.")

def esc_ics(value):
    value = str(value or "")
    return value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\r\n", "\\n").replace("\n", "\\n")

def fold_line(line):
    result, current = [], ""
    for ch in line:
        test = current + ch
        if len(test.encode("utf-8")) > 72:
            result.append(current)
            current = " " + ch
        else:
            current = test
    result.append(current)
    return "\r\n".join(result)

def build_description(event):
    desc = event.get("description", "")
    if event.get("registrationUrl"):
        desc = f"{desc}\n\nAanmelden / meer informatie: {event['registrationUrl']}".strip()
    return desc

def category_label(config, key):
    return config.get("categories", {}).get(key, {}).get("label", key or "ALSO Cloud")

def build_ics(config, events):
    cal = config["calendar"]
    tz = cal.get("timezone", "Europe/Amsterdam")
    agenda_name = cal.get("agendaName", cal.get("name", "ALSO Cloud Agenda"))
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//ALSO Nederland B.V.//ALSO Cloud Agenda//NL",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{esc_ics(agenda_name)}",
        f"NAME:{esc_ics(agenda_name)}",
        f"X-WR-CALDESC:{esc_ics(cal.get('description', ''))}",
        f"X-WR-TIMEZONE:{esc_ics(tz)}",
        "REFRESH-INTERVAL;VALUE=DURATION:PT12H",
        "X-PUBLISHED-TTL:PT12H",
    ]
    for event in sorted(events, key=parse_event_date):
        lines += [
            "BEGIN:VEVENT",
            f"UID:{esc_ics(event['id'])}@also-cloud-agenda",
            f"DTSTAMP:{now}",
            f"SUMMARY:{esc_ics(event.get('title'))}",
            f"LOCATION:{esc_ics(event.get('location'))}",
            f"DESCRIPTION:{esc_ics(build_description(event))}",
            f"CATEGORIES:{esc_ics(category_label(config, event.get('category')))}",
        ]
        if event.get("registrationUrl"):
            lines.append(f"URL:{esc_ics(event['registrationUrl'])}")
        if event.get("allDay"):
            start = datetime.strptime(event["date"], "%Y-%m-%d")
            end = start + timedelta(days=1)
            lines.append(f"DTSTART;VALUE=DATE:{start.strftime('%Y%m%d')}")
            lines.append(f"DTEND;VALUE=DATE:{end.strftime('%Y%m%d')}")
        else:
            start = datetime.fromisoformat(event["start"])
            end = datetime.fromisoformat(event["end"])
            lines.append(f"DTSTART;TZID={tz}:{start.strftime('%Y%m%dT%H%M%S')}")
            lines.append(f"DTEND;TZID={tz}:{end.strftime('%Y%m%dT%H%M%S')}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(fold_line(l) for l in lines) + "\r\n"

def display_date(event):
    if event.get("allDay"):
        return datetime.strptime(event["date"], "%Y-%m-%d").strftime("%d-%m-%Y")
    start = datetime.fromisoformat(event["start"])
    end = datetime.fromisoformat(event["end"])
    return f"{start.strftime('%d-%m-%Y %H:%M')} - {end.strftime('%H:%M')}"

def event_google_link(event):
    if event.get("allDay"):
        start = datetime.strptime(event["date"], "%Y-%m-%d")
        end = start + timedelta(days=1)
        start_s, end_s = start.strftime("%Y%m%d"), end.strftime("%Y%m%d")
    else:
        start = datetime.fromisoformat(event["start"])
        end = datetime.fromisoformat(event["end"])
        start_s, end_s = start.strftime("%Y%m%dT%H%M%S"), end.strftime("%Y%m%dT%H%M%S")
    params = {
        "action": "TEMPLATE",
        "text": event.get("title", ""),
        "dates": f"{start_s}/{end_s}",
        "details": build_description(event),
        "location": event.get("location", "")
    }
    return "https://calendar.google.com/calendar/render?" + urllib.parse.urlencode(params)

def tag_html(event):
    return "".join(f"<span>{html.escape(str(t))}</span>" for t in event.get("tags", []))

def event_card(config, event):
    site_url = config["calendar"].get("siteUrl", "").rstrip("/") + "/"
    ics_url = site_url + "calendar.ics"
    webcal_url = ics_url.replace("https://", "webcal://").replace("http://", "webcal://")
    event_id = html.escape(event.get("id", ""))
    title = html.escape(event.get("title", ""))
    registration = ""
    if event.get("registrationUrl"):
        registration = f'<a class="small-button tracked-link requires-identity" href="{html.escape(event["registrationUrl"])}" data-action="registration_click" data-calendar-type="registration" data-event-id="{event_id}" data-event-title="{title}">Aanmelden</a>'
    featured = " featured" if event.get("featured") else ""
    search = html.escape((event.get("title","") + " " + event.get("description","") + " " + " ".join(event.get("tags", []))).lower())
    return f"""
    <article class="event-card{featured}" data-category="{html.escape(event.get('category',''))}" data-search="{search}">
      <div class="event-date">{html.escape(display_date(event))}</div>
      <div class="event-content">
        <div class="event-category">{html.escape(category_label(config, event.get("category")))}</div>
        <h3>{title}</h3>
        <p class="location">{html.escape(event.get("location", ""))}</p>
        <div class="tags">{tag_html(event)}</div>
        <p>{html.escape(event.get("description", "")).replace(chr(10), "<br>")}</p>
        <div class="event-actions">
          <a class="small-button tracked-link requires-identity" href="{html.escape(webcal_url)}" data-action="event_calendar_click" data-calendar-type="outlook" data-event-id="{event_id}" data-event-title="{title}">Outlook</a>
          <a class="small-button secondary tracked-link requires-identity" href="{html.escape(webcal_url)}" data-action="event_calendar_click" data-calendar-type="apple" data-event-id="{event_id}" data-event-title="{title}">Apple</a>
          <a class="small-button light tracked-link requires-identity" href="{html.escape(event_google_link(event))}" target="_blank" rel="noopener" data-action="event_calendar_click" data-calendar-type="google" data-event-id="{event_id}" data-event-title="{title}">Google</a>
          {registration}
        </div>
      </div>
    </article>
    """

def build_public(config, events):
    cal = config["calendar"]
    site_url = cal.get("siteUrl", "").rstrip("/") + "/"
    ics_url = site_url + "calendar.ics"
    webcal_url = ics_url.replace("https://", "webcal://").replace("http://", "webcal://")
    google_url = "https://calendar.google.com/calendar/render?cid=" + urllib.parse.quote(webcal_url, safe="")
    today = datetime.now().date()
    if not config.get("settings", {}).get("showPastEvents", False):
        events = [e for e in events if parse_event_date(e).date() >= today]
    events = sorted(events, key=parse_event_date)
    featured = [e for e in events if e.get("featured")]
    normal = [e for e in events if not e.get("featured")]
    if not featured and events:
        featured, normal = [events[0]], events[1:]
    featured_cards = "".join(event_card(config, e) for e in featured) or "<p>Er staat momenteel geen featured event gepland.</p>"
    event_cards = "".join(event_card(config, e) for e in normal) or "<p>Er staan momenteel geen overige events gepland.</p>"
    filters = ['<button class="filter active" data-filter="all">Alle events</button>'] + [
        f'<button class="filter" data-filter="{html.escape(k)}">{html.escape(v.get("label", k))}</button>'
        for k, v in config.get("categories", {}).items()
    ]
    tracking_json = json.dumps(config.get("tracking", {}), ensure_ascii=False)
    return f"""<!doctype html>
<html lang="nl">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{html.escape(cal.get("name"))}</title>
<style>
:root{{--bg:#f4f6fb;--card:#fff;--text:#1f2937;--muted:#6b7280;--dark:#111827;--border:#e5e7eb;--accent:#2563eb}}*{{box-sizing:border-box}}body{{margin:0;font-family:Arial,sans-serif;background:var(--bg);color:var(--text);line-height:1.55}}header{{background:linear-gradient(135deg,#111827,#1f2937);color:white;padding:42px 24px}}.wrap,main{{max-width:1120px;margin:0 auto}}main{{padding:32px 24px 48px}}.logo{{height:56px;width:auto;display:block;margin-bottom:28px}}h1{{font-size:42px;margin:8px 0 12px}}.eyebrow{{color:#bfdbfe;font-weight:bold;letter-spacing:.04em;text-transform:uppercase;font-size:13px}}header p{{max-width:850px;font-size:18px}}.panel{{background:white;border:1px solid var(--border);border-radius:18px;padding:24px;margin-bottom:24px;box-shadow:0 1px 3px rgba(0,0,0,.04)}}.button-row{{display:flex;flex-wrap:wrap;gap:12px;margin:18px 0}}.button,.small-button{{display:inline-block;background:#111827;color:white;padding:12px 18px;border-radius:10px;text-decoration:none;font-weight:bold;border:0;cursor:pointer;font:inherit}}.small-button{{padding:9px 13px;margin:4px 6px 4px 0}}.secondary{{background:#374151!important}}.light{{background:#eef2ff!important;color:#111827!important}}.disabled{{opacity:.45;cursor:not-allowed}}code{{background:#f3f4f6;padding:3px 6px;border-radius:6px;word-break:break-all}}.hint{{color:var(--muted);font-size:14px}}.identity-box{{background:#f8fbff;border:1px solid #dbeafe;border-radius:14px;padding:16px;margin-top:16px}}.identity-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}}.identity-grid label{{font-weight:bold;font-size:13px}}.identity-grid input{{width:100%;padding:10px;border:1px solid var(--border);border-radius:8px;margin-top:6px;font:inherit}}#identityStatus{{display:none;color:#065f46;font-weight:bold}}.toolbar input{{width:100%;padding:12px;border:1px solid var(--border);border-radius:10px;font:inherit}}.filter{{border:1px solid var(--border);background:white;padding:10px 12px;border-radius:999px;cursor:pointer}}.filter.active{{background:#111827;color:white;border-color:#111827}}.event-card{{display:grid;grid-template-columns:170px 1fr;gap:24px;border-top:1px solid var(--border);padding:24px 0}}.event-card:first-child{{border-top:none;padding-top:0}}.event-card.featured{{border:1px solid #dbeafe;background:#f8fbff;border-radius:16px;padding:22px}}.event-date{{font-weight:bold}}.event-category{{color:var(--accent);font-size:14px;font-weight:bold}}.location{{color:var(--muted);margin-top:0}}.tags{{display:flex;flex-wrap:wrap;gap:6px;margin:10px 0}}.tags span{{background:#eef2ff;border-radius:999px;padding:4px 8px;font-size:12px}}footer{{color:var(--muted);font-size:14px}}@media(max-width:720px){{h1{{font-size:32px}}.event-card{{grid-template-columns:1fr}}.identity-grid{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<header><div class="wrap"><img class="logo" src="assets/also-logo.png" alt="ALSO logo"><div class="eyebrow">ALSO Nederland B.V.</div><h1>{html.escape(cal.get("name"))}</h1><p>{html.escape(cal.get("description"))}</p></div></header>
<main>
<section class="panel">
<h2>Abonneer op de agenda</h2><p>Vul je gegevens in en voeg de agenda daarna toe aan Outlook, Apple Calendar of Google Calendar.</p>
<div class="identity-box"><h3>Gegevens voor gebruiksregistratie</h3><p class="hint">Deze gegevens zijn verplicht zodat we kunnen zien welke partners de agenda gebruiken.</p><div class="identity-grid"><label>Naam<input id="userName" required placeholder="Voor- en achternaam"></label><label>Organisatie<input id="organization" required placeholder="Partnerorganisatie"></label><label>E-mailadres<input id="email" required type="email" placeholder="naam@organisatie.nl"></label></div><div class="button-row"><button class="button" onclick="saveIdentity()">Gegevens opslaan</button><button class="button light" onclick="clearIdentity()">Gegevens wissen</button></div><div id="identityStatus">Gegevens opgeslagen. Je kunt de agenda nu toevoegen.</div></div>
<div class="button-row"><a class="button tracked-link requires-identity" href="{html.escape(webcal_url)}" data-action="subscribe_click" data-calendar-type="outlook" data-event-id="none" data-event-title="none">Outlook Calendar</a><a class="button secondary tracked-link requires-identity" href="{html.escape(webcal_url)}" data-action="subscribe_click" data-calendar-type="apple" data-event-id="none" data-event-title="none">Apple Calendar</a><a class="button light tracked-link requires-identity" href="{html.escape(google_url)}" target="_blank" rel="noopener" data-action="subscribe_click" data-calendar-type="google" data-event-id="none" data-event-title="none">Google Calendar</a></div>
<p class="hint">Voor Outlook gebruiken we <strong>webcal://</strong>. Als Windows vraagt welke app je wilt gebruiken, kies Outlook Desktop.</p><p class="hint">{html.escape(config.get("tracking", {}).get("privacyNotice", ""))}</p><p>Webcal-link:</p><p><code>{html.escape(webcal_url)}</code></p>
</section>
<section class="panel"><h2>Featured event</h2>{featured_cards}</section>
<section class="panel"><h2>Alle geplande events</h2><div class="toolbar"><input id="search" type="search" placeholder="Zoek op titel, onderwerp of tag..."></div><div class="button-row">{''.join(filters)}</div><div id="events">{event_cards}</div></section>
<footer>Deze kalender wordt automatisch gepubliceerd vanuit GitHub Pages.</footer>
</main>
<script>
window.ALSO_TRACKING_CONFIG={tracking_json};
function cfg(){{return window.ALSO_TRACKING_CONFIG||{{}}}}function storageKey(){{return"alsoCloudEventsUser"}}function norm(v,f){{v=(v||"").trim();return v||f||"unknown"}}function getParam(n){{return new URLSearchParams(location.search).get(n)||""}}function getIdentity(){{try{{return JSON.parse(localStorage.getItem(storageKey())||"{{}}")}}catch(e){{return {{}}}}}}function setIdentity(i){{localStorage.setItem(storageKey(),JSON.stringify(i))}}function hasValidIdentity(){{const i=getIdentity();return !!(i.userName&&i.organization&&i.email)}}function updateButtons(){{const ok=hasValidIdentity();document.querySelectorAll(".requires-identity").forEach(b=>{{b.classList.toggle("disabled",!ok);b.setAttribute("aria-disabled",ok?"false":"true");b.title=ok?"":"Vul eerst je gegevens in."}})}}function loadIdentity(){{const i=getIdentity();userName.value=i.userName||"";organization.value=i.organization||"";email.value=i.email||"";if(hasValidIdentity())identityStatus.style.display="block";updateButtons()}}function saveIdentity(){{const i={{userName:norm(userName.value,""),organization:norm(organization.value,""),email:norm(email.value,"")}};const ok=/^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/.test(i.email);if(!i.userName||!i.organization||!i.email||!ok){{alert("Vul naam, organisatie en een geldig e-mailadres in.");return false}}setIdentity(i);identityStatus.style.display="block";updateButtons();track({{action:"identity_saved",calendarType:"identity",eventId:"none",eventTitle:"none"}});return true}}function clearIdentity(){{localStorage.removeItem(storageKey());identityStatus.style.display="none";loadIdentity()}}function ensureIdentity(){{if(hasValidIdentity())return true;alert("Vul eerst je naam, organisatie en e-mailadres in en klik op Gegevens opslaan.");userName.focus();return false}}function sessionId(){{let k="alsoCloudEventsSessionId",v=sessionStorage.getItem(k);if(!v){{v=(crypto.randomUUID?crypto.randomUUID():String(Date.now())+Math.random());sessionStorage.setItem(k,v)}}return v}}function track(p){{const c=cfg();if(!c.enabled||!c.endpointUrl)return;const i=getIdentity();const body={{timestampUtc:new Date().toISOString(),source:c.source||"ALSO Cloud Events",action:norm(p.action,"unknown"),calendarType:norm(p.calendarType,"none"),eventId:norm(p.eventId,"none"),eventTitle:norm(p.eventTitle,"none"),partnerCode:norm(getParam("partner")||getParam("partnerCode"),"direct"),campaign:norm(getParam("campaign")||getParam("utm_campaign"),"direct"),pageUrl:location.href,referrer:norm(document.referrer,"direct"),userAgent:norm(navigator.userAgent,"unknown"),language:norm(navigator.language,"unknown"),sessionId:sessionId(),userName:norm(i.userName,"anonymous"),organization:norm(i.organization,"unknown"),email:norm(i.email,"unknown")}};try{{const blob=new Blob([JSON.stringify(body)],{{type:"application/json"}});if(navigator.sendBeacon)navigator.sendBeacon(c.endpointUrl,blob);else fetch(c.endpointUrl,{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify(body),keepalive:true}}).catch(()=>{{}})}}catch(e){{}}}}
document.querySelectorAll(".tracked-link").forEach(l=>l.addEventListener("click",e=>{{if(l.classList.contains("requires-identity")&&!ensureIdentity()){{e.preventDefault();return}}track({{action:l.dataset.action,calendarType:l.dataset.calendarType,eventId:l.dataset.eventId,eventTitle:l.dataset.eventTitle}})}}));const filters=document.querySelectorAll(".filter"),cards=document.querySelectorAll(".event-card"),search=document.getElementById("search");let active="all";function applyFilters(){{const q=(search.value||"").toLowerCase();cards.forEach(card=>{{const ok=(active==="all"||card.dataset.category===active)&&(!q||card.dataset.search.includes(q));card.style.display=ok?"":"none"}})}}filters.forEach(btn=>btn.addEventListener("click",()=>{{filters.forEach(b=>b.classList.remove("active"));btn.classList.add("active");active=btn.dataset.filter;applyFilters();track({{action:"filter_click",calendarType:active,eventId:"none",eventTitle:"none"}})}}));search.addEventListener("input",applyFilters);["userName","organization","email"].forEach(id=>document.getElementById(id).addEventListener("input",updateButtons));loadIdentity();track({{action:"page_view",calendarType:"none",eventId:"none",eventTitle:"none"}});
</script>
</body></html>"""

def build_admin(config, events):
    cats = config.get("categories", {})
    options = "".join(f'<option value="{html.escape(k)}">{html.escape(v.get("label", k))}</option>' for k,v in cats.items())
    admin_json = json.dumps(config.get("adminPublish", {}), ensure_ascii=False)
    cats_json = json.dumps(cats, ensure_ascii=False)
    return f"""<!doctype html><html lang="nl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Admin - ALSO Cloud Events</title><style>
body{{font-family:Arial,sans-serif;margin:0;background:#f4f6fb;color:#1f2937;line-height:1.5}}header{{background:#111827;color:white;padding:32px 24px}}main,.wrap{{max-width:1100px;margin:0 auto}}main{{padding:32px 24px}}.logo{{height:50px;margin-bottom:18px}}.grid{{display:grid;grid-template-columns:320px 1fr;gap:24px}}.panel{{background:white;border:1px solid #e5e7eb;border-radius:16px;padding:24px;margin-bottom:24px}}label{{display:block;font-weight:bold;margin-top:14px}}input,select,textarea{{width:100%;padding:10px;border:1px solid #d1d5db;border-radius:8px;margin-top:6px;font:inherit}}textarea{{min-height:120px}}button,.button{{background:#111827;color:white;padding:12px 18px;border:0;border-radius:8px;font-weight:bold;margin-top:16px;cursor:pointer;text-decoration:none;display:inline-block}}.secondary{{background:#374151!important}}.light{{background:#eef2ff!important;color:#111827!important}}.danger{{background:#b91c1c!important}}pre{{white-space:pre-wrap;background:#111827;color:white;padding:18px;border-radius:12px;overflow:auto}}.hint{{color:#6b7280}}.event-list{{display:flex;flex-direction:column;gap:8px}}.event-item{{border:1px solid #e5e7eb;border-radius:10px;padding:10px;background:#fafafa;cursor:pointer}}.event-item.active{{border-color:#2563eb;background:#eff6ff}}.event-item strong{{display:block}}.event-item span{{font-size:13px;color:#6b7280}}.status{{margin-top:12px;padding:12px;border-radius:10px;display:none}}.status.ok{{display:block;background:#ecfdf5;color:#065f46;border:1px solid #a7f3d0}}.status.error{{display:block;background:#fef2f2;color:#991b1b;border:1px solid #fecaca}}.button-row{{display:flex;flex-wrap:wrap;gap:10px}}@media(max-width:850px){{.grid{{grid-template-columns:1fr}}}}
</style></head><body><header><div class="wrap"><img class="logo" src="assets/also-logo.png" alt="ALSO logo"><h1>ALSO Cloud Events Admin</h1><p>Interne beheerpagina voor ALSO-medewerkers.</p></div></header><main>
<section class="panel"><h2>Beheer events</h2><p class="hint">Wijzig events en publiceer direct naar GitHub. GitHub Actions bouwt daarna automatisch de publieke agenda opnieuw.</p><div class="button-row"><button onclick="loadEvents()">Events laden</button><button class="light" onclick="newEvent()">Nieuw event</button><button class="secondary" onclick="publishToGitHub()">Publiceer naar GitHub</button><a class="button light" href="index.html">Publieke pagina bekijken</a></div><div id="publishStatus" class="status"></div></section>
<div class="grid"><section class="panel"><h2>Events</h2><div id="eventList" class="event-list"><p class="hint">Klik op “Events laden”.</p></div></section><section class="panel"><h2 id="formTitle">Event aanmaken of wijzigen</h2>
<label>Titel</label><input id="title"><label>Unieke ID</label><input id="id"><label>Categorie</label><select id="category">{options}</select><label>Featured?</label><select id="featured"><option value="false">Nee</option><option value="true">Ja</option></select><label>Hele dag?</label><select id="allDay" onchange="toggleTime()"><option value="false">Nee</option><option value="true">Ja</option></select><label>Datum</label><input id="date" type="date"><div id="timeFields"><label>Starttijd</label><input id="startTime" type="time" value="10:00"><label>Eindtijd</label><input id="endTime" type="time" value="11:00"></div><label>Locatie</label><input id="location"><label>Registratie URL</label><input id="registration"><label>Tags, gescheiden met komma's</label><input id="tags"><label>Beschrijving</label><textarea id="description"></textarea><div class="button-row"><button onclick="saveEvent()">Event opslaan</button><button class="danger" onclick="deleteEvent()">Event verwijderen</button><button class="light" onclick="copyJson()">Kopieer JSON</button></div></section></div><section class="panel"><h2>JSON preview</h2><pre id="output"></pre></section></main>
<script>
const categories={cats_json};const publishConfig={admin_json};let events=[];let selectedId=null;
function slugify(t){{return t.toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-+|-+$/g,'')}}function datePart(v){{return(v||'').split('T')[0]||''}}function timePart(v,f){{let t=(v||'').split('T')[1]||f;return(t||f).substring(0,5)}}function selected(){{return events.find(e=>e.id===selectedId)}}async function loadEvents(){{const r=await fetch('events.json?ts='+Date.now());events=await r.json();render();if(events.length)selectEvent(events[0].id);preview()}}function render(){{eventList.innerHTML=events.length?events.map(e=>`<div class="event-item ${{e.id===selectedId?'active':''}}" onclick="selectEvent('${{e.id}}')"><strong>${{e.title||e.id}}</strong><span>${{e.date||(e.start||'').substring(0,10)||'geen datum'}} · ${{e.category||''}}</span></div>`).join(''):'<p class="hint">Geen events.</p>'}}function selectEvent(id){{selectedId=id;const e=selected();if(!e)return;formTitle.textContent='Event wijzigen';title.value=e.title||'';window.id.value=e.id||'';category.value=e.category||Object.keys(categories)[0]||'';featured.value=String(!!e.featured);allDay.value=String(!!e.allDay);date.value=e.allDay?(e.date||''):datePart(e.start);startTime.value=e.allDay?'10:00':timePart(e.start,'10:00');endTime.value=e.allDay?'11:00':timePart(e.end,'11:00');location.value=e.location||'';registration.value=e.registrationUrl||'';tags.value=(e.tags||[]).join(', ');description.value=e.description||'';toggleTime();render()}}function newEvent(){{selectedId=null;formTitle.textContent='Nieuw event';['title','id','date','location','registration','tags','description'].forEach(x=>document.getElementById(x).value='');category.value=Object.keys(categories)[0]||'';featured.value='false';allDay.value='false';startTime.value='10:00';endTime.value='11:00';toggleTime();render()}}function toggleTime(){{timeFields.style.display=allDay.value==='true'?'none':'block'}}function readForm(){{const titleValue=title.value.trim()||'Titel van het event';const event={{id:window.id.value.trim()||slugify(titleValue),title:titleValue,location:location.value.trim(),category:category.value,featured:featured.value==='true',tags:tags.value.split(',').map(t=>t.trim()).filter(Boolean),registrationUrl:registration.value.trim(),description:description.value.trim()||'Meer informatie volgt binnenkort.'}};if(allDay.value==='true'){{event.date=date.value||'2026-01-01';event.allDay=true}}else{{event.start=`${{date.value||'2026-01-01'}}T${{startTime.value||'10:00'}}:00`;event.end=`${{date.value||'2026-01-01'}}T${{endTime.value||'11:00'}}:00`;event.allDay=false}}return event}}function saveEvent(){{const e=readForm();const idx=events.findIndex(x=>x.id===selectedId||x.id===e.id);if(idx>=0)events[idx]=e;else events.push(e);events.sort((a,b)=>(a.date||a.start||'').localeCompare(b.date||b.start||''));selectedId=e.id;render();preview()}}function deleteEvent(){{if(!selectedId)return alert('Selecteer eerst een event.');if(!confirm('Event verwijderen?'))return;events=events.filter(e=>e.id!==selectedId);selectedId=null;newEvent();render();preview()}}function preview(){{output.textContent=JSON.stringify(events,null,2)}}function status(m,t){{publishStatus.textContent=m;publishStatus.className='status '+t}}async function publishToGitHub(){{if(selectedId)saveEvent();if(!publishConfig.enabled||!publishConfig.endpointUrl)return status('Publicatie-flow is nog niet ingesteld in data/config.json.','error');if(!publishConfig.adminKey)return status('Admin key ontbreekt in data/config.json.','error');if(!confirm('Publiceren naar GitHub?'))return;status('Publiceren gestart...','ok');try{{const r=await fetch(publishConfig.endpointUrl,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{adminKey:publishConfig.adminKey,repository:publishConfig.repository,branch:publishConfig.branch,filePath:publishConfig.filePath,events:events,commitMessage:'Update events from admin portal',timestampUtc:new Date().toISOString()}})}});if(!r.ok)throw new Error('HTTP '+r.status);status('Publicatie verzonden. Controleer GitHub Actions.','ok')}}catch(e){{status('Publiceren mislukt: '+e.message,'error')}}}}function copyJson(){{navigator.clipboard.writeText(JSON.stringify(events,null,2))}}toggleTime();
</script></body></html>"""

def main():
    DOCS.mkdir(exist_ok=True)
    config = load_json(DATA / "config.json")
    events = load_json(DATA / "events-source.json")
    validate_events(events)
    (DOCS / "calendar.ics").write_text(build_ics(config, events), encoding="utf-8")
    (DOCS / "events.json").write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")
    (DOCS / "index.html").write_text(build_public(config, events), encoding="utf-8")
    (DOCS / "admin.html").write_text(build_admin(config, events), encoding="utf-8")
    print("Generated docs/index.html")
    print("Generated docs/admin.html")
    print("Generated docs/calendar.ics")
    print("Generated docs/events.json")

if __name__ == "__main__":
    main()
