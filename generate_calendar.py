from pathlib import Path
from datetime import datetime, timedelta, timezone
import json, html, urllib.parse

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'
DOCS = ROOT / 'docs'

def load(p):
    return json.loads(p.read_text(encoding='utf-8'))

def parse_dt(e):
    return datetime.strptime(e['date'], '%Y-%m-%d') if e.get('allDay') else datetime.fromisoformat(e['start'])

def day(e):
    return e.get('date') if e.get('allDay') else str(e.get('start',''))[:10]

def validate(events):
    ids = set()
    for e in events:
        for f in ['id','title','status','location','category','registrationUrl','description']:
            if not str(e.get(f,'')).strip():
                raise SystemExit(f'Missing {f} in {e.get("id", "unknown")}')
        if e['id'] in ids:
            raise SystemExit('Duplicate id: ' + e['id'])
        ids.add(e['id'])
        if e['status'] not in ['published','draft','archived']:
            raise SystemExit('Invalid status: ' + e['id'])
        if not isinstance(e.get('tags'), list) or not e['tags']:
            raise SystemExit('Tags required: ' + e['id'])
        if e.get('allDay'):
            datetime.strptime(e['date'], '%Y-%m-%d')
        else:
            s = datetime.fromisoformat(e['start']); t = datetime.fromisoformat(e['end'])
            if t <= s:
                raise SystemExit('Invalid start/end: ' + e['id'])

def esc(v):
    return str(v or '').replace('\\','\\\\').replace(';','\\;').replace(',','\\,').replace('\n','\\n')

def fold(line):
    out=[]; cur=''
    for ch in line:
        if len((cur+ch).encode('utf-8')) > 72:
            out.append(cur); cur=' '+ch
        else:
            cur += ch
    out.append(cur)
    return '\r\n'.join(out)

def cat(config,k):
    return config.get('categories',{}).get(k,{}).get('label', k or '')

def desc(e):
    d = e.get('description','').strip()
    if e.get('registrationUrl'):
        d += '\n\nAanmelden / meer informatie: ' + e['registrationUrl']
    return d.strip()

def build_ics(config, events):
    tz = config['calendar'].get('timezone','Europe/Amsterdam')
    now = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    lines = ['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//ALSO Nederland B.V.//ALSO Cloud Agenda//NL','CALSCALE:GREGORIAN','METHOD:PUBLISH',f"X-WR-CALNAME:{esc(config['calendar'].get('agendaName'))}",f"NAME:{esc(config['calendar'].get('agendaName'))}",f"X-WR-TIMEZONE:{esc(tz)}",'REFRESH-INTERVAL;VALUE=DURATION:PT12H','X-PUBLISHED-TTL:PT12H']
    for e in sorted(events, key=parse_dt):
        lines += ['BEGIN:VEVENT', f"UID:{esc(e['id'])}@also-cloud-agenda", f'DTSTAMP:{now}', f"SUMMARY:{esc(e['title'])}", f"LOCATION:{esc(e['location'])}", f"DESCRIPTION:{esc(desc(e))}", f"CATEGORIES:{esc(cat(config,e.get('category')))}"]
        if e.get('registrationUrl'):
            lines.append(f"URL:{esc(e['registrationUrl'])}")
        if e.get('allDay'):
            s = datetime.strptime(e['date'], '%Y-%m-%d'); t = s + timedelta(days=1)
            lines += [f"DTSTART;VALUE=DATE:{s:%Y%m%d}", f"DTEND;VALUE=DATE:{t:%Y%m%d}"]
        else:
            s = datetime.fromisoformat(e['start']); t = datetime.fromisoformat(e['end'])
            lines += [f"DTSTART;TZID={tz}:{s:%Y%m%dT%H%M%S}", f"DTEND;TZID={tz}:{t:%Y%m%dT%H%M%S}"]
        lines.append('END:VEVENT')
    lines.append('END:VCALENDAR')
    return '\r\n'.join(fold(x) for x in lines) + '\r\n'

