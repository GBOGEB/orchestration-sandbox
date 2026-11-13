"""Use the pinned ABACUS DOW SVG/PDF engine as an external dependency; never copy it.

The DOW engine owns PDF OCG build/fidelity logic. This bridge checks checkout
identity and writes transparent receipts. It cannot waive the ABACUS red gates.
"""
from __future__ import annotations
import hashlib
import json
import subprocess
import sys
from pathlib import Path

PIN='eca6782f9850b61c083c25a03371a7be74aa0a98'


def verify_checkout(root):
    root=Path(root).resolve()
    if not (root/'DMAIC_V3'/'svg_engine'/'pdf_ocg.py').exists():
        raise ValueError('DOW_ENGINE_MISSING')
    cp=subprocess.run(['git','-C',str(root),'rev-parse','HEAD'],text=True,capture_output=True,check=False)
    if cp.returncode or cp.stdout.strip()!=PIN:
        raise ValueError('DOW_SHA_DRIFT')
    return root


def build(source_svg,output_pdf,abacus_root,strict=True):
    root=verify_checkout(abacus_root)
    sys.path.insert(0,str(root))
    from DMAIC_V3.svg_engine.ingress import load_svg, layer_items
    from DMAIC_V3.svg_engine.pdf_ocg import build_nested_ocg_pdf,build_flat_ocg_pdf
    from DMAIC_V3.svg_engine.fidelity import check_pdf_fidelity
    source_svg=Path(source_svg)
    output_pdf=Path(output_pdf)
    svgroot,raw=load_svg(source_svg)
    source_sha=hashlib.sha256(raw).hexdigest()
    build_receipt=build_nested_ocg_pdf(svgroot,output_pdf,source_bytes=raw)
    flat=output_pdf.with_name('flat_baseline.pdf')
    build_flat_ocg_pdf(svgroot,flat,source_bytes=raw)
    qa=check_pdf_fidelity(output_pdf,build_receipt,svgroot,baseline_pdf=flat)
    checks=qa.get('checks',[])
    fail=[c.get('id') for c in checks if c.get('result')=='FAIL']
    ret={
        'schema':'gg-w12-dow-bridge-0.1','engine':'DMAIC_V3.svg_engine',
        'engine_git_sha':PIN,'source_svg_sha256':source_sha,
        'pdf_sha256':hashlib.sha256(output_pdf.read_bytes()).hexdigest(),
        'ocg_count':build_receipt.get('ocg_count'),
        'source_layer_count':len(layer_items(svgroot)),
        'status':'PASS_REVIEW_ONLY' if not fail else 'FAIL_FIDELITY',
        'checks':checks,'failures':fail,
        'source_validation':'NATIVE_SOURCE_SAFETY_PASSED',
        'engine_admission':'ABACUS_PR_2745_STILL_SEPARATELY_GATED',
        'native_acrobat_layer_panel':'NOT_TESTED',
        'engineering_acceptance':'HOLD'
    }
    output_pdf.with_name('dow_fidelity_receipt.json').write_text(json.dumps(ret,indent=2,sort_keys=True)+'\n')
    if strict and fail:
        raise RuntimeError('DOW_FIDELITY_FAIL:'+','.join(fail))
    return ret
