"""Fixture diagnostics, intentionally separate from inference. Not a population benchmark."""
from __future__ import annotations
import argparse
from collections import Counter
from pathlib import Path
import unicodedata

from common import BENCHMARK,FIXTURES,read_json,write_json,iou,intersection,area


def normalize(text):
    return " ".join(unicodedata.normalize("NFC",text).casefold().split())


def match_regions(targets,predictions,threshold=.5):
    from scipy.optimize import linear_sum_assignment
    if not targets or not predictions: return []
    matrix=[[iou(t["bbox"],p["bbox"]) if p.get("bbox") else 0 for p in predictions] for t in targets]
    # Prioritize maximum number above threshold, then IoU within that cardinality.
    weights=[[-(10+v) if v>=threshold else 0 for v in row] for row in matrix]
    rows,cols=linear_sum_assignment(weights)
    return [(int(r),int(c),matrix[r][c]) for r,c in zip(rows,cols) if matrix[r][c]>=threshold]


def score_page(gt,pred):
    items=gt["components"]; byid={i["id"]:i for i in items}
    result=dict(table_matches=[],figure_matches=[],text_checks=[],issues=[])
    tables=[i for i in items if i["type"]=="table"]
    matches=match_regions(tables,pred["tables"])
    table_links={tables[ti]["id"]:pred["tables"][pi]["id"] for ti,pi,_ in matches}
    result["table_detection"]=dict(expected=len(tables),predicted=len(pred["tables"]),matched=len(matches))
    complete_ids={t["id"] for t in tables if t.get("grid_policy")=="complete"}
    expected_cell_text=sum(1 for c in items if c["type"]=="table_cell" and c["parent_id"] in complete_ids and
        any(i.get("text") and i["parent_id"]==c["id"] and i.get("recognition_target",True) for i in items))
    result["cell_text_evaluation"]=dict(expected=expected_cell_text,compared=0,exact=0)
    for ti,pi,overlap in matches:
        target,p=tables[ti],pred["tables"][pi]
        check=dict(gt_id=target["id"],prediction_id=p["id"],iou=overlap,grid_policy=target.get("grid_policy"),
                   expected_shape=[target["rows"],target["cols"]],predicted_shape=[p["rows"],p["cols"]])
        if target.get("grid_policy")=="complete":
            cells=[i for i in items if i["type"]=="table_cell" and i["parent_id"]==target["id"]]
            key=lambda c:(c["row"],c["col"],c["rowspan"],c["colspan"])
            expected={key(c) for c in cells}; actual={key(c) for c in p["cells"]}
            correct=expected&actual
            check.update(shape_exact=check["expected_shape"]==check["predicted_shape"],
                         span_grid_exact=expected==actual and len(p["cells"])==len(actual),
                         cells_expected=len(cells),cells_predicted=len(p["cells"]),logical_cells_exact=len(correct))
            if not check["span_grid_exact"]:
                result["issues"].append(dict(type="table_structure_mismatch",target_id=target["id"],detail=check))
            text_comparison=[]
            for c in cells:
                pc=next((pc for pc in p["cells"] if key(pc)==key(c)),None)
                expected_text=" ".join(i["text"] for i in items if i["parent_id"]==c["id"] and "text" in i and i.get("recognition_target",True))
                if pc is not None and expected_text:
                    text_comparison.append(dict(row=c["row"],col=c["col"],expected=expected_text,
                        predicted=pc["text"],exact=normalize(expected_text)==normalize(pc["text"])))
            check["cell_text_checks"]=text_comparison
            result["cell_text_evaluation"]["compared"]+=len(text_comparison)
            result["cell_text_evaluation"]["exact"]+=sum(c["exact"] for c in text_comparison)
        result["table_matches"].append(check)
    for i,t in enumerate(tables):
        if i not in {m[0] for m in matches}:
            issue="single_cell_box_not_classified_as_table" if t["rows"]==t["cols"]==1 else "table_region_missing_or_low_iou"
            result["issues"].append(dict(type=issue,target_id=t["id"],bbox=t["bbox"]))
    figures=[i for i in items if i["type"] in ("image","diagram")]
    predictions=[b for b in pred["blocks"] if b["type"]=="figure" and b.get("bbox")]
    matches=match_regions(figures,predictions)
    result["figure_detection"]=dict(expected=len(figures),predicted=len(predictions),matched=len(matches),
        body_expected=sum(i.get("layer")!="furniture" for i in figures),
        body_matched=sum(figures[m[0]].get("layer")!="furniture" for m in matches),
        diagram_expected=sum(i["type"]=="diagram" for i in figures),
        diagram_matched=sum(figures[m[0]]["type"]=="diagram" for m in matches),
        nested_expected=sum(byid.get(i["parent_id"],{}).get("type") in ("table_cell","container","table") for i in figures))
    for ti,pi,overlap in matches:
        t,p=figures[ti],predictions[pi]
        parent=byid.get(t["parent_id"],{})
        nested=parent.get("type") in ("table_cell","container","table")
        parent_ref=p.get("parent_ref")
        lookup={b["id"]:b for b in pred["blocks"]+pred.get("containers",[])}
        visited=set(); predicted_table_parent=None;predicted_cell_parent=None
        while parent_ref and parent_ref not in visited:
            visited.add(parent_ref); explicit_parent=lookup.get(parent_ref)
            if not explicit_parent: break
            if explicit_parent["type"]=="table_cell":predicted_cell_parent=explicit_parent
            if explicit_parent["type"]=="table":
                predicted_table_parent=explicit_parent["id"]; break
            parent_ref=explicit_parent.get("parent_ref")
        gt_parent=t.get("parent_id"); gt_seen=set(); expected_table_parent=None
        while gt_parent and gt_parent not in gt_seen:
            gt_seen.add(gt_parent); ancestor=byid.get(gt_parent,{})
            if ancestor.get("type")=="table":
                expected_table_parent=gt_parent; break
            gt_parent=ancestor.get("parent_id")
        nested_explicit=bool(predicted_table_parent and expected_table_parent and
                             table_links.get(expected_table_parent)==predicted_table_parent)
        cell_verified=None
        if parent.get("type")=="table_cell":
            cell_verified=bool(nested_explicit and predicted_cell_parent and all(
                parent[k]==predicted_cell_parent.get(k) for k in ("row","col","rowspan","colspan")))
        check=dict(gt_id=t["id"],prediction_id=p["id"],expected_type=t["type"],predicted_label=p["label"],
            iou=overlap,target_area_coverage=intersection(t["bbox"],p["bbox"])/area(t["bbox"]),
            bbox_purity=intersection(t["bbox"],p["bbox"])/area(p["bbox"]),
            nested_expected=nested,nested_explicit=nested_explicit,
            predicted_table_parent=predicted_table_parent,
            cell_ownership_verified=cell_verified,
            note="Explicit ancestor is checked against the matched table; exact cell ownership is not automatically verified")
        result["figure_matches"].append(check)
        if t["type"]=="diagram":
            leaked=[b["id"] for b in pred["blocks"] if b["type"] in ("text","heading") and b.get("bbox")
                    and intersection(b["bbox"],t["bbox"])/max(1e-9,area(b["bbox"]))>=.7]
            if leaked:
                result["issues"].append(dict(type="diagram_and_independent_text_overlap",target_id=t["id"],
                    block_ids=leaked,note="Review whether diagram labels are also emitted as independent document text"))
        if check["target_area_coverage"]<.95:
            result["issues"].append(dict(type="figure_crop_may_be_incomplete",target_id=t["id"],detail=check))
        if nested and not nested_explicit:
            result["issues"].append(dict(type="nested_figure_parent_unresolved",target_id=t["id"],detail=check))
    for i,t in enumerate(figures):
        if i not in {m[0] for m in matches}:
            result["issues"].append(dict(type="figure_region_missing_or_low_iou",expected_type=t["type"],
                target_id=t["id"],bbox=t["bbox"],layer=t.get("layer","body")))
    # Localized text diagnostic accepts one-to-many line segmentation. It is not CER/WER.
    for t in items:
        if "text" not in t or not t.get("recognition_target",True): continue
        if t.get("rotation_degrees"):
            # Horizontal paragraph geometry is not a valid matching rule for rotated text.
            result["text_checks"].append(dict(gt_id=t["id"],text=t["text"],rotation=t["rotation_degrees"],
                evaluation="manual_rotated_text",layer=t.get("layer","body")))
            continue
        candidates=[]
        for p in pred["texts"]:
            b=p["bbox"]; tb=t["bbox"]
            vertical=max(0,min(tb[3],b[3])-max(tb[1],b[1]))/max(1,min(tb[3]-tb[1],b[3]-b[1]))
            horizontal=max(0,min(tb[2],b[2])-max(tb[0],b[0]))/max(1,min(tb[2]-tb[0],b[2]-b[0]))
            if vertical>=.45 and horizontal>=.45 and area(b)<=max(area(tb)*7,1):
                candidates.append(p)
        candidates.sort(key=lambda p:(round(p["bbox"][1]/5),p["bbox"][0]))
        actual=" ".join(p["text"] for p in candidates)
        expected=normalize(t["text"]); observed=normalize(actual)
        ec,ac=Counter(expected.split()),Counter(observed.split())
        recall=sum((ec&ac).values())/max(1,sum(ec.values()))
        check=dict(gt_id=t["id"],text=t["text"],observed=actual,spatial_token_recall=recall,
                   exact=expected==observed,layer=t.get("layer","body"),
                   note="Whitespace/case/NFC normalized; sensitive to bbox alignment, not an OCR-only metric")
        result["text_checks"].append(check)
        if recall<.8:
            result["issues"].append(dict(type="localized_text_needs_review",target_id=t["id"],detail=check))
    return result