def display(e):
    if e.get('allDay'):
        return datetime.strptime(e['date'], '%Y-%m-%d').strftime('%d-%m-%Y')
    s = datetime.fromisoformat(e['start']); t = datetime.fromisoformat(e['end'])
    return f'{s:%d-%m-%Y %H:%M} - {t:%H:%M}'

def google(e):
    if e.get('allDay'):
        s = datetime.strptime(e['date'], '%Y-%m-%d'); t = s + timedelta(days=1)
        dates = f'{s:%Y%m%d}/{t:%Y%m%d}'
    else:
        s = datetime.fromisoformat(e['start']); t = datetime.fromisoformat(e['end'])
        dates = f'{s:%Y%m%dT%H%M%S}/{t:%Y%m%dT%H%M%S}'
    return 'https://calendar.google.com/calendar/render?' + urllib.parse.urlencode({'action':'TEMPLATE','text':e['title'],'dates':dates,'details':desc(e),'location':e['location']})

CSS = """body{font-family:Arial,sans-serif;margin:0;background:#f4f6fb;color:#111827}header{background:#111827;color:white;padding:40px 24px}.wrap,main{max-width:1120px;margin:0 auto}.logo{height:52px}.panel{background:white;border:1px solid #e5e7eb;border-radius:16px;padding:24px;margin:24px}.button,.small-button{display:inline-block;background:#111827;color:white;padding:10px 14px;border-radius:9px;text-decoration:none;font-weight:bold;border:0;cursor:pointer}.secondary{background:#374151}.light{background:#eef2ff;color:#111827}.event-card{display:grid;grid-template-columns:170px 1fr;gap:20px;border-top:1px solid #e5e7eb;padding:22px 0}.featured{border:1px solid #dbeafe;background:#f8fbff;border-radius:16px;padding:22px}.tags span{background:#eef2ff;border-radius:999px;padding:4px 8px;margin:3px;display:inline-block}code{background:#f3f4f6;padding:4px;border-radius:6px;word-break:break-all}input,select,textarea{width:100%;padding:10px;border:1px solid #d1d5db;border-radius:8px}.grid{display:grid;grid-template-columns:340px 1fr;gap:18px}.event-item{border:1px solid #e5e7eb;border-radius:12px;padding:10px;margin:8px 0;cursor:pointer}.active{border-color:#2563eb;background:#eff6ff}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.stats div{background:#f8fbff;border:1px solid #dbeafe;border-radius:12px;padding:14px}.invalid{border-color:#b91c1c!important;background:#fef2f2}.status{padding:12px;border-radius:10px;margin-top:10px}.okmsg{background:#ecfdf5}.errmsg{background:#fef2f2;color:#991b1b}pre{background:#111827;color:white;padding:14px;border-radius:12px;white-space:pre-wrap;max-height:360px;overflow:auto}@media(max-width:800px){.event-card,.grid,.stats{grid-template-columns:1fr}}"""

def card(config,e):
    site=config['calendar']['siteUrl'].rstrip('/')+'/'
    webcal=(site+'calendar.ics').replace('https://','webcal://').replace('http://','webcal://')
    tags=''.join(f"<span>{html.escape(t)}</span>" for t in e['tags'])
    reg=f"<a class='small-button' href='{html.escape(e['registrationUrl'])}'>Aanmelden</a>" if e.get('registrationUrl') else ''
    klass = 'featured' if e.get('featured') else ''
    return f"<article class='event-card {klass}'><div><b>{display(e)}</b></div><div><div>{html.escape(cat(config,e['category']))}</div><h3>{html.escape(e['title'])}</h3><p>{html.escape(e['location'])}</p><div class='tags'>{tags}</div><p>{html.escape(e['description']).replace(chr(10),'<br>')}</p><a class='small-button' href='{html.escape(webcal)}'>Outlook abonnement</a> <a class='small-button secondary' href='{html.escape(webcal)}'>Apple</a> <a class='small-button light' target='_blank' href='{html.escape(google(e))}'>Google</a> {reg}</div></article>"

