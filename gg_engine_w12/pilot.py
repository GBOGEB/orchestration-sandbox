"""W12 controlled native-object roundtrip: SVG -> W11 claim -> PPTX -> W11 claim -> SVG.

Only supports the small synthetic fixture grammar. This is a real OOXML/SVG byte
rebuild and parse cycle, NOT a production converter or owner-authorized twin.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT/'gg_engine_w11') not in sys.path:
    sys.path.insert(0,str(ROOT/'gg_engine_w11'))
from svg_adapter import read_svg
from pptx_adapter import read_pptx
import synthetic_fixtures as fx
from w10_bridge import compare_graphs, receipt
from viewer import render

FIXED=(2026,11,13,0,0,0)
NAME=re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,40}$')


def write_json(path,value):
    Path(path).write_text(json.dumps(value,sort_keys=True,indent=2,ensure_ascii=True)+'\n',encoding='utf-8')


def supported_flow(graph):
    nodes=sorted(graph['nodes'],key=lambda x:x['id'])
    edges=graph['edges']
    if len(nodes)!=2 or len(edges)!=1 or graph.get('quarantine'):
        raise ValueError('EMITTER_UNSUPPORTED_GRAPH_SIZE_OR_QUARANTINE')
    names={n['id']:n['id'].split(':',1)[-1] for n in nodes}
    if not all(NAME.fullmatch(s) for s in names.values()):
        raise ValueError('EMITTER_UNSAFE_NAME')
    edge=edges[0]
    if not (edge['source_id'] in names and edge['target_id'] in names and
            edge['state']=='CANDIDATE' and edge['direction']=='SOURCE_TO_TARGET' and
            edge['relationship']=='FLOW'):
        raise ValueError('EMITTER_UNSUPPORTED_EDGE_AUTHORITY_OR_DIRECTION')
    return names,edge


def emit_pptx(graph):
    names,edge=supported_flow(graph)
    # Source/target identity is controlled by the accepted W10 claim.
    a,b=names[edge['source_id']],names[edge['target_id']]
    # W11 fixture factory is only used as a transparent synthetic OOXML emitter.
    return fx.pptx_bytes([fx.shape(4,a,a),fx.shape(5,b,b),
        fx.connector(9,'flow-001',4,5,tail='triangle',color='0000FF'),
        fx.shape(12,'Legend','Blue line = FLOW')])


def emit_svg(graph):
    names,edge=supported_flow(graph)
    a,b=names[edge['source_id']],names[edge['target_id']]
    return fx.svg_doc(fx.svg_shape('p101',a,a,transform='translate(0,40)'),
            fx.svg_shape('hx201',b,b,transform='translate(200,40)'),
            fx.svg_connector('flow001','flow-001','p101','hx201',marker_end='ArrowEnd'))


def no_promotion(*graphs):
    for doc in graphs:
        if doc.get('adapter',{}).get('qualification',{}).get('owner_acceptance')!='HOLD':
            raise ValueError('ADAPTER_AUTHORITY_PROMOTION')
        if any(e.get('state')=='GOLDEN' for e in doc['edges']):
            raise ValueError('GOLDEN_FROM_UNAPPROVED_SOURCE')


def archive(outdir,zip_path):
    zip_path=Path(zip_path)
    hashes={}
    files=sorted(p for p in Path(outdir).rglob('*') if p.is_file() and p!=zip_path and p.name!='SHA256SUMS.txt')
    for p in files:
        hashes[p.relative_to(outdir).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
    sums=''.join(f'{digest}  {filename}\n' for filename,digest in sorted(hashes.items()))
    (Path(outdir)/'SHA256SUMS.txt').write_text(sums,encoding='utf-8')
    files=files+[Path(outdir)/'SHA256SUMS.txt']
    zip_path.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(zip_path,'w',compression=zipfile.ZIP_STORED) as z:
        for path in sorted(files):
            info=zipfile.ZipInfo(path.relative_to(outdir).as_posix(),FIXED)
            info.compress_type=zipfile.ZIP_STORED
            info.create_system=3
            info.external_attr=0o644<<16
            z.writestr(info,path.read_bytes())
    return {'zip_sha256':hashlib.sha256(zip_path.read_bytes()).hexdigest(),'files':hashes}


def run(out,abacus_root=None):
    out=Path(out)
    out.mkdir(parents=True,exist_ok=True)
    svg=fx.svg_flow()
    graph0=read_svg(svg, name='source.svg', legend=fx.svg_legend(svg))
    pptx=emit_pptx(graph0)
    graph1=read_pptx(pptx,name='from_svg.pptx',legend=fx.pptx_legend(pptx))
    svg2=emit_svg(graph1)
    graph2=read_svg(svg2,name='roundtrip.svg',legend=fx.svg_legend(svg2))
    no_promotion(graph0,graph1,graph2)
    for doc in [graph0,graph1,graph2]:
        if receipt(doc)['status']!='PASS_CONTRACT_ONLY':
            raise ValueError('W10_GRAPH_CONTRACT_FAIL')
    p01=compare_graphs(graph0,graph1)
    p12=compare_graphs(graph1,graph2)
    if p01['status']!='PASS_SEMANTIC_PARITY_ONLY' or p12['status']!='PASS_SEMANTIC_PARITY_ONLY':
        raise ValueError('W10_SEMANTIC_PARITY_FAIL')
    (out/'source.svg').write_bytes(svg)
    (out/'from_svg.pptx').write_bytes(pptx)
    (out/'roundtrip.svg').write_bytes(svg2)
    write_json(out/'source_legend.synthetic.json',fx.svg_legend(svg))
    write_json(out/'pptx_legend.synthetic.json',fx.pptx_legend(pptx))
    write_json(out/'source_claim.json',graph0)
    write_json(out/'pptx_claim.json',graph1)
    write_json(out/'roundtrip_claim.json',graph2)
    write_json(out/'svg_to_pptx_parity.json',p01)
    write_json(out/'pptx_to_svg_parity.json',p12)
    (out/'index.html').write_text(render({'svg':graph0,'pptx':graph1},p01),encoding='utf-8')
    dow={'status':'DEFERRED_NOT_INSTALLED','engineering_acceptance':'HOLD'}
    if abacus_root:
        from dow_bridge import build
        dow=build(out/'source.svg',out/'layered.pdf',abacus_root,strict=True)
    write_json(out/'dow_receipt.json',dow)
    report={
        'schema':'gg-w12-convergence-0.1','source_type':'SYNTHETIC_NATIVE_FORMAT_BYTES',
        'input_svg_sha256':hashlib.sha256(svg).hexdigest(),
        'pptx_sha256':hashlib.sha256(pptx).hexdigest(),
        'roundtrip_svg_sha256':hashlib.sha256(svg2).hexdigest(),
        'graph_source_to_pptx':p01['status'],'graph_pptx_to_svg':p12['status'],
        'graph_nodes':len(graph0['nodes']),'graph_edges':len(graph0['edges']),
        'real_owner_binary_test':'NOT_RUN','independent_human_review':'OPEN',
        'native_powerpoint_open':'NOT_TESTED','native_inkscape_open':'NOT_TESTED',
        'dow':dow.get('status'),'owner_acceptance':'HOLD',
        'claim':'NATIVE_OOXML_SVG_SEMANTIC_ROUNDTRIP_SYNTHETIC_ONLY',
        'no_private_sources':True,
    }
    write_json(out/'roundtrip_receipt.json',report)
    bundle=archive(out,out/'gg_engine_w12_demo.zip')
    report['bundle_sha256']=bundle['zip_sha256']
    return report


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--out',default='w12-out')
    ap.add_argument('--abacus-root',default=None)
    args=ap.parse_args()
    print(json.dumps(run(args.out,args.abacus_root),sort_keys=True,indent=2))


if __name__=='__main__':
    main()
