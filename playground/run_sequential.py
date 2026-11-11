"""Run the measured CPU experiment sequentially; do not mix smoke/resume timings."""
import argparse
from datetime import datetime,timezone
from pathlib import Path
import subprocess
import time

from common import ROOT,BENCHMARK,read_json,write_json


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--run-name",default="refined_v1")
    ap.add_argument("--engines",nargs="+",choices=["docling","paddle"],default=["docling","paddle"])
    args=ap.parse_args()
    records=[]; start_all=time.perf_counter()
    output=BENCHMARK/"experiments"/args.run_name;output.mkdir(parents=True,exist_ok=True)
    for engine in args.engines:
        python=ROOT/f".venv-{engine}"/("Scripts/python.exe" if __import__('os').name=='nt' else "bin/python")
        command=[str(python),"-X","utf8",str(ROOT/"playground/run.py"),"--engine",engine,
            "--profile","refined","--run-name",args.run_name,"--offline","--threads","4"]
        log=output/f"{engine}.console.log"
        started=datetime.now(timezone.utc).isoformat();start=time.perf_counter()
        print(f"START sequential {engine}: {started}",flush=True)
        with log.open("w",encoding="utf-8") as stream:
            result=subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
        elapsed=time.perf_counter()-start
        record=dict(engine=engine,command=command,started_utc=started,process_wall_seconds=elapsed,
                    returncode=result.returncode,console_log=log.relative_to(BENCHMARK).as_posix())
        execution=BENCHMARK/f"runs/{engine}/{args.run_name}/execution.json"
        if execution.exists():record["execution"]=read_json(execution)
        init=execution.parent/"initialization.json"
        if init.exists():record["initialization"]=read_json(init)
        records.append(record)
        write_json(output/"timing.json",dict(run_name=args.run_name,sequential=True,offline=True,
            started_utc=records[0]["started_utc"],total_wall_seconds=time.perf_counter()-start_all,engines=records))
        print(f"END {engine}: {elapsed:.2f}s, exit={result.returncode}",flush=True)
        if result.returncode:raise SystemExit(result.returncode)
    print(f"TOTAL {time.perf_counter()-start_all:.2f}s",flush=True)


if __name__=="__main__":main()
