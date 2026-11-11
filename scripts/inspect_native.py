"""Inspect native PDF evidence without OCR, semantic models, or ground-truth access."""
import argparse
import hashlib
import json
from pathlib import Path

import fitz

ROOT=Path(__file__).resolve().parents[1]


def inspect(path, destination):
    doc=fitz.open(path)
    pages=[]
    for page in doc:
        words=page.get_text("words")
        tables=[]
        error=None
        try:
            for table in page.find_tables().tables:
                tables.append(dict(bbox=list(table.bbox),rows=table.row_count,cols=table.col_count,
                                   cells=[list(b) if b else None for b in table.cells],
                                   content=table.extract()))
        except Exception as exc:
            error=f"{type(exc).__name__}: {exc}"
        pages.append(dict(page_number=page.number+1,width=page.rect.width,height=page.rect.height,
                          native_text_chars=len(page.get_text().strip()),
                          words=[dict(bbox=list(w[:4]),text=w[4]) for w in words],
                          raster_occurrences=[dict(bbox=list(i["bbox"]),width=i["width"],height=i["height"])
                                              for i in page.get_image_info()],
                          vector_path_count=len(page.get_drawings()),
                          geometry_table_candidates=tables,table_error=error))
    doc.close()
    output=dict(source=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                engine=f"PyMuPDF {fitz.VersionBind}",
                limitation="Native diagnostics only. No OCR, semantic layout, diagram detection, or accuracy measurement.",
                pages=pages)
    destination.mkdir(parents=True,exist_ok=True)
    (destination/f"{path.stem}.native.json").write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding="utf-8")
    return dict(file=path.name,pages=[dict(page=p["page_number"],native_chars=p["native_text_chars"],
        raster_occurrences=len(p["raster_occurrences"]),vector_paths=p["vector_path_count"],
        table_candidates=[f"{t['rows']}x{t['cols']}" for t in p["geometry_table_candidates"]],
        table_error=p["table_error"]) for p in pages])


if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("pdfs",nargs="*",type=Path)
    ap.add_argument("--output",type=Path,default=ROOT/"output/pdf/diagnostics")
    args=ap.parse_args()
    paths=args.pdfs or sorted((ROOT/"output/pdf").glob("sop_*.pdf"))
    summary=[inspect(p,args.output) for p in paths]
    (args.output/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2))
