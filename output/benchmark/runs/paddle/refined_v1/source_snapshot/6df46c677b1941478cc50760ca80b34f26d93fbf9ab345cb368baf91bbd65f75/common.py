"""Shared evidence format for the experiment; not a downstream product schema."""
from __future__ import annotations
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import threading
import time

ROOT=Path(__file__).resolve().parents[1]
FIXTURES=ROOT/"output/pdf"
BENCHMARK=ROOT/"output/benchmark"


def write_json(path, data):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+".tmp")
    temp.write_text(json.dumps(data,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
    temp.replace(path)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def configure_cache():
    cache=ROOT/".cache"
    for key,child in {"HF_HOME":"huggingface","TORCH_HOME":"torch",
                      "EASYOCR_MODULE_PATH":"easyocr",
                      "PADDLE_PDX_CACHE_HOME":"paddlex","PADDLE_HOME":"paddle",
                      "MPLCONFIGDIR":"matplotlib"}.items():
        os.environ.setdefault(key,str(cache/child))
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING","1")
    os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT","120")
    os.environ.setdefault("HF_HUB_ETAG_TIMEOUT","30")
    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK","True")
    os.environ.setdefault("OMP_NUM_THREADS","4")


def environment():
    import psutil
    packages={}
    for name in ["docling","docling-core","docling-ibm-models","easyocr","torch","torchvision",
                 "paddleocr","paddlex","paddlepaddle","numpy","transformers","pymupdf"]:
        try: packages[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError: pass
    return dict(python=platform.python_version(),platform=platform.platform(),
                cpu=platform.processor(),logical_cpus=os.cpu_count(),ram_bytes=psutil.virtual_memory().total,packages=packages)


class MemorySampler:
    """Approximate process-tree resident memory, sampled every 200 ms; not VRAM."""
    def __enter__(self):
        self.peak=0; self.stop=threading.Event()
        def sample():
            import psutil
            proc=psutil.Process()
            while not self.stop.is_set():
                try:
                    processes=[proc]+proc.children(recursive=True)
                    self.peak=max(self.peak,sum(p.memory_info().rss for p in processes if p.is_running()))
                except psutil.Error: pass
                self.stop.wait(.2)
        self.thread=threading.Thread(target=sample,daemon=True); self.thread.start()
        return self
    def __exit__(self,*args):
        self.stop.set(); self.thread.join()


def box(value,width,height):
    """Docling bbox -> canonical unrotated top-left PDF points."""
    if value is None: return None
    if hasattr(value,"model_dump"): value=value.model_dump(mode="json")
    if isinstance(value,dict):
        l,t,r,b=[float(value[k]) for k in ("l","t","r","b")]
        if "BOTTOMLEFT" in str(value.get("coord_origin","")).upper().replace("_",""):
            t,b=height-t,height-b
        return [min(l,r),min(t,b),max(l,r),max(t,b)]
    return [float(v) for v in value]


def area(b): return max(0,b[2]-b[0])*max(0,b[3]-b[1])
def intersection(a,b): return area([max(a[0],b[0]),max(a[1],b[1]),min(a[2],b[2]),min(a[3],b[3])])
def iou(a,b):
    overlap=intersection(a,b)
    return overlap/max(1e-9,area(a)+area(b)-overlap)


def render_input(pdf,page_number):
    import fitz
    destination=BENCHMARK/"inputs"/pdf.stem/f"page_{page_number:03}.png"
    meta=destination.with_suffix(".json")
    source_hash=sha256(pdf)
    if destination.exists() and meta.exists() and read_json(meta).get("pdf_sha256")==source_hash:
        return destination,read_json(meta)
    destination.parent.mkdir(parents=True,exist_ok=True)
    with fitz.open(pdf) as doc:
        p=doc[page_number-1]
        if p.rotation:
            raise ValueError("This experiment currently expects unrotated fixture pages")
        pix=p.get_pixmap(dpi=200,alpha=False); pix.save(destination)
        info=dict(pdf_sha256=source_hash,page_number=page_number,width=p.rect.width,height=p.rect.height,
                  pixel_width=pix.width,pixel_height=pix.height,dpi=200,rotation=p.rotation)
    write_json(meta,info)
    return destination,info


def export_evidence(evidence,image_path,directory):
    from PIL import Image,ImageDraw
    image=Image.open(image_path).convert("RGB")
    sx,sy=image.width/evidence["width"],image.height/evidence["height"]
    overlay=image.copy(); draw=ImageDraw.Draw(overlay)
    colors={"text":"#1683C5","heading":"#1683C5","table":"#D62F2F","figure":"#B72AC6"}
    crops=[]
    for i,block in enumerate(evidence["blocks"]):
        b=block.get("bbox")
        if not b: continue
        coords=[b[0]*sx,b[1]*sy,b[2]*sx,b[3]*sy]
        color=colors.get(block["type"],"#64748B")
        draw.rectangle(coords,outline=color,width=3)
        draw.text((coords[0]+2,max(0,coords[1]-12)),f"{i}:{block['label']}",fill=color)
        if block["type"] in ("figure","table"):
            clipped=[max(0,round(coords[0])),max(0,round(coords[1])),min(image.width,round(coords[2])),min(image.height,round(coords[3]))]
            if clipped[2]>clipped[0] and clipped[3]>clipped[1]:
                name=f"crop_{i:03}_{block['type']}.png"
                image.crop(clipped).save(directory/name)
                crops.append(dict(block_id=block["id"],file=name,bbox=b,type=block["type"]))
    overlay.save(directory/"overlay.png")
    cells=image.copy(); draw=ImageDraw.Draw(cells)
    for table in evidence["tables"]:
        if table.get("cell_box_alignment")=="unresolved":
            for index,cell_box in enumerate(table.get("raw_cell_boxes",[])):
                a,b,c,d=cell_box
                draw.rectangle([a*sx,b*sy,c*sx,d*sy],outline="#D99A00",width=2)
                draw.text((a*sx+2,b*sy+2),f"raw {index}",fill="#9C3D00")
        for cell in table["cells"]:
            if cell.get("bbox"):
                a,b,c,d=cell["bbox"]
                draw.rectangle([a*sx,b*sy,c*sx,d*sy],outline="#D99A00",width=2)
                draw.text((a*sx+2,b*sy+2),f"{cell.get('row','?')},{cell.get('col','?')}",fill="#9C3D00")
    cells.save(directory/"cells_overlay.png")
    write_json(directory/"crops.json",crops)