def evaluate(run_name="baseline"):
    output_directory=BENCHMARK if run_name=="baseline" else BENCHMARK/"experiments"/run_name
    rows=[]
    for engine in ("docling","paddle"):
        run=BENCHMARK/"runs"/engine/run_name
        for path in sorted(run.glob("sop_*/page_*/status.json")):
            status=read_json(path)
            row=dict(engine=engine,pdf=status["pdf"],page_number=status["page_number"],state=status["state"],
                     directory=path.parent.relative_to(BENCHMARK).as_posix(),seconds=status.get("seconds"),
                     peak_rss_bytes=status.get("peak_rss_bytes"),phase_seconds=status.get("phase_seconds",{}))
            if status["state"]=="success":
                gt=read_json(FIXTURES/Path(status["pdf"]).with_suffix(".ground_truth.json"))
                if gt["sha256"]!=status["pdf_sha256"]: raise ValueError("Stale source/annotation pair")
                page=next(p for p in gt["pages"] if p["page_number"]==status["page_number"])
                row.update(score_page(page,read_json(path.parent/"evidence.json")))
                write_json(path.parent/"evaluation.json",row)
            else: row["error"]=status.get("error","incomplete")
            rows.append(row)
    summaries=[]
    for engine in ("docling","paddle"):
        ok=[r for r in rows if r["engine"]==engine and r["state"]=="success"]
        summary=dict(engine=engine,successful_pages=len(ok),failed_pages=sum(r["engine"]==engine and r["state"]=="failed" for r in rows),
                     running_pages=sum(r["engine"]==engine and r["state"]=="running" for r in rows),
                     not_run_pages=max(0,16-sum(r["engine"]==engine for r in rows)),expected_pages=16)
        for category in ("table_detection","figure_detection"):
            totals={key:sum(r[category][key] for r in ok) for key in ("expected","predicted","matched")}
            summary[category]=totals
        summary["issues"]=dict(Counter(i["type"] for r in ok for i in r["issues"]))
        summaries.append(summary)
        for key in ("body_expected","body_matched","diagram_expected","diagram_matched","nested_expected"):
            summary["figure_detection"][key]=sum(r["figure_detection"][key] for r in ok)
        summary["nested_explicit"]=sum(f["nested_expected"] and f["nested_explicit"] for r in ok for f in r["figure_matches"])
        summary["complete_grids_exact"]=sum(t.get("span_grid_exact",False) for r in ok for t in r["table_matches"])
        summary["cell_text_evaluation"]={key:sum(r["cell_text_evaluation"][key] for r in ok) for key in ("expected","compared","exact")}
        summary["cell_ownership_verified"]=sum(f["cell_ownership_verified"] is True for r in ok for f in r["figure_matches"])
    output=dict(policy=dict(region_match_iou=.5,matching="one-to-one maximum-cardinality then IoU",
        table_structure="exact logical cell row/col/spans; partial layout grids excluded",
        text="localized normalized token recall diagnostic, NOT CER/WER",
        population="4 authored page designs, 16 paired variants; no generalization estimate",
        nesting="explicit predicted parent only; geometric containment does not count as successful ownership"),
        summaries=summaries,pages=rows)
    output["run_name"]=run_name
    write_json(output_directory/"evaluation.json",output)
    print(__import__("json").dumps(summaries,indent=2))
    return output


if __name__=="__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("--run-name",default="baseline")
    evaluate(ap.parse_args().run_name)
