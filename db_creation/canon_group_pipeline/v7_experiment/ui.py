from __future__ import annotations

import argparse
import json
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from db_creation.canon_pipeline.layer_1_normalization import format_display
from db_creation.paths import analysis_dir


REPORT_PATH = analysis_dir() / "canon_v7_game_sample.json"


def dashboard_data() -> dict:
    try:
        report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        report = {"results": []}
    grouped: dict[str, list[dict]] = defaultdict(list)
    for result in report.get("results", []):
        accepted = bool(result.get("v6_merge_safe_under_v7"))
        surviving_tag = result.get("v6_tag") if accepted else result.get("raw_tag")
        enriched = {**result, "v7_canonical_outcome": format_display(str(surviving_tag or ""))}
        grouped[result.get("game", "Unknown game")].append(enriched)
    games = []
    for name, results in grouped.items():
        games.append({
            "name": name,
            "appid": results[0].get("appid"),
            "accepted": sum(bool(row.get("v6_merge_safe_under_v7")) for row in results),
            "rejected": sum(not bool(row.get("v6_merge_safe_under_v7")) for row in results),
            "results": results,
        })
    games.sort(key=lambda game: (-game["rejected"], game["name"].lower()))
    return {"summary": {key: value for key, value in report.items() if key != "results"}, "games": games}


