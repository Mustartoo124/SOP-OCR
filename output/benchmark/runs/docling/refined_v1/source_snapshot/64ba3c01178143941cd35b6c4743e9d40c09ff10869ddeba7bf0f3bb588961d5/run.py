"""Run independent parser baselines, retaining raw output and reproducible evidence."""
from __future__ import annotations
import argparse
import hashlib
import json
import logging
import os
from pathlib import Path
import sys
import time
import traceback
import zipfile
import warnings

from common import ROOT,FIXTURES,BENCHMARK,configure_cache,environment,sha256,write_json,read_json,render_input,export_evidence,MemorySampler


def main():
    runner_start=time.perf_counter()
    ap=argparse.ArgumentParser()
    ap.add_argument("--engine",choices=["docling","paddle"],required=True)
    ap.add_argument("--fixtures",nargs="*",default=["sop_digital","sop_scan_clean","sop_scan_degraded","sop_hybrid"])
    ap.add_argument("--pages",nargs="*",type=int,default=[1,2,3,4])
    ap.add_argument("--device",default="cpu")
    ap.add_argument("--threads",type=int,default=4)
    ap.add_argument("--profile",choices=["baseline","refined"],default="baseline")
    ap.add_argument("--run-name")
    ap.add_argument("--offline",action="store_true")
    ap.add_argument("--resume",action="store_true")
    ap.add_argument("--download-only",action="store_true")
    ap.add_argument("--prefetch-easyocr",action="store_true")
    args=ap.parse_args()
    args.run_name=args.run_name or ("refined_v1" if args.profile=="refined" else "baseline")
    if args.offline:
        os.environ["HF_HUB_OFFLINE"]="1"
        os.environ["TRANSFORMERS_OFFLINE"]="1"
    configure_cache()
    os.environ["OMP_NUM_THREADS"]=str(args.threads)
    if args.prefetch_easyocr:
        from prefetch_easyocr import prefetch
        prefetch()
        return
    run=BENCHMARK/"runs"/args.engine/args.run_name
    run.mkdir(parents=True,exist_ok=True)
    metadata=dict(engine=args.engine,profile=args.profile,device=args.device,threads=args.threads,offline=args.offline,environment=environment(),
        scope="independent baseline" if args.profile=="baseline" else "parser plus geometry refinement, native image/text recovery, nested figures",
        timing_policy="v2: page seconds include input preparation, parser/raw export, refinement, and evidence/crop export; startup separate",
        renderer_dpi=200,runner_sha256=sha256(__file__),adapter_sha256=sha256(Path(__file__).with_name("adapters.py")),
        common_sha256=sha256(Path(__file__).with_name("common.py")))
    source_files=["run.py","adapters.py","common.py"]
    if args.profile=="refined":
        metadata["refinement_sha256"]=sha256(Path(__file__).with_name("refinement.py"));source_files.append("refinement.py")
    for filename in source_files:
        source=Path(__file__).with_name(filename)
        snapshot=run/"source_snapshot"/sha256(source)/filename
        snapshot.parent.mkdir(parents=True,exist_ok=True)
        if not snapshot.exists(): snapshot.write_bytes(source.read_bytes())
    write_json(run/"environment.json",metadata)
    from adapters import DoclingAdapter,PaddleAdapter
    start=time.perf_counter()
    try:
        with MemorySampler() as memory:
            adapter=(DoclingAdapter if args.engine=="docling" else PaddleAdapter)(args.device,args.threads,args.profile)
    except Exception as exc:
        write_json(run/"initialization.json",dict(state="failed",seconds=time.perf_counter()-start,
            error=f"{type(exc).__name__}: {exc}",traceback=traceback.format_exc()))
        raise
    write_json(run/"initialization.json",dict(state="success",seconds=time.perf_counter()-start,peak_rss_bytes=memory.peak,
               includes_downloads_if_missing=True))
    write_json(run/"config.json",adapter.config)
    if hasattr(adapter,"pipeline") and hasattr(adapter.pipeline,"export_paddlex_config_to_yaml"):
        adapter.pipeline.export_paddlex_config_to_yaml(str(run/"effective_paddlex_config.yaml"))
    metadata["config"]=adapter.config
    fingerprint=hashlib.sha256(json.dumps(metadata,sort_keys=True).encode()).hexdigest()
    if args.download_only:
        print("Models initialized. No pages inferred.",flush=True); return
    failures=0
    finished=[];skipped=0
    for name in args.fixtures:
        pdf=FIXTURES/(name if name.endswith(".pdf") else name+".pdf")
        pdf_hash=sha256(pdf)
        for page_number in args.pages:
            destination=run/pdf.stem/f"page_{page_number:03}"
            destination.mkdir(parents=True,exist_ok=True)
            status_file=destination/"status.json"
            if args.resume and status_file.exists():
                previous=read_json(status_file)
                if previous.get("state")=="success" and previous.get("fingerprint")==fingerprint and previous.get("pdf_sha256")==pdf_hash:
                    skipped+=1
                    print(f"SKIP {args.engine} {pdf.stem} p{page_number}",flush=True); continue
            if status_file.exists():
                # Retain earlier evidence before a retry/config change; never report it as fresh output.
                archive=run/"history"/pdf.stem/f"page_{page_number:03}_{time.time_ns()}.zip"
                archive.parent.mkdir(parents=True,exist_ok=True)
                with zipfile.ZipFile(archive,"w",zipfile.ZIP_DEFLATED) as zipped:
                    for old in destination.iterdir():
                        if old.is_file(): zipped.write(old,old.name)
            status=dict(engine=args.engine,pdf=pdf.name,pdf_sha256=pdf_hash,page_number=page_number,
                        fingerprint=fingerprint,state="running")
            write_json(status_file,status)
            print(f"RUN {args.engine} {pdf.stem} p{page_number}",flush=True)
            start=time.perf_counter()
            try:
                phase={}
                handler=logging.FileHandler(destination/"parser.log",mode="w",encoding="utf-8")
                handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
                logging.getLogger().addHandler(handler)
                try:
                    with warnings.catch_warnings(record=True) as captured,MemorySampler() as memory:
                        warnings.simplefilter("always")
                        tick=time.perf_counter()
                        image_path,info=render_input(pdf,page_number)
                        phase["input_preparation"]=time.perf_counter()-tick
                        tick=time.perf_counter()
                        evidence=adapter.extract(pdf,page_number,image_path,info,destination)
                        phase["parser_and_raw_export"]=time.perf_counter()-tick
                        tick=time.perf_counter()
                        if args.profile=="refined":
                            from refinement import refine
                            evidence=refine(pdf,page_number,image_path,evidence,destination)
                        phase["refinement_and_debug_export"]=time.perf_counter()-tick
                        evidence["runtime_warnings"]=[str(w.message) for w in captured]
                        evidence.update(engine=args.engine,profile=args.profile,page_number=page_number,pdf=pdf.name,pdf_sha256=pdf_hash,
                            coordinate_system="pdf_points_top_left_unrotated")
                        tick=time.perf_counter()
                        write_json(destination/"evidence.json",evidence)
                        export_evidence(evidence,image_path,destination)
                        phase["evidence_and_crop_export"]=time.perf_counter()-tick
                finally:
                    logging.getLogger().removeHandler(handler); handler.close()
                elapsed=time.perf_counter()-start
                status.update(state="success",seconds=elapsed,phase_seconds=phase,peak_rss_bytes=memory.peak,
                              block_count=len(evidence["blocks"]),table_count=len(evidence["tables"]))
                print(f"OK {args.engine} {pdf.stem} p{page_number}: {elapsed:.1f}s, {len(evidence['blocks'])} blocks, {len(evidence['tables'])} tables",flush=True)
            except Exception as exc:
                failures+=1
                status.update(state="failed",seconds=time.perf_counter()-start,error=f"{type(exc).__name__}: {exc}")
                (destination/"error.log").write_text(traceback.format_exc(),encoding="utf-8")
                print(f"FAILED {args.engine} {pdf.stem} p{page_number}: {exc}",flush=True)
            write_json(status_file,status)
            finished.append(status)
    write_json(run/"execution.json",dict(engine=args.engine,profile=args.profile,runner_elapsed_seconds=time.perf_counter()-runner_start,
        processed_pages=len(finished),skipped_pages=skipped,failed_pages=failures,page_seconds=sum(s["seconds"] for s in finished),
        phase_seconds={key:sum(s.get("phase_seconds",{}).get(key,0) for s in finished) for key in
            ("input_preparation","parser_and_raw_export","refinement_and_debug_export","evidence_and_crop_export")},
        model_downloads_allowed=not args.offline))
    if failures: sys.exit(1)


if __name__=="__main__": main()
