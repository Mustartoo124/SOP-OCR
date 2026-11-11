"""Validate completed evidence and package current artifacts, excluding stale retries/models."""
from pathlib import Path
import json
import zipfile
import argparse
from html.parser import HTMLParser
from urllib.parse import unquote,urlsplit
from common import ROOT,BENCHMARK,FIXTURES,read_json,write_json,sha256


class LinkCollector(HTMLParser):
    def __init__(self): super().__init__(); self.links=[]
    def handle_starttag(self,tag,attrs):
        for key,value in attrs:
            if key in ("href","src") and value and not urlsplit(value).scheme and not value.startswith("#"):
                self.links.append(unquote(urlsplit(value).path))


def package(run_name="baseline"):
    report_directory=BENCHMARK if run_name=="baseline" else BENCHMARK/"experiments"/run_name
    evaluation=read_json(report_directory/"evaluation.json")
    assert len(evaluation["pages"])==32,"Expected 16 pages for each of two engines"
    assert all(r["state"]=="success" for r in evaluation["pages"]),"Inference is incomplete"
    selected=set()
    for engine in ("docling","paddle"):
        run=BENCHMARK/"runs"/engine/run_name
        statuses=[read_json(p) for p in run.glob("sop_*/page_*/status.json")]
        assert len(statuses)==16 and all(s["state"]=="success" for s in statuses)
        assert len({s["fingerprint"] for s in statuses})==1,"Mixed inference configurations"
        metadata=read_json(run/"environment.json")
        for name,key in [("run.py","runner_sha256"),("adapters.py","adapter_sha256"),("common.py","common_sha256")]:
            snapshot=run/"source_snapshot"/metadata[key]/name
            assert sha256(snapshot)==metadata[key],"Inference source snapshot mismatch"
            selected.add(snapshot)
        if "refinement_sha256" in metadata:
            snapshot=run/"source_snapshot"/metadata["refinement_sha256"]/"refinement.py"
            assert sha256(snapshot)==metadata["refinement_sha256"];selected.add(snapshot)
        for name in ("environment.json","initialization.json","config.json","effective_paddlex_config.yaml","execution.json"):
            path=run/name
            if path.exists(): selected.add(path)
        for s in statuses:
            pdf=FIXTURES/s["pdf"]
            assert sha256(pdf)==s["pdf_sha256"]
            directory=run/pdf.stem/f"page_{s['page_number']:03}"
            evidence=read_json(directory/"evidence.json")
            assert evidence["pdf_sha256"]==s["pdf_sha256"]
            names=["status.json","evidence.json","evaluation.json","overlay.png","cells_overlay.png","parser.log","crops.json"]
            names += ["raw_document.json","document.md"] if engine=="docling" else ["raw_paddle.json"]
            if run_name!="baseline":
                names += ["parser_evidence.json","geometry_candidates.json","grid_mask.png","diagram_working_mask.png", "token_ownership.json","suppressed_duplicates.json"]
                if engine=="docling":names.append("raw_page_tokens.json")
                parser_evidence=read_json(directory/"parser_evidence.json")
                names += [f"parser_table_{i:02}.html" for i in range(len(parser_evidence["tables"]))]
            for i in range(len(evidence["tables"])):
                names += [f"table_{i:02}.html",f"table_{i:02}.view.html"]
            names += [c["file"] for c in read_json(directory/"crops.json")]
            records=[]
            for name in names:
                path=directory/name
                assert path.exists(),f"Missing current artifact: {path}"
                records.append(dict(file=name,bytes=path.stat().st_size,sha256=sha256(path)))
                selected.add(path)
            manifest=directory/"page_manifest.json"
            write_json(manifest,dict(engine=engine,pdf=s["pdf"],page=s["page_number"],
                inference_fingerprint=s["fingerprint"],artifacts=records,
                note="Only listed artifacts belong to the current successful attempt; archived retries are not exported"))
            selected.add(manifest)
    for directory in (FIXTURES,BENCHMARK/"inputs",ROOT/"playground",ROOT/"scripts"):
        for path in directory.rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts:
                if directory in (ROOT/"playground",ROOT/"scripts") and path.suffix not in (".py",".md",".txt"): continue
                selected.add(path)
    for name in ("index.html","evaluation.json","REPORT.md"):
        path=report_directory/name
        assert path.exists(),f"Missing report artifact: {path}"
        selected.add(path)
    selected.add(BENCHMARK/"model_inventory.json")
    if run_name!="baseline":
        for name in ("timing.json","comparison.json","docling.console.log","paddle.console.log"):
            path=report_directory/name
            assert path.exists();selected.add(path)
    selected.add(ROOT/"requirements-fixtures.txt")
    resolved_selected={p.resolve() for p in selected}
    for path in list(selected):
        if path.suffix==".html":
            parser=LinkCollector(); parser.feed(path.read_text(encoding="utf-8"))
            for link in parser.links:
                target=(path.parent/link).resolve()
                assert target.is_file(),f"Broken report link: {path} -> {link}"
                assert target in resolved_selected,f"Report link missing from package: {target}"
    records=[dict(file=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha256(p)) for p in sorted(selected)]
    manifest=report_directory/"package_manifest.json"
    write_json(manifest,dict(files=records,inference_pages=32,models_included=False,virtualenvs_included=False,
        archived_retries_included=False,entry_point=(report_directory/"index.html").relative_to(ROOT).as_posix()))
    selected.add(manifest)
    archive=ROOT/("output/sop_extraction_benchmark.zip" if run_name=="baseline" else f"output/sop_extraction_{run_name}.zip")
    with zipfile.ZipFile(archive,"w",zipfile.ZIP_DEFLATED) as zipped:
        for path in sorted(selected): zipped.write(path,path.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(archive) as zipped:
        assert zipped.testzip() is None
    print(json.dumps(dict(archive=str(archive),files=len(selected),bytes=archive.stat().st_size,sha256=sha256(archive)),indent=2))


if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument('--run-name',default='baseline')
    package(ap.parse_args().run_name)
