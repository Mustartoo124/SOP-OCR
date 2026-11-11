"""Portable local HTML report: evidence, annotations, crops, tables, diagnostics."""
from __future__ import annotations
import html
import json
import argparse
import os
from pathlib import Path

from common import BENCHMARK,FIXTURES,read_json
from evaluate import evaluate

def esc(value): return html.escape(str(value))


def build(run_name="baseline"):
    results=evaluate(run_name)
    report_directory=BENCHMARK if run_name=="baseline" else BENCHMARK/"experiments"/run_name
    sections=[]
    for row in results["pages"]:
        directory=BENCHMARK/row["directory"]
        relative=Path(os.path.relpath(directory,report_directory)).as_posix()
        title=f"{row['engine']} / {row['pdf']} / page {row['page_number']}"
        if row["state"]!="success":
            sections.append(f'<section><h2>{esc(title)}</h2><p class="bad">{esc(row.get("error",row["state"]))}</p></section>')
            continue
        pred=read_json(directory/"evidence.json")
        crops=read_json(directory/"crops.json")
        gt=read_json(FIXTURES/Path(row["pdf"]).with_suffix(".ground_truth.json"))
        page=next(p for p in gt["pages"] if p["page_number"]==row["page_number"])
        rects=[]
        for item in page["components"]:
            a,b,c,d=item["bbox"]
            color={"diagram":"#C026D3","image":"#16A34A","table":"#DC2626","table_cell":"#D99A00"}.get(item["type"],"#2563EB")
            rects.append(f'<rect x="{a}" y="{b}" width="{c-a}" height="{d-b}" fill="none" stroke="{color}" stroke-width=".8"><title>{esc(item["id"]+": "+item["type"])}</title></rect>')
        source_image=BENCHMARK/f'inputs/{Path(row["pdf"]).stem}/page_{row["page_number"]:03}.png'
        source_image=Path(os.path.relpath(source_image,report_directory)).as_posix()
        svg=f'<svg viewBox="0 0 {page["width"]} {page["height"]}"><image href="{source_image}" width="{page["width"]}" height="{page["height"]}"/><g>{"".join(rects)}</g></svg>'
        links=[]
        for i in range(len(pred["tables"])):
            raw_file=directory/f"table_{i:02}.html"
            markup=raw_file.read_text(encoding="utf-8")
            start=markup.lower().find("<table"); end=markup.lower().rfind("</table>")
            fragment=markup[start:end+8] if start>=0 and end>=start else esc(markup)
            description="Structure and text are the parser's unchanged table fragment; only viewing styles were added." if run_name=="baseline" else "Geometry-refined table. Original parser table/evidence are retained separately; OCR text can still contain errors."
            viewer=f'''<!doctype html><meta charset="utf-8"><title>{esc(title)} - Table {i+1}</title>
<style>body{{font:15px/1.5 system-ui;margin:24px;color:#233448}}table{{border-collapse:collapse}}td,th{{border:1px solid #94a3b8;padding:9px;min-width:70px;max-width:330px;vertical-align:top;overflow-wrap:anywhere}}th{{background:#eaf2f5}}img{{max-width:300px}}</style>
<h1>{esc(title)} - Table {i+1}</h1><p>{description} <a href="table_{i:02}.html">HTML</a></p>{fragment}'''
            (directory/f"table_{i:02}.view.html").write_text(viewer,encoding="utf-8")
            links.append(f'<a href="{relative}/table_{i:02}.view.html">Table {i+1}</a>')
        table_links=" ".join(links)
        gallery="".join(f'<figure><a href="{relative}/{c["file"]}"><img loading="lazy" src="{relative}/{c["file"]}"></a><figcaption>{esc(c["block_id"])} / {esc(c["type"])}</figcaption></figure>' for c in crops)
        issues="".join(f'<li><b>{esc(i["type"])}</b> {esc(i.get("target_id",""))}</li>' for i in row["issues"])
        text_rows="".join(f'<tr><td>{esc(t["gt_id"])}</td><td>{esc(t["text"])}</td><td>{esc(t.get("observed","Manual rotated text check"))}</td><td>{t.get("spatial_token_recall",0):.0%}</td></tr>' for t in row["text_checks"])
        structure_rows="".join(f'<tr><td>{esc(t["gt_id"])}</td><td>{esc(t["expected_shape"])}</td><td>{esc(t["predicted_shape"])}</td><td>{esc(t.get("span_grid_exact","partial grid - excluded"))}</td></tr>' for t in row["table_matches"])
        native=esc(json.dumps(pred["blocks"],ensure_ascii=False,indent=2))
        phases=" · ".join(f'{esc(key)} {value:.2f}s' for key,value in row.get("phase_seconds",{}).items())
        extra_links=""
        if run_name!="baseline":
            extra_links=f'<a href="{relative}/parser_evidence.json">Original parser evidence</a> · <a href="{relative}/token_ownership.json">All source tokens / ownership</a> · <a href="{relative}/geometry_candidates.json">Geometry candidates</a>'
        sections.append(f'''<section data-engine="{row['engine']}"><h2>{esc(title)}</h2>
<p>{row['seconds']:.1f}s · sampled process-tree peak RSS {row['peak_rss_bytes']/1024**3:.2f} GiB · {len(pred['blocks'])} blocks · {len(pred['tables'])} tables</p>
<p>{phases}</p>
<div class="views"><div><h3>Authoring ground truth</h3>{svg}</div><div><h3>Parser regions</h3><a href="{relative}/overlay.png"><img loading="lazy" src="{relative}/overlay.png"></a></div><div><h3>Parser cell geometry</h3><a href="{relative}/cells_overlay.png"><img loading="lazy" src="{relative}/cells_overlay.png"></a></div></div>
<p>{table_links} · <a href="{relative}/evidence.json">Evidence JSON</a> · <a href="{relative}/evaluation.json">Diagnostics</a> · <a href="{relative}/parser.log">Parser log</a></p>
<p>{extra_links}</p>
<details open><summary>Automatically flagged review candidates ({len(row['issues'])})</summary><ul>{issues or '<li>No automatic flags; this does not establish correctness.</li>'}</ul></details>
<details><summary>Table shape and merged-cell checks</summary><table><tr><th>Target</th><th>Expected</th><th>Predicted</th><th>Exact logical grid</th></tr>{structure_rows}</table></details>
<details><summary>Localized text comparison (not CER/WER)</summary><table><tr><th>Target</th><th>Expected</th><th>Observed in region</th><th>Token recall</th></tr>{text_rows}</table></details>
<details><summary>Component associations in this output</summary><pre>{native}</pre></details>
<h3>Source-page region crops</h3><div class="gallery">{gallery or '<p>No figure/table region crops.</p>'}</div></section>''')
    summary_rows="".join(f'<tr><td>{s["engine"]}</td><td>{s["successful_pages"]}/16</td><td>{s["table_detection"]["matched"]}/{s["table_detection"]["expected"]}</td><td>{s["figure_detection"]["body_matched"]}/{s["figure_detection"]["body_expected"]}</td><td>{s["figure_detection"]["diagram_matched"]}/{s["figure_detection"]["diagram_expected"]}</td><td>{s["complete_grids_exact"]}</td></tr>' for s in results["summaries"])
    document='''<!doctype html><html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SOP extraction experiment</title>
<style>body{font:15px/1.5 system-ui,sans-serif;color:#233448;background:#eef3f5;margin:24px}main{max-width:1700px;margin:auto}section,.intro{background:white;border:1px solid #d1dce1;border-radius:10px;padding:22px;margin:24px 0}.views{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}.views img,svg{width:100%;height:auto}.gallery{display:flex;flex-wrap:wrap;gap:20px}.gallery figure{margin:0;max-width:420px}.gallery img{max-width:100%;max-height:440px;object-fit:contain}table{border-collapse:collapse;width:100%}td,th{border:1px solid #cad7de;padding:8px;text-align:left;vertical-align:top}pre{white-space:pre-wrap;max-height:500px;overflow:auto}summary{cursor:pointer;font-weight:600;padding:10px 0}.bad{color:#b91c1c}a{color:#076c94}nav{position:sticky;top:0;background:#233448;color:white;padding:12px;z-index:2}button{margin-right:12px;padding:8px 18px;cursor:pointer}@media(max-width:900px){.views{grid-template-columns:1fr}body{margin:10px}}</style>
<main><div class="intro"><h1>SOP extraction experiment</h1><p>Independent Docling and PP-StructureV3 baselines. Synthetic fixtures only: 4 page designs in 16 paired variants. No custom diagram grouping, text recovery fusion, or learned routing.</p><p>Region matches use one-to-one IoU ≥ 0.5. Table grid checks exclude ambiguous layout grids. Figure matching does not establish diagram semantics or correct cell ownership. Text flags are spatial diagnostics, not CER/WER. Unmatched elements and automatic flags require visual review.</p><table><tr><th>Engine</th><th>Completed pages</th><th>Table regions matched / expected</th><th>Body figures matched / expected</th><th>Diagram regions matched / expected</th><th>Complete logical grids exact</th></tr>'''+summary_rows+'''</table><p>Blue=text, red=table, yellow=cell, purple=diagram/figure, green=ground-truth image. Timings include page preparation and parser work; startup/downloads are recorded separately. They are not controlled speed benchmarks.</p><p><a href="evaluation.json">Full evaluation JSON</a> · <a href="REPORT.md">Findings and limitations</a></p></div><nav><button onclick="filter('all')">All</button><button onclick="filter('docling')">Docling</button><button onclick="filter('paddle')">PaddleOCR</button></nav>'''+"".join(sections)+'''</main><script>function filter(engine){document.querySelectorAll('section[data-engine]').forEach(s=>s.hidden=engine!=='all'&&s.dataset.engine!==engine)}</script></html>'''
    if run_name!="baseline":
        document=document.replace("Independent Docling and PP-StructureV3 baselines.","Geometry-refined Docling and PP-StructureV3 experiment.")
        document=document.replace("No custom diagram grouping, text recovery fusion, or learned routing.","Includes native text/image recovery, ruled-grid reconstruction, connected-shape diagram grouping and token ownership. Rules target upright ruled pages; candidates still need review.")
        document=document.replace("They are not controlled speed benchmarks.","The measured run is sequential with pre-cached models; initialization, processing and exports are recorded separately in timing.json. This is a single run on the current CPU, not a hardware-independent benchmark.")
        document=document.replace('<a href="evaluation.json">Full evaluation JSON</a>', '<a href="evaluation.json">Full evaluation JSON</a> · <a href="timing.json">Sequential runtime</a> · <a href="comparison.json">Baseline comparison</a>')
    (report_directory/"index.html").write_text(document,encoding="utf-8")
    print(report_directory/"index.html")


if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("--run-name",default="baseline")
    build(ap.parse_args().run_name)
