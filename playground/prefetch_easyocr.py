"""Download official EasyOCR assets with resumable, buffered HTTP and weight MD5 checks."""
from pathlib import Path
import hashlib
import importlib.util
import runpy
import time
import zipfile

import requests
from common import ROOT


def prefetch():
    specification=importlib.util.find_spec("easyocr")
    config=runpy.run_path(str(Path(specification.origin).with_name("config.py")))
    models=[config["detection_models"]["craft"],config["recognition_models"]["gen2"]["latin_g2"]]
    directory=ROOT/".cache/easyocr"; directory.mkdir(parents=True,exist_ok=True)
    for model in models:
        target=directory/model["filename"]
        expected=model["md5sum"]
        if target.exists() and hashlib.md5(target.read_bytes()).hexdigest()==expected:
            print(f"VERIFIED {target.name}",flush=True); continue
        partial=directory/(model["filename"]+".zip.part")
        # EasyOCR's interrupted craft download is from this exact official asset URL.
        old=directory/"temp.zip"
        if model["filename"].startswith("craft") and old.exists() and not partial.exists():
            partial.write_bytes(old.read_bytes())
        for attempt in range(3):
            try:
                offset=partial.stat().st_size if partial.exists() else 0
                headers={"User-Agent":"SOP-OCR-Playground/1.0"}
                if offset: headers["Range"]=f"bytes={offset}-"
                with requests.get(model["url"],headers=headers,stream=True,timeout=(30,120)) as response:
                    response.raise_for_status()
                    resumed=response.status_code==206
                    if resumed and not response.headers.get("Content-Range","").startswith(f"bytes {offset}-"):
                        raise RuntimeError("Unexpected Content-Range")
                    mode="ab" if resumed else "wb"
                    received=offset if resumed else 0
                    print(f"DOWNLOAD {target.name} offset={received} official={model['url']}",flush=True)
                    checkpoint=received
                    with partial.open(mode) as output:
                        for chunk in response.iter_content(chunk_size=1024*1024):
                            if chunk:
                                output.write(chunk); received+=len(chunk)
                                if received-checkpoint>=5*1024*1024:
                                    print(f"{target.name}: {received/1e6:.1f} MB",flush=True); checkpoint=received
                with zipfile.ZipFile(partial) as zipped:
                    member=next(m for m in zipped.infolist() if Path(m.filename).name==target.name)
                    weight=zipped.read(member)
                if hashlib.md5(weight).hexdigest()!=expected: raise RuntimeError("Official weight MD5 mismatch")
                temporary=target.with_suffix(target.suffix+".part")
                temporary.write_bytes(weight); temporary.replace(target)
                print(f"VERIFIED {target.name} MD5={expected}",flush=True)
                break
            except Exception as exc:
                print(f"Attempt {attempt+1}: {type(exc).__name__}: {exc}",flush=True)
                if attempt==2: raise
                time.sleep(2)


if __name__=="__main__": prefetch()