def public(config, events):
    site=config['calendar']['siteUrl'].rstrip('/')+'/'
    webcal=(site+'calendar.ics').replace('https://','webcal://').replace('http://','webcal://')
    featured=[e for e in events if e.get('featured')]; normal=[e for e in events if not e.get('featured')]
    if not featured and events: featured, normal = [events[0]], events[1:]
    return f"<!doctype html><html lang='nl'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{html.escape(config['calendar']['name'])}</title><style>{CSS}</style></head><body><header><div class='wrap'><img src='assets/also-logo.svg' class='logo'><h1>{html.escape(config['calendar']['name'])}</h1><p>{html.escape(config['calendar']['description'])}</p></div></header><main><section class='panel'><h2>Abonneer op de agenda</h2><p>Webcal-abonnementslink:</p><p><code>{html.escape(webcal)}</code></p></section><section class='panel'><h2>Featured event</h2>{''.join(card(config,e) for e in featured)}</section><section class='panel'><h2>Alle geplande events</h2>{''.join(card(config,e) for e in normal) or '<p>Geen overige events.</p>'}</section></main></body></html>"

def admin(config, events):
    cats=json.dumps(config.get('categories',{}),ensure_ascii=False); pub=json.dumps(config.get('adminPublish',{}),ensure_ascii=False)
    opts=''.join(f"<option value='{html.escape(k)}'>{html.escape(v['label'])}</option>" for k,v in config['categories'].items())
    return f"""<!doctype html><html lang='nl'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Admin</title><style>{CSS}</style></head><body><header><div class='wrap'><img src='assets/also-logo.svg' class='logo'><h1>ALSO Cloud Events Admin</h1><p>V15 Clean Full Replace</p></div></header><main><section class='panel'><h2>Systeemstatus</h2><div id='systemStatus' class='status'>Laden...</div></section><section class='panel'><h2>Publiceren</h2><label>Admin key<input id='adminKeyInput' type='password'></label><p><button onclick='saveAdminKey()'>Key opslaan</button> <button onclick='loadEvents()'>Events laden</button> <button onclick='newEvent()'>Nieuw event</button> <button onclick='publishToGitHub()'>Publiceer naar GitHub</button> <a class='button light' href='index.html'>Publieke pagina</a></p><div id='publishStatus'></div></section><section class='panel'><div class='stats'><div><b id='statTotal'>0</b><br>Totaal</div><div><b id='statPublished'>0</b><br>Published</div><div><b id='statDraft'>0</b><br>Draft</div><div><b id='statArchived'>0</b><br>Archived</div></div></section><div class='grid'><section class='panel'><h2>Events</h2><input id='listSearch' placeholder='Zoeken'><select id='statusFilter'><option value='all'>Alle</option><option value='published'>Published</option><option value='draft'>Draft</option><option value='archived'>Archived</option></select><div id='eventList'></div></section><section class='panel'><h2>Event</h2><label>Titel<input id='title'></label><label>Unieke ID<input id='eventId'></label><label>Status<select id='statusField'><option value='published'>Published</option><option value='draft'>Draft</option><option value='archived'>Archived</option></select></label><label>Categorie<select id='category'>{opts}</select></label><label>Featured<select id='featured'><option value='false'>Nee</option><option value='true'>Ja</option></select></label><label>Hele dag<select id='allDay'><option value='false'>Nee</option><option value='true'>Ja</option></select></label><label>Datum<input id='date' type='date'></label><div id='timeFields'><label>Start<input id='startTime' type='time' value='10:00'></label><label>Eind<input id='endTime' type='time' value='11:00'></label></div><label>Locatie<input id='location'></label><label>Registratie URL<input id='registration'></label><label>Banner URL<input id='bannerUrl'></label><label>Tags<input id='tags'></label><label>Beschrijving<textarea id='description'></textarea></label><p><button onclick='saveEvent()'>Opslaan</button> <button onclick='duplicateEvent()'>Dupliceren</button> <button onclick='archiveEvent()'>Archiveren</button> <button onclick='deleteEvent()'>Verwijderen</button> <button onclick='copyJson()'>Kopieer JSON</button></p></section></div><div class='grid'><section class='panel'><h2>Preview</h2><div id='preview'></div></section><section class='panel'><h2>JSON</h2><pre id='output'></pre></section></div></main><script>const categories={cats};const publishConfig={pub};{ADMINJS}</script></body></html>"""

