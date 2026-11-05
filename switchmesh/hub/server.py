"""SwitchMesh webhook and command hub."""

from __future__ import annotations

from html import escape
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from .dedup import IncidentCorrelator
from .guardrails import sanitize_payload


class WebhookPayload(BaseModel):
    text: str = ""
    title: str = ""
    summary: str = ""
    description: str = ""
    body: str = ""
    message: str = ""
    source: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CommandPayload(BaseModel):
    command: str


app = FastAPI(title="SwitchMesh Command Hub")
correlator = IncidentCorrelator()
war_rooms: set[str] = set()
approvals: set[str] = set()
incident_sources: dict[str, set[str]] = {}
incident_redactions: dict[str, int] = {}


def _redaction_count(text: str) -> int:
    return sum(text.count(marker) for marker in ("[REDACTED_SECRET]", "[REDACTED_EMAIL]", "[REDACTED_CARD]", "[REDACTED_PHONE]"))


def _report(payload: WebhookPayload, source: str) -> dict[str, Any]:
    raw_text = " ".join(
        value for value in (payload.title, payload.summary, payload.description, payload.body, payload.message, payload.text) if value
    )
    safe_text = sanitize_payload(raw_text)
    incident_id = correlator.correlate({**payload.metadata, "source": source, "text": safe_text})
    incident_sources.setdefault(incident_id, set()).add(source)
    incident_redactions[incident_id] = incident_redactions.get(incident_id, 0) + _redaction_count(safe_text)
    return {"incident_id": incident_id, "source": source, "payload": safe_text}


@app.post("/webhooks/{source}")
def webhook(source: str, payload: WebhookPayload):
    if source not in {"telegram", "discord", "sentry", "github"}:
        raise HTTPException(status_code=404, detail="Unknown webhook source")
    return _report(payload, source)


@app.post("/webhooks/telegram")
def telegram(payload: WebhookPayload):
    return _report(payload, "telegram")


@app.post("/webhooks/discord")
def discord(payload: WebhookPayload):
    return _report(payload, "discord")


@app.post("/webhooks/sentry")
def sentry(payload: WebhookPayload):
    return _report(payload, "sentry")


@app.post("/webhooks/github")
def github(payload: WebhookPayload):
    return _report(payload, "github")


def _incident_cards() -> list[dict[str, Any]]:
    return [
        {
            "incident_id": incident_id,
            "platforms": sorted(incident_sources.get(incident_id, set())),
            "redactions": incident_redactions.get(incident_id, 0),
            "war_room": incident_id in war_rooms,
            "approved": incident_id in approvals,
        }
        for incident_id in correlator.incidents
    ]


@app.get("/api/incidents")
def incidents():
    return {"incidents": _incident_cards()}


