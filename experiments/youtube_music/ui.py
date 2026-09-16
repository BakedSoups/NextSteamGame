from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

OUTPUT_DIR = Path(__file__).resolve().parent / "output"


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def dashboard_data() -> dict:
    benchmark = load_json(OUTPUT_DIR / "benchmark-25.json")
    classifications: dict[str, dict] = {}
    discoveries: dict[str, dict] = {}
    for path in OUTPUT_DIR.glob("*.classification.json"):
        classifications[path.name.removesuffix(".classification.json")] = load_json(path)
    for path in OUTPUT_DIR.glob("*.discovery.json"):
        discoveries[path.name.removesuffix(".discovery.json")] = load_json(path)
    games = []
    for item in benchmark.get("games", []):
        appid = str(item.get("appid", ""))
        games.append({**item, "classification": classifications.get(appid), "discovery": discoveries.get(appid)})
    extras = [
        {"appid": key, "game": "Classifier smoke test", "classification": value, "selected": []}
        for key, value in classifications.items()
        if key not in {str(item.get("appid", "")) for item in games}
    ]
    return {"summary": benchmark, "games": games + extras}


HTML = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Music Tag Lab</title>
<style>
:root{--bg:#07121d;--panel:#0e1d2a;--panel2:#142635;--line:#294052;--text:#e7f0f7;--muted:#8fa6b7;--cyan:#66c9ef;--green:#62d7a7;--amber:#f5c451;--pink:#ec7fa6}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 70% -20%,#16344b 0,transparent 35%),var(--bg);color:var(--text);font:14px Inter,ui-sans-serif,system-ui,sans-serif}
header{height:62px;border-bottom:1px solid var(--line);display:flex;align-items:center;padding:0 24px;gap:13px;background:#091622dd;position:sticky;top:0;z-index:3;backdrop-filter:blur(14px)}
.logo{width:34px;height:34px;border:1px solid #345267;border-radius:50%;display:grid;place-items:center;color:var(--cyan);font-size:18px}.title{font-weight:750;font-size:16px}.subtitle{color:var(--muted);font-size:11px;letter-spacing:.14em;text-transform:uppercase}
.layout{display:grid;grid-template-columns:300px minmax(0,1fr);min-height:calc(100vh - 62px)}aside{border-right:1px solid var(--line);padding:16px;background:#09162280;position:sticky;top:62px;height:calc(100vh - 62px);overflow:auto}
.summary{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin-bottom:14px}.stat{background:var(--panel);border:1px solid var(--line);border-radius:9px;padding:9px}.stat b{display:block;font-size:17px;color:var(--cyan)}.stat span{font-size:9px;color:var(--muted);text-transform:uppercase;letter-spacing:.1em}
input{width:100%;background:#0b1a27;border:1px solid var(--line);color:var(--text);padding:10px 11px;border-radius:8px;outline:none;margin-bottom:10px}input:focus{border-color:var(--cyan)}
.game{padding:10px;border-radius:8px;border:1px solid transparent;cursor:pointer;margin:3px 0}.game:hover{background:#102332}.game.active{background:#142a3a;border-color:#3c6177}.game-name{font-weight:650}.game-meta{color:var(--muted);font-size:11px;margin-top:3px}.dot{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:6px;background:var(--amber)}.dot.done{background:var(--green)}
main{padding:24px 28px;max-width:1200px}.hero{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:18px}.hero h1{margin:0 0 5px;font-size:26px}.hero p{margin:0;color:var(--muted)}.badge{border:1px solid #346078;background:#102c3d;color:var(--cyan);padding:6px 9px;border-radius:99px;font-size:11px}
.grid{display:grid;grid-template-columns:1.2fr .8fr;gap:14px}.card{background:linear-gradient(145deg,var(--panel),#0c1a26);border:1px solid var(--line);border-radius:12px;padding:16px;margin-bottom:14px}.card h2{font-size:12px;letter-spacing:.13em;text-transform:uppercase;color:#a9becd;margin:0 0 13px}.wide{grid-column:1/-1}
.track{display:grid;grid-template-columns:34px minmax(0,1fr) auto;gap:10px;align-items:center;padding:10px 0;border-top:1px solid #223747}.track:first-of-type{border-top:0}.rank{width:28px;height:28px;border-radius:7px;background:#183044;color:var(--cyan);display:grid;place-items:center;font-weight:800}.track-title{font-weight:650}.track-channel{color:var(--muted);font-size:11px;margin-top:3px}.score{font-variant-numeric:tabular-nums;color:var(--green)}
.tags{display:flex;gap:7px;flex-wrap:wrap}.tag{border:1px solid #3a586c;background:#172a38;border-radius:99px;padding:6px 9px}.tag strong{color:var(--cyan);margin-left:6px}.tag.primary{border-color:#4a9379;background:#13352e}.tag.warn{border-color:#79566a;background:#30212c;color:#efa7bf}
.bars{display:grid;gap:10px}.bar-row{display:grid;grid-template-columns:145px 1fr 45px;gap:9px;align-items:center}.bar-label{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.bar-track{height:7px;background:#233644;border-radius:9px;overflow:hidden}.bar-fill{height:100%;background:linear-gradient(90deg,var(--cyan),var(--green));border-radius:9px}.bar-value{text-align:right;color:var(--muted);font-size:11px}.empty{padding:26px;border:1px dashed #395164;border-radius:9px;text-align:center;color:var(--muted)}
.note{font-size:12px;color:var(--muted);line-height:1.55}.expected{color:var(--amber)}@media(max-width:800px){.layout{grid-template-columns:1fr}aside{position:static;height:auto;border-right:0}.grid{grid-template-columns:1fr}.wide{grid-column:auto}}
</style></head>
<body><header><div class="logo">♫</div><div><div class="title">Music Tag Lab</div><div class="subtitle">NextSteamGame experiment</div></div></header>
<div class="layout"><aside><div class="summary" id="summary"></div><input id="search" placeholder="Filter 25 games"><div id="games"></div></aside><main id="detail"></main></div>
<script>
let data,selected=0;
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pct=n=>Math.round(Number(n||0)*100)+'%';
function tags(items=[],cls=''){return `<div class="tags">${items.map(x=>`<span class="tag ${cls}">${esc(x.tag??x)}${x.confidence!=null?`<strong>${pct(x.confidence)}</strong>`:''}</span>`).join('')}</div>`}
function bars(items=[]){return `<div class="bars">${items.map(x=>`<div class="bar-row"><div class="bar-label" title="${esc(x.label)}">${esc(x.label)}</div><div class="bar-track"><div class="bar-fill" style="width:${Math.min(100,Number(x.score)*100)}%"></div></div><div class="bar-value">${pct(x.score)}</div></div>`).join('')}</div>`}
function renderList(filter=''){const q=filter.toLowerCase();document.querySelector('#games').innerHTML=data.games.map((g,i)=>({g,i})).filter(x=>x.g.game.toLowerCase().includes(q)).map(({g,i})=>`<div class="game ${i===selected?'active':''}" onclick="selectGame(${i})"><div class="game-name"><span class="dot ${g.classification?'done':''}"></span>${esc(g.game)}</div><div class="game-meta">${g.selected?.length||0} sources · ${g.classification?'classified':'awaiting audio'}</div></div>`).join('')}
function selectGame(i){selected=i;renderList(document.querySelector('#search').value);renderDetail()}
function renderDetail(){const g=data.games[selected],c=g.classification,p=c?.music_profile,a=c?.aggregate||{};const tracks=g.selected||[];document.querySelector('#detail').innerHTML=`
<div class="hero"><div><h1>${esc(g.game)}</h1><p>Steam app ${esc(g.appid)} · ${g.candidate_count??0} search candidates</p></div><span class="badge">${c?'CNN CLASSIFIED':'DISCOVERY ONLY'}</span></div>
<div class="grid"><section class="card"><h2>Selected soundtrack evidence</h2>${tracks.length?tracks.map((t,i)=>`<div class="track"><div class="rank">${i+1}</div><div><div class="track-title">${esc(t.title)}</div><div class="track-channel">${esc(t.channel)}</div></div><div class="score">${pct(t.ranking_score)}</div></div>`).join(''):'<div class="empty">No trustworthy individual soundtrack track was selected.</div>'}</section>
<section class="card"><h2>Benchmark expectation</h2>${tags(g.expected_genres||[],'')}<p class="note">These are human reference labels for checking the model, not inputs to classification.</p></section>
${c?`<section class="card wide"><h2>Game-focused music profile</h2><div class="tags"><span class="tag primary">Primary: ${esc(p?.music_primary||'none')}</span><span class="tag">Secondary: ${esc(p?.music_secondary||'none')}</span><span class="tag">Evidence tracks: ${p?.track_count||0}</span></div><br>${tags(p?.subgenres||[])}<br>${tags(p?.musical_traits||[])}</section>
<section class="card"><h2>Raw genre predictions</h2>${bars(a.genres||[])}</section><section class="card"><h2>Instrument predictions</h2>${bars(a.instruments||[])}</section>
<section class="card wide"><h2>Suppressed vague labels</h2>${p?.suppressed_vague_labels?.length?tags(p.suppressed_vague_labels,'warn'):'<div class="empty">No vague labels suppressed.</div>'}</section>`:`<section class="card wide"><h2>Classification status</h2><div class="empty">Soundtrack sources were discovered, but no authorized WAV analysis exists for this game yet. This view intentionally does not invent genre results from video titles.</div></section>`}</div>`}
fetch('/api/data').then(r=>r.json()).then(d=>{data=d;const s=d.summary;document.querySelector('#summary').innerHTML=`<div class="stat"><b>${s.sample_size||0}</b><span>games</span></div><div class="stat"><b>${s.games_with_selection||0}</b><span>found</span></div><div class="stat"><b>${s.total_selected_tracks||0}</b><span>tracks</span></div>`;renderList();renderDetail()});
document.querySelector('#search').addEventListener('input',e=>renderList(e.target.value));
</script></body></html>'''


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/data":
            payload = json.dumps(dashboard_data(), ensure_ascii=False).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json; charset=utf-8")
        elif path in {"/", "/index.html"}:
            payload = HTML.encode()
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8")
        else:
            payload = b"Not found"; self.send_response(404); self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(payload))); self.end_headers(); self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:
        print(f"music-ui: {format % args}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Temporary music experiment dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9999)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Music Tag Lab: http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
