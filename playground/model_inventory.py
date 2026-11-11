"""Record local model/config file hashes, without copying weights into the report."""
from pathlib import Path
from common import ROOT,BENCHMARK,sha256,write_json

suffixes={".pth",".pt",".onnx",".safetensors",".bin",".pdiparams",".pdmodel",".json",".yaml",".yml"}
cache=ROOT/".cache"
files=[]
for directory in (cache/"easyocr",cache/"paddlex/official_models",cache/"huggingface/hub"):
    if not directory.exists(): continue
    for path in sorted(directory.rglob("*")):
        if path.is_file() and path.suffix.lower() in suffixes and "xet" not in path.parts:
            files.append(dict(path=path.relative_to(ROOT).as_posix(),bytes=path.stat().st_size,sha256=sha256(path)))
write_json(BENCHMARK/"model_inventory.json",dict(files=files,weights_included=False))
print(f"Recorded {len(files)} model/config files")
