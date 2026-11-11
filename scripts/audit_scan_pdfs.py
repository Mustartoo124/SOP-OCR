"""Audit actual image-only PDF contents; viewer selection is not a modality test."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import fitz
import pdfplumber
from pypdf import PdfReader
from pypdf.generic import ContentStream

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"output/pdf"
SHOW_TEXT={b"Tj",b"TJ",b"'",b'"'}
PAINT_PATH={b"S",b"s",b"f",b"F",b"f*",b"B",b"B*",b"b",b"b*",b"sh"}


def resolved(value):
    return value.get_object() if hasattr(value,"get_object") else value


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stream_audit(stream,resources,reader,seen=None):
    seen=set() if seen is None else seen
    counts=Counter(); images=0; text_show=0; paint=0; actual_text=False
    for operands,operator in ContentStream(stream,reader).operations:
        counts[operator.decode("latin1")]+=1
        text_show+=operator in SHOW_TEXT
        paint+=operator in PAINT_PATH
        if operator==b"BDC":
            actual_text|=any(isinstance(o,dict) and "/ActualText" in o for o in operands)
        if operator==b"Do":
            obj=resolved(resources.get("/XObject",{})).get(operands[0])
            if obj is None: raise ValueError("Unresolved XObject")
            obj=obj.get_object()
            if obj.get("/Subtype")=="/Image": images+=1
            elif obj.get("/Subtype")=="/Form" and id(obj) not in seen:
                seen.add(id(obj))
                nested=stream_audit(obj,resolved(obj.get("/Resources",resources)),reader,seen)
                text_show+=nested["text_show_operations"]
                paint+=nested["vector_paint_operations"]
                images+=nested["image_draw_operations"]
                actual_text|=nested["actual_text_marked_content"]
    return dict(operators=dict(counts),text_show_operations=text_show,vector_paint_operations=paint,
                image_draw_operations=images,actual_text_marked_content=actual_text)


def poppler_text(pdf,executable):
    if not executable: return None
    result=subprocess.run([str(executable),"-enc","UTF-8",str(pdf),"-"],capture_output=True,check=True)
    text=result.stdout.decode("utf-8")
    return dict(content_characters=len(text.replace("\f","").strip()),
                page_separators=text.count("\f"))


def audit(pdf,executable=None):
    reader=PdfReader(pdf)
    catalog=reader.trailer["/Root"]
    pages=[]
    with fitz.open(pdf) as doc,pdfplumber.open(pdf) as plumber:
        for number,(page,native,plumb) in enumerate(zip(reader.pages,doc,plumber.pages),1):
            resources=page.get("/Resources",{}).get_object()
            streams=stream_audit(page.get_contents(),resources,reader)
            placements=native.get_image_info()
            width,height=float(native.rect.width),float(native.rect.height)
            coverage=0.0
            if len(placements)==1:
                a,b,c,d=placements[0]["bbox"]
                coverage=max(0,min(width,c)-max(0,a))*max(0,min(height,d)-max(0,b))/(width*height)
            full_page=bool(len(placements)==1 and coverage>=.995)
            page_result=dict(page_number=number,pypdf_text_chars=len(page.extract_text().strip()),
                pymupdf_text_chars=len(native.get_text().strip()),pdfplumber_character_count=len(plumb.chars),
                font_resource_count=len(resolved(resources.get("/Font",{}))),annotations=len(resolved(page.get("/Annots",[]))),
                full_page_single_image=full_page,page_image_coverage=coverage,
                image_dimensions=[dict(width=i["width"],height=i["height"],bbox=list(i["bbox"])) for i in placements],
                **streams)
            page_result["image_only"]=bool(full_page and streams["text_show_operations"]==0 and
                streams["vector_paint_operations"]==0 and not streams["actual_text_marked_content"] and
                page_result["pypdf_text_chars"]==page_result["pymupdf_text_chars"]==page_result["pdfplumber_character_count"]==0 and
                page_result["annotations"]==0)
            pages.append(page_result)
    result=dict(file=pdf.name,sha256=sha256(pdf),page_count=len(pages),encrypted=reader.is_encrypted,
                has_structure_tree="/StructTreeRoot" in catalog,has_acroform="/AcroForm" in catalog,
                poppler=poppler_text(pdf,executable),pages=pages,
                image_only=all(p["image_only"] for p in pages),
                font_note="ReportLab adds an unused Helvetica resource and empty BT/Tf/TL/ET setup. These contain no text-show operations or character content.")
    if result["poppler"] is not None:
        result["image_only"]&=result["poppler"]["content_characters"]==0
    return result


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--poppler",type=Path)
    args=ap.parse_args()
    executable=args.poppler or shutil.which("pdftotext")
    if not executable:
        executable=next((ROOT/"tmp/poppler").rglob("pdftotext.exe"),None)
    results=[audit(OUT/name,executable) for name in ("sop_scan_clean.pdf","sop_scan_degraded.pdf")]
    manifest=json.loads((OUT/"manifest.json").read_text(encoding="utf-8"))
    hashes={f["file"]:f["sha256"] for f in manifest["fixtures"]}
    for result in results:
        result["matches_fixture_manifest"]=result["sha256"]==hashes[result["file"]]
        benchmark=ROOT/"output/benchmark/runs"
        statuses=list(benchmark.glob(f"*/baseline/{Path(result['file']).stem}/page_*/status.json"))
        result["benchmark_source_hashes_match"]=all(json.loads(p.read_text(encoding="utf-8"))["pdf_sha256"]==result["sha256"] for p in statuses) if statuses else None
        assert result["image_only"],f"Unexpected selectable native content in {result['file']}"
        assert result["matches_fixture_manifest"]
    # Negative controls: confirm the audit really detects native text and mixed pages.
    digital=audit(OUT/"sop_digital.pdf",executable)
    hybrid=audit(OUT/"sop_hybrid.pdf",executable)
    assert not digital["image_only"] and all(p["text_show_operations"]>0 for p in digital["pages"])
    assert [p["image_only"] for p in hybrid["pages"]]==[False,True,False,False]
    report=dict(scope="PDF file contents, not viewer-generated OCR",files=results,
        controls=dict(digital_detected_as_native=not digital["image_only"],
                      hybrid_image_only_pages=[p["page_number"] for p in hybrid["pages"] if p["image_only"]]),
        poppler_available=bool(executable),pdfs_modified=False,
        conclusion="Both scan fixtures are image-only. Viewer OCR can make text selectable without adding native text to the source PDF.")
    (OUT/"scan_audit.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(dict(files=[dict(file=r["file"],image_only=r["image_only"],pages=r["page_count"],
        text_show_operations=sum(p["text_show_operations"] for p in r["pages"]),
        extracted_characters=sum(p["pymupdf_text_chars"] for p in r["pages"]),
        manifest_hash_matches=r["matches_fixture_manifest"],benchmark_hash_matches=r["benchmark_source_hashes_match"]) for r in results],
        controls=report["controls"],pdfs_modified=False),ensure_ascii=False,indent=2))


if __name__=="__main__": main()