HTML = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Canon Tag Lab</title><style>
:root{--bg:#07111b;--nav:#091722;--panel:#0d1d29;--panel2:#122634;--line:#263d4d;--text:#e7f1f7;--muted:#8ca3b3;--cyan:#66c9ef;--green:#5ed39e;--red:#ef7e87;--amber:#edc45d;--violet:#ae98ed}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 76% -15%,#16374c 0,transparent 34%),var(--bg);color:var(--text);font:14px Inter,ui-sans-serif,system-ui,sans-serif}
header{height:64px;display:flex;align-items:center;padding:0 25px;border-bottom:1px solid var(--line);background:#081520e8;backdrop-filter:blur(15px);position:sticky;top:0;z-index:5}.brand{display:flex;align-items:center;gap:12px}.mark{width:36px;height:36px;border:1px solid #37566a;border-radius:50%;display:grid;place-items:center;color:var(--cyan);font-weight:900}.title{font-size:16px;font-weight:760}.eyebrow{font-size:10px;letter-spacing:.15em;text-transform:uppercase;color:var(--muted);margin-top:2px}.branch{margin-left:auto;color:var(--muted);border:1px solid var(--line);border-radius:99px;padding:7px 11px;font:11px ui-monospace,monospace}
main{max-width:1360px;margin:auto;padding:24px}.hero{display:grid;grid-template-columns:1fr auto;gap:20px;align-items:end;margin-bottom:18px}.hero h1{font-size:28px;margin:0 0 6px}.hero p{color:var(--muted);margin:0;line-height:1.5}.stats{display:flex;gap:8px}.stat{min-width:98px;background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:10px 12px}.stat b{display:block;font-size:21px}.stat span{font-size:9px;color:var(--muted);letter-spacing:.12em;text-transform:uppercase}.stat.good b{color:var(--green)}.stat.bad b{color:var(--red)}
.toolbar{display:flex;gap:9px;margin:15px 0}.search{flex:1;background:var(--panel);color:var(--text);border:1px solid var(--line);border-radius:9px;padding:11px 13px;outline:none}.search:focus{border-color:var(--cyan)}button{background:var(--panel);border:1px solid var(--line);color:var(--muted);border-radius:9px;padding:0 13px;cursor:pointer}button.active{color:var(--cyan);border-color:#397895;background:#102a3b}
.game{background:linear-gradient(145deg,var(--panel),#0b1924);border:1px solid var(--line);border-radius:13px;margin:12px 0;overflow:hidden}.game-head{display:flex;align-items:center;gap:12px;padding:14px 16px;border-bottom:1px solid var(--line)}.game-icon{width:34px;height:34px;border-radius:8px;background:#173044;display:grid;place-items:center;color:var(--cyan);font-weight:800}.game-name{font-weight:730;font-size:16px}.game-id{font-size:11px;color:var(--muted);margin-top:3px}.counts{margin-left:auto;display:flex;gap:6px}.pill{font-size:10px;border:1px solid var(--line);border-radius:99px;padding:5px 8px}.pill.accept{color:var(--green);border-color:#2b765b}.pill.reject{color:var(--red);border-color:#79434a}
.mapping{display:grid;grid-template-columns:minmax(170px,1fr) 45px minmax(170px,1fr) 150px 150px;gap:12px;align-items:center;padding:14px 16px;border-top:1px solid #1e3443}.mapping:first-child{border-top:0}.tag-label{font-size:9px;letter-spacing:.13em;text-transform:uppercase;color:var(--muted);margin-bottom:5px}.tag{font-weight:670}.arrow{text-align:center;color:#567184;font-size:20px}.context{display:inline-block;margin-top:6px;color:#9eb3c1;font-size:10px;background:#172a38;border:1px solid #2b4353;border-radius:99px;padding:3px 7px}.relation{font-weight:680}.relation small{display:block;color:var(--muted);font-weight:450;margin-top:5px}.meter{height:5px;background:#253743;border-radius:9px;overflow:hidden;margin-top:6px}.fill{height:100%;background:var(--violet)}.decision{text-align:center;font-size:10px;font-weight:800;letter-spacing:.06em;border-radius:7px;padding:8px 7px}.decision.accept{color:var(--green);background:#102e25;border:1px solid #286d52}.decision.reject{color:var(--amber);background:#302a19;border:1px solid #77632b}.reason{grid-column:1/-1;color:var(--muted);font-size:12px;line-height:1.45;background:#0a1721;border-radius:7px;padding:8px 10px}.outcome{grid-column:1/-1;display:flex;gap:7px;align-items:center;color:#c6d6df;font-size:12px}.outcome b{color:var(--cyan)}.empty{text-align:center;border:1px dashed var(--line);border-radius:12px;padding:40px;color:var(--muted)}
@media(max-width:850px){.hero{grid-template-columns:1fr}.stats{flex-wrap:wrap}.mapping{grid-template-columns:1fr 30px 1fr}.relation,.decision{grid-column:auto}.relation{grid-column:1/3}.decision{grid-column:3}.branch{display:none}} </style></head>
<body><header><div class="brand"><div class="mark">CT</div><div><div class="title">Canon Tag Lab</div><div class="eyebrow">Ontology-first mapping audit</div></div></div><div class="branch">experiment/ontology-canon-v7</div></header>
<main><section class="hero"><div><h1>Real-game canonical tag audit</h1><p>V6 proposes the replacement. V7 decides whether the two meanings are truly interchangeable.<br>Only high-confidence synonyms pass.</p></div><div class="stats" id="stats"></div></section>
<div class="toolbar"><input class="search" id="search" placeholder="Search games, tags, contexts"><button data-filter="all" class="active">All</button><button data-filter="rejected">Rejected</button><button data-filter="accepted">Accepted</button></div><div id="content"></div></main>
<script>
let data,filter='all';const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function mapping(r){const ok=!!r.v6_merge_safe_under_v7,pct=Math.round((r.confidence||0)*100);return `<div class="mapping" data-ok="${ok}"><div><div class="tag-label">Raw game tag</div><div class="tag">${esc(r.raw_tag)}</div><span class="context">${esc(r.context)}</span></div><div class="arrow">→</div><div><div class="tag-label">V6 replacement</div><div class="tag">${esc(r.v6_tag)}</div></div><div class="relation">${esc((r.relation||'').replaceAll('_',' '))}<small>${pct}% confidence</small><div class="meter"><div class="fill" style="width:${pct}%"></div></div></div><div class="decision ${ok?'accept':'reject'}">${ok?'USE V6 TAG':'KEEP RAW TAG'}</div><div class="outcome">V7 canonical outcome: <b>${esc(r.v7_canonical_outcome)}</b></div><div class="reason">${esc(r.reason)}</div></div>`}
function render(){const q=document.querySelector('#search').value.trim().toLowerCase();let shown=0;const cards=data.games.map(g=>{const rows=g.results.filter(r=>(filter==='all'||(filter==='accepted')===!!r.v6_merge_safe_under_v7)&&(!q||[g.name,r.raw_tag,r.v6_tag,r.context,r.relation].join(' ').toLowerCase().includes(q)));if(!rows.length)return'';shown++;return `<section class="game"><div class="game-head"><div class="game-icon">${esc(g.name.slice(0,1))}</div><div><div class="game-name">${esc(g.name)}</div><div class="game-id">Steam app ${esc(g.appid)}</div></div><div class="counts"><span class="pill accept">${rows.filter(r=>r.v6_merge_safe_under_v7).length} accepted</span><span class="pill reject">${rows.filter(r=>!r.v6_merge_safe_under_v7).length} rejected</span></div></div><div>${rows.map(mapping).join('')}</div></section>`}).join('');document.querySelector('#content').innerHTML=cards||'<div class="empty">No mappings match this view.</div>'}
fetch('/api/data').then(r=>r.json()).then(d=>{data=d;const s=d.summary;document.querySelector('#stats').innerHTML=`<div class="stat"><b>${s.games_found||0}</b><span>games</span></div><div class="stat"><b>${s.mappings_audited||0}</b><span>audited</span></div><div class="stat good"><b>${s.v6_merges_accepted||0}</b><span>accepted</span></div><div class="stat bad"><b>${s.v6_merges_rejected||0}</b><span>rejected</span></div>`;render()});
document.querySelector('#search').addEventListener('input',render);document.querySelectorAll('button').forEach(b=>b.onclick=()=>{filter=b.dataset.filter;document.querySelectorAll('button').forEach(x=>x.classList.toggle('active',x===b));render()});
</script></body></html>'''


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/data":
            payload = json.dumps(dashboard_data(), ensure_ascii=False).encode("utf-8")
            content_type = "application/json; charset=utf-8"
            status = 200
        elif path in {"/", "/index.html"}:
            payload = HTML.encode("utf-8")
            content_type = "text/html; charset=utf-8"
            status = 200
        else:
            payload = b"Not found"
            content_type = "text/plain; charset=utf-8"
            status = 404
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:
        print(f"canon-v7-ui: {format % args}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Canonical tag v7 sample dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9998)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Canon Tag Lab: http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