ADMINJS = r'''
let events=[];let selectedId=null;const $=id=>document.getElementById(id);function slug(v){return(v||"").toLowerCase().replace(/[^a-z0-9]+/g,"-").replace(/^-+|-+$/g,"")}function day(e){return e.allDay?e.date:String(e.start||"").slice(0,10)}function msg(m,t){publishStatus.textContent=m;publishStatus.className="status "+t}function saveAdminKey(){sessionStorage.setItem("alsoAdminPublishKey",adminKeyInput.value.trim());msg("Key opgeslagen","okmsg")}function key(){return sessionStorage.getItem("alsoAdminPublishKey")||adminKeyInput.value.trim()}async function loadEvents(){try{const r=await fetch("events-admin.json?ts="+Date.now());if(!r.ok)throw new Error("HTTP "+r.status);events=await r.json();systemStatus.textContent="events-admin.json geladen: "+events.length+" event(s)";systemStatus.className="status okmsg";render();if(events.length)selectEvent(events[0].id)}catch(e){systemStatus.textContent="Laden mislukt: "+e.message;systemStatus.className="status errmsg"}}function render(){statTotal.textContent=events.length;statPublished.textContent=events.filter(e=>e.status==="published").length;statDraft.textContent=events.filter(e=>e.status==="draft").length;statArchived.textContent=events.filter(e=>e.status==="archived").length;renderList();output.textContent=JSON.stringify(events,null,2)}function renderList(){const q=(listSearch.value||"").toLowerCase(),s=statusFilter.value;eventList.innerHTML=events.filter(e=>(s==="all"||e.status===s)&&(!q||JSON.stringify(e).toLowerCase().includes(q))).map(e=>`<div class="event-item ${e.id===selectedId?"active":""}" onclick="selectEvent('${e.id}')"><b>${e.title}</b><br>${e.status} - ${day(e)}</div>`).join("")||"<p>Geen events</p>"}function selectEvent(id){selectedId=id;const e=events.find(x=>x.id===id);if(!e)return;title.value=e.title||"";eventId.value=e.id||"";statusField.value=e.status||"draft";category.value=e.category||"webinar";featured.value=String(!!e.featured);allDay.value=String(!!e.allDay);date.value=e.allDay?e.date:String(e.start||"").slice(0,10);startTime.value=e.allDay?"10:00":String((e.start||"T10:00").split("T")[1]).slice(0,5);endTime.value=e.allDay?"11:00":String((e.end||"T11:00").split("T")[1]).slice(0,5);location.value=e.location||"";registration.value=e.registrationUrl||"";bannerUrl.value=e.bannerUrl||"";tags.value=(e.tags||[]).join(", ");description.value=e.description||"";toggleTime();preview();renderList()}function newEvent(){selectedId=null;["title","eventId","date","location","registration","bannerUrl","tags","description"].forEach(i=>$(i).value="");statusField.value="draft";featured.value="false";allDay.value="false";startTime.value="10:00";endTime.value="11:00";preview()}function toggleTime(){timeFields.style.display=allDay.value==="true"?"none":"block"}function validate(){for(const el of [title,eventId,statusField,category,featured,allDay,date,location,registration,tags,description]){if(!(el.value||"").trim()){el.classList.add("invalid");msg("Vul alle verplichte velden in","errmsg");return false}else el.classList.remove("invalid")}if(registration.value&&!/^https?:\/\//i.test(registration.value)){msg("Registratie URL moet starten met https:// of http://","errmsg");return false}if(events.some(e=>e.id===eventId.value.trim()&&e.id!==selectedId)){msg("Dubbele ID","errmsg");return false}return true}function read(){const e={id:eventId.value.trim(),title:title.value.trim(),status:statusField.value,location:location.value.trim(),category:category.value,featured:featured.value==="true",tags:tags.value.split(",").map(x=>x.trim()).filter(Boolean),registrationUrl:registration.value.trim(),bannerUrl:bannerUrl.value.trim(),description:description.value.trim()};if(allDay.value==="true"){e.date=date.value;e.allDay=true}else{e.start=`${date.value}T${startTime.value||"10:00"}:00`;e.end=`${date.value}T${endTime.value||"11:00"}:00`;e.allDay=false}return e}function saveEvent(){if(!validate())return false;const e=read();const i=events.findIndex(x=>x.id===selectedId||x.id===e.id);if(i>=0)events[i]=e;else events.push(e);selectedId=e.id;events.sort((a,b)=>(day(a)||"").localeCompare(day(b)||""));render();selectEvent(e.id);msg("Lokaal opgeslagen","okmsg");return true}function duplicateEvent(){if(!selectedId)return;const b=events.find(e=>e.id===selectedId),c={...b,id:b.id+"-copy",title:b.title+" kopie",status:"draft"};events.push(c);render();selectEvent(c.id)}function archiveEvent(){if(!selectedId)return;events.find(e=>e.id===selectedId).status="archived";render();selectEvent(selectedId)}function deleteEvent(){if(!selectedId||!confirm("Verwijderen?"))return;events=events.filter(e=>e.id!==selectedId);selectedId=null;newEvent();render()}function preview(){preview.innerHTML=`<h3>${title.value||"Nieuw event"}</h3><p>${date.value||"Geen datum"} - ${location.value||"Geen locatie"} - ${statusField.value}</p><p>${(description.value||"").replace(/\n/g,"<br>")}</p>`}async function publishToGitHub(){if(!saveEvent())return;if(!key())return msg("Vul admin key in","errmsg");try{msg("Publiceren gestart...","okmsg");const r=await fetch(publishConfig.endpointUrl,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({adminKey:key(),events,commitMessage:"Update events from V15 admin",timestampUtc:new Date().toISOString()})});if(!r.ok)throw new Error("HTTP "+r.status);msg("Publicatie verzonden. Controleer GitHub Actions.","okmsg")}catch(e){msg("Publiceren mislukt: "+e.message,"errmsg")}}function copyJson(){navigator.clipboard.writeText(JSON.stringify(events,null,2))}title.addEventListener("input",()=>{if(!selectedId&&!eventId.value)eventId.value=slug(title.value);preview()});["description","date","location","statusField","allDay"].forEach(i=>$(i).addEventListener("input",()=>{toggleTime();preview()}));listSearch.addEventListener("input",renderList);statusFilter.addEventListener("change",renderList);adminKeyInput.value=sessionStorage.getItem("alsoAdminPublishKey")||"";loadEvents();
'''

def main():
    config=load(DATA/'config.json'); events=load(DATA/'events-source.json'); validate(events)
    public_events=[e for e in events if e['status']=='published']
    DOCS.mkdir(exist_ok=True)
    (DOCS/'calendar.ics').write_text(build_ics(config,public_events),encoding='utf-8')
    (DOCS/'events.json').write_text(json.dumps(public_events,ensure_ascii=False,indent=2),encoding='utf-8')
    (DOCS/'events-admin.json').write_text(json.dumps(events,ensure_ascii=False,indent=2),encoding='utf-8')
    (DOCS/'index.html').write_text(public(config,public_events),encoding='utf-8')
    (DOCS/'admin.html').write_text(admin(config,events),encoding='utf-8')
    print('Generated V15')
if __name__=='__main__': main()
