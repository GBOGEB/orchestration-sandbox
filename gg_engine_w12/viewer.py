"""Offline source-bound semantic viewer. Diagram layout is schematic, not geometric truth."""
from __future__ import annotations
import argparse
import hashlib
import html
import json
from pathlib import Path


def safe_json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')


def render(graphs, parity, evidence=None, title='gg_Engine W12 | Semantic review', source_svg='source.svg', pdf_link='layered.pdf'):
    if not all(g.get('contract_version')=='gg-semantic-1.0' for g in graphs.values()):
        raise ValueError('VIEWER_SCHEMA_MISMATCH')
    if not all(g.get('source',{}).get('sha256') for g in graphs.values()):
        raise ValueError('VIEWER_SOURCE_SHA_MISSING')
    payload={'graphs':graphs,'parity':parity,'evidence':evidence or {'links':[], 'quarantine':[]}}
    digest=hashlib.sha256(safe_json(payload).encode('utf-8')).hexdigest()
    title_safe=html.escape(title,quote=True)
    svg_safe=html.escape(source_svg,quote=True)
    pdf_safe=html.escape(pdf_link,quote=True)
    return '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>'''+title_safe+'''</title><style>
:root{--plum:#43144f;--violet:#722c85;--pink:#bb417c;--blush:#f8e8f1;--paper:#fcf9fd;--ink:#272132;--muted:#675e6d;--border:#e4d8e6;--amber:#80510d;--ok:#246a4a}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.5 Aptos,"Segoe UI",Arial,sans-serif}header{background:var(--plum);color:white;padding:23px max(22px,calc((100vw - 1270px)/2));}header h1{font-size:25px;margin:3px 0}header p{margin:0;color:#ebcee9}.header-k{font:700 12px Consolas,monospace;color:#ffd3ea;letter-spacing:.1em}.frame{max-width:1270px;margin:0 auto;padding:20px}.notice{background:white;border-left:4px solid var(--pink);border-radius:0 10px 10px 0;padding:12px 16px;margin-bottom:20px}.toolbar{display:flex;align-items:center;justify-content:space-between;gap:14px;flex-wrap:wrap;margin-bottom:14px}.toolbar label{font-weight:700}.toolbar select,.toolbar input{border:1px solid #ceb7d0;border-radius:9px;padding:9px;color:var(--ink);background:white;font:inherit}.toolbar input{width:min(330px,90vw)}.actions{display:flex;gap:9px;align-items:center;flex-wrap:wrap}.button{border:1px solid var(--border);border-radius:9px;background:white;color:var(--plum);padding:9px 12px;font-weight:700;cursor:pointer;text-decoration:none}.button:hover{background:var(--blush)}.layout{display:grid;grid-template-columns:minmax(0,1.55fr) minmax(310px,1fr);gap:14px}.panel{background:white;border:1px solid var(--border);border-radius:15px;overflow:hidden}.panel h2{font-size:16px;color:var(--plum);margin:0;background:var(--blush);padding:13px 16px}.panel-body{padding:15px}.diagram{width:100%;height:auto;min-height:270px;background:#fffdfd;border:1px solid var(--border);border-radius:11px}.node{cursor:pointer}.node rect{stroke:#813e94;fill:#f7eaf5;stroke-width:2}.node text{fill:var(--plum);font:700 16px Aptos,Arial,sans-serif}.node.active rect{fill:#e9b8d5;stroke:var(--pink);stroke-width:4}.edge-line{stroke:var(--violet);stroke-width:3;fill:none}.edge-text{font:11px Consolas,monospace;fill:#6b5372}.source-image{width:100%;max-height:310px;object-fit:contain;background:#fff;border:1px solid var(--border);border-radius:10px;margin-top:13px}.source-image[hidden]{display:none}.list{list-style:none;margin:0;padding:0;max-height:400px;overflow-y:auto}.list li{border-bottom:1px solid var(--border)}.list button{display:block;border:0;width:100%;background:white;text-align:left;padding:11px 13px;cursor:pointer;font:inherit}.list button:hover,.list button.active{background:var(--blush)}.list small{display:block;color:var(--muted);font:12px Consolas,monospace}.tag{font:700 10px Consolas,monospace;color:var(--pink)}.detail{padding:15px;overflow-wrap:anywhere;min-height:160px}.detail dl{display:grid;grid-template-columns:120px minmax(0,1fr);gap:7px;margin:0}.detail dt{font-weight:700;color:var(--plum)}.detail dd{margin:0;font:12px Consolas,monospace;white-space:pre-wrap}.status{margin:12px 0 0;color:var(--muted);font-size:12px;overflow-wrap:anywhere;word-break:break-word}.detail dt{overflow-wrap:anywhere}.grid2{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:14px;margin-top:14px}.chips{display:flex;gap:8px;flex-wrap:wrap}.chip{background:#f2e9f5;color:var(--violet);border-radius:30px;padding:5px 10px;font:700 11px Consolas,monospace}.chip.alert{background:#fff1d7;color:var(--amber)}.mono{font:12px/1.5 Consolas,"Courier New",monospace;white-space:pre-wrap;overflow-wrap:anywhere}footer{max-width:1270px;margin:30px auto;padding:16px 20px;border-top:1px solid var(--border);color:var(--muted);font-size:12px}@media(max-width:900px){.layout,.grid2{grid-template-columns:1fr}}@media(max-width:540px){.frame{padding:10px}header{padding:20px 13px}.toolbar{align-items:stretch}.toolbar input{width:100%}}
</style></head><body><header><div class="header-k">GG_ENGINE / W12 / INTERACTIVE REVIEW</div><h1>Semantic engineering objects</h1><p>Source-bound identity, direction evidence, legend status and cross-format links</p></header>
<main class="frame"><div class="notice"><b>Review only:</b> drawing positions below are schematic, not recovered native geometry. Synthetic source claims, source hashes and owner authority remain separate. No semantic promotion from a good-looking diagram.</div>
<div class="toolbar"><div class="actions"><label for="format">View source:</label><select id="format" aria-label="Select semantic source"><option value="svg">SVG</option><option value="pptx">PPTX</option></select><input id="search" type="search" placeholder="Search object ID or label" aria-label="Filter semantic objects"></div><div class="actions"><a class="button" href="'''+svg_safe+'''" target="_blank" rel="noopener">Native SVG</a><a class="button" id="pdf-link" href="'''+pdf_safe+'''" target="_blank" rel="noopener">Layered PDF</a><button class="button" id="copy-hash" type="button">Copy source SHA</button></div></div>
<div class="layout"><section class="panel"><h2>Graph object map (schematic layout)</h2><div class="panel-body"><svg class="diagram" id="diagram" role="img" aria-label="Clickable semantic node and edge map" viewBox="0 0 800 350"></svg><img id="native-svg" class="source-image" alt="Original synthetic source SVG for comparative review" src="'''+svg_safe+'''"><p class="status" id="graph-status"></p></div></section><section class="panel"><h2>Selectable objects</h2><ul id="object-list" class="list" aria-label="Graph objects"></ul><div id="object-detail" class="detail" role="region" aria-live="polite" aria-label="Selected object evidence"></div></section></div>
<div class="grid2"><section class="panel"><h2>Cross-format parity</h2><div class="panel-body" id="parity"></div></section><section class="panel"><h2>Document/RTM evidence links</h2><div class="panel-body" id="evidence"></div></section></div>
<div class="status">Semantic snapshot SHA256: <code>'''+digest+'''</code> | No external JavaScript dependencies. All review data embedded locally.</div></main><footer>gg_Engine W12 | HTML is a review projection; Layered PDF OCGs belong to DOW/ABACUS. Independent owner/DOW acceptance is NOT granted by this viewer.</footer>
<script id="review-data" type="application/json">'''+safe_json(payload)+'''</script>
<script>(function(){'use strict';
const data=JSON.parse(document.getElementById('review-data').textContent);
const format=document.getElementById('format'),search=document.getElementById('search'),list=document.getElementById('object-list'),detail=document.getElementById('object-detail'),diagram=document.getElementById('diagram');
let chosen=null;const NS='http://www.w3.org/2000/svg';
function node(tag,attrs,text){const e=document.createElementNS(NS,tag);for(const [k,v] of Object.entries(attrs||{}))e.setAttribute(k,String(v));if(text!==undefined)e.textContent=String(text);return e;}
function label(text,tag){const e=document.createElement(tag||'div');e.textContent=String(text);return e;}
function objects(){const d=data.graphs[format.value];return [...(d.nodes||[]).map(o=>({...o,_kind:'node'})),...(d.edges||[]).map(o=>({...o,_kind:'edge'}))];}
function select(o){chosen=o.id;draw();}
function draw(){const d=data.graphs[format.value],q=search.value.trim().toLowerCase(),all=objects(),filtered=all.filter(o=>[o.id,o.label,o.source_object_id,o.relationship].join(' ').toLowerCase().includes(q));
list.replaceChildren();for(const o of filtered){const li=document.createElement('li'),b=document.createElement('button');b.type='button';b.className=chosen===o.id?'active':'';b.append(label(o._kind+' / '+o.id));const sub=label(o.label||o.relationship||o.state||o.source_object_id||'','small');b.append(sub);b.onclick=()=>select(o);li.append(b);list.append(li);}
diagram.replaceChildren();const ns=d.nodes||[],edges=d.edges||[];const xy={};ns.forEach((o,i)=>{xy[o.id]=[130+540*(i%4)/3,75+Math.floor(i/4)*120];});
for(const e of edges){const a=xy[e.source_id],b=xy[e.target_id];if(!a||!b)continue;diagram.append(node('line',{x1:a[0],y1:a[1],x2:b[0],y2:b[1],class:'edge-line'}));const t=node('text',{x:(a[0]+b[0])/2,y:(a[1]+b[1])/2-15,'text-anchor':'middle',class:'edge-text'},e.direction||'UNKNOWN');diagram.append(t);}
for(const o of ns){const [x,y]=xy[o.id],g=node('g',{class:'node'+(chosen===o.id?' active':''),tabindex:'0',role:'button','aria-label':o.id});g.append(node('rect',{x:x-85,y:y-27,width:170,height:54,rx:12}));g.append(node('text',{x,y:y+6,'text-anchor':'middle'},o.label||o.id));g.addEventListener('click',()=>select(o));g.addEventListener('keydown',ev=>{if(ev.key==='Enter'||ev.key===' '){ev.preventDefault();select(o);}});diagram.append(g);}
const selected=all.find(o=>o.id===chosen)||filtered[0];detail.replaceChildren();if(selected){chosen=selected.id;const dl=document.createElement('dl');for(const [key,value] of Object.entries(selected)){if(key==='_kind')continue;const dt=label(key,'dt'),dd=label(typeof value==='object'?JSON.stringify(value,null,2):value,'dd');dl.append(dt,dd);}detail.append(dl);}else{detail.append(label('No matching objects.'));}
document.getElementById('graph-status').textContent='Source SHA-256: '+d.source.sha256+' | Nodes '+ns.length+' | Edges '+edges.length+' | Quarantine '+(d.quarantine||[]).length;
document.getElementById('native-svg').hidden=format.value!=='svg';}
format.addEventListener('change',()=>{chosen=null;draw();});search.addEventListener('input',draw);document.getElementById('copy-hash').addEventListener('click',async()=>{const s=data.graphs[format.value].source.sha256;try{await navigator.clipboard.writeText(s);}catch(e){const inp=document.createElement('input');inp.value=s;document.body.append(inp);inp.select();document.execCommand('copy');inp.remove();}});
const p=document.getElementById('parity');p.append(label(data.parity.status,'strong'));p.append(label(' | '+data.parity.nodes_before+' → '+data.parity.nodes_after+' nodes; '+data.parity.edges_before+' → '+data.parity.edges_after+' edges'));for(const f of data.parity.findings||[])p.append(label(f.code+': '+f.message,'div'));
const ep=document.getElementById('evidence');const links=data.evidence.links||[],quarantine=data.evidence.quarantine||[];ep.append(label(links.length+' explicit trace links; '+quarantine.length+' quarantined bindings','strong'));for(const l of links)ep.append(label(l.semantic_id+' ← '+l.evidence_format+':'+l.source_object_id+' [CANDIDATE]','div'));for(const q of quarantine)ep.append(label('BLOCKED '+JSON.stringify(q),'div'));draw();})();</script></body></html>'''


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--svg-claim',required=True,type=Path)
    ap.add_argument('--pptx-claim',required=True,type=Path)
    ap.add_argument('--parity',required=True,type=Path)
    ap.add_argument('--out',required=True,type=Path)
    args=ap.parse_args()
    doc=render({'svg':json.loads(args.svg_claim.read_text()),'pptx':json.loads(args.pptx_claim.read_text())}, json.loads(args.parity.read_text()))
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(doc,encoding='utf-8')
    print(args.out)


if __name__=='__main__':
    main()