def _dashboard_html() -> str:
    cards = _incident_cards()
    total_redactions = sum(card["redactions"] for card in cards)
    if not cards:
        cards_markup = '<div class="empty">No incidents yet. Simulate a signal to begin correlation.</div>'
    else:
        cards_markup = "".join(
            f'''<article class="card" data-incident="{escape(card["incident_id"])}">
              <div class="card-head"><span class="incident">{escape(card["incident_id"])}</span><span class="status">{"APPROVED" if card["approved"] else "OPEN"}</span></div>
              <div class="platforms">{" ".join(f'<span class="badge">{escape(platform.title())}</span>' for platform in card["platforms"])}</div>
              <p class="meta">{card["redactions"]} PII/secrets redacted · {"War room linked" if card["war_room"] else "No war room yet"}</p>
              <div class="actions"><button onclick="simulate('telegram')">Telegram</button><button onclick="simulate('discord')">Discord</button><button onclick="simulate('sentry')">Sentry</button><button onclick="simulate('github')">GitHub</button></div>
              <div class="actions"><button class="accent" onclick="command('war-room','{escape(card['incident_id'])}')">Spawn war room</button><button class="good" onclick="command('approve','{escape(card['incident_id'])}')">Approve resolution</button></div>
            </article>'''
            for card in cards
        )
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SwitchMesh Command Hub</title>
<style>
:root {{ color-scheme: dark; --bg:#090d18; --panel:#11182a; --line:#24304a; --muted:#8d9ab5; --text:#edf3ff; --cyan:#57d5ff; --green:#59e6a7; --purple:#9c8cff; }}
* {{ box-sizing:border-box; }} body {{ margin:0; min-height:100vh; font-family:Inter,ui-sans-serif,system-ui,sans-serif; color:var(--text); background:radial-gradient(circle at 10% 0%,#152442 0%,var(--bg) 42%); }}
.shell {{ max-width:1120px; margin:auto; padding:48px 24px 72px; }} .eyebrow {{ color:var(--cyan); font-size:12px; letter-spacing:.16em; text-transform:uppercase; font-weight:700; }}
h1 {{ margin:10px 0 8px; font-size:clamp(32px,5vw,58px); letter-spacing:-.04em; }} .lead {{ color:var(--muted); max-width:680px; line-height:1.6; }}
.toolbar {{ display:flex; gap:10px; align-items:stretch; flex-wrap:wrap; margin:28px 0; }} .stat {{ display:flex; min-width:150px; flex-direction:column; justify-content:center; padding:9px 14px; border:1px solid var(--line); border-radius:9px; background:#101a2d; }} .stat strong {{ font-size:20px; color:var(--cyan); }} .stat span {{ color:var(--muted); font-size:11px; }} button {{ border:1px solid var(--line); background:#18233b; color:var(--text); border-radius:9px; padding:10px 13px; cursor:pointer; font-weight:650; }} button:hover {{ border-color:var(--cyan); transform:translateY(-1px); }} button.accent {{ background:#282153; border-color:#6557c9; }} button.good {{ background:#123a35; border-color:#2a9f76; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(300px,1fr)); gap:18px; }} .card {{ background:linear-gradient(145deg,rgba(22,32,55,.96),rgba(13,19,34,.96)); border:1px solid var(--line); border-radius:16px; padding:20px; box-shadow:0 18px 45px rgba(0,0,0,.22); }}
.card-head {{ display:flex; justify-content:space-between; align-items:center; }} .incident {{ font-size:20px; font-weight:800; }} .status {{ color:var(--green); font-size:11px; letter-spacing:.12em; font-weight:800; }} .platforms {{ display:flex; gap:7px; flex-wrap:wrap; margin:18px 0; }} .badge {{ border:1px solid #314667; color:#b8d9ff; background:#14233d; border-radius:999px; padding:5px 9px; font-size:12px; }} .meta {{ color:var(--muted); font-size:13px; }} .actions {{ display:flex; gap:8px; flex-wrap:wrap; margin-top:14px; }} .actions button {{ font-size:12px; padding:8px 10px; }} .empty {{ border:1px dashed var(--line); padding:28px; border-radius:14px; color:var(--muted); }} #toast {{ position:fixed; right:20px; bottom:20px; background:#18233b; border:1px solid var(--cyan); padding:12px 15px; border-radius:10px; display:none; }}
</style></head><body><main class="shell"><div class="eyebrow">SwitchMesh · Live operations</div><h1>Command Hub</h1><p class="lead">Correlate cross-platform signals, open a linked war room, and record human-approved resolutions from one focused workspace.</p>
<div class="toolbar"><div class="stat"><strong>{len(cards)}</strong><span>correlated incidents</span></div><div class="stat"><strong>{total_redactions}</strong><span>PII values redacted</span></div><button onclick="simulateAll()">Simulate all webhooks</button><button onclick="refresh()">Refresh incidents</button></div><section id="cards" class="grid">{cards_markup}</section></main><div id="toast"></div>
<script>
const toast=(message)=>{{const el=document.getElementById('toast');el.textContent=message;el.style.display='block';setTimeout(()=>el.style.display='none',2600)}};
async function simulate(source){{const response=await fetch('/webhooks/'+source,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{text:'checkout FREESHIP TypeError from '+source}})}});if(!response.ok) return toast('Webhook failed');toast(source+' signal correlated');await refresh();}}
async function simulateAll(){{for(const source of ['telegram','discord','sentry','github']) await simulate(source);}}
async function command(action,id){{const response=await fetch('/api/command',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{command:action+' '+id}})}});toast(response.ok?action+' '+id:'Command failed');await refresh();}}
async function refresh(){{const response=await fetch('/api/incidents');const data=await response.json();if(data.incidents.length) location.reload();}}
</script></body></html>'''


@app.get("/", response_class=HTMLResponse)
def dashboard():
    return _dashboard_html()


@app.post("/api/command")
def command(payload: CommandPayload):
    parts = payload.command.strip().split()
    if len(parts) != 2 or parts[1].upper().startswith("INC-") is False:
        raise HTTPException(status_code=400, detail="Use 'war-room INC-101' or 'approve INC-101'")
    action, incident_id = parts[0].lower(), parts[1].upper()
    if action == "war-room":
        war_rooms.add(incident_id)
        return {"action": action, "incident_id": incident_id, "status": "opened"}
    if action == "approve":
        approvals.add(incident_id)
        return {"action": action, "incident_id": incident_id, "status": "approved"}
    raise HTTPException(status_code=400, detail="Unsupported command")
