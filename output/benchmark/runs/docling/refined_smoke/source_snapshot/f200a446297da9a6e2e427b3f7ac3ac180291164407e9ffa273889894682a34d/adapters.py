"""Parser adapters. Inference code intentionally does not load fixture annotations."""
from __future__ import annotations
from pathlib import Path
import html
from html.parser import HTMLParser
import json

from common import ROOT,box,iou,write_json


class DoclingAdapter:
    def __init__(self,device="cpu",threads=4,profile="baseline"):
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions,EasyOcrOptions,TableFormerMode
        from docling.datamodel.accelerator_options import AcceleratorOptions
        from docling.document_converter import DocumentConverter,PdfFormatOption
        options=PdfPipelineOptions()
        options.accelerator_options=AcceleratorOptions(device=device,num_threads=threads)
        options.do_ocr=True
        options.ocr_options=EasyOcrOptions(lang=["vi","en"],
            model_storage_directory=str(ROOT/".cache/easyocr"),force_full_page_ocr=False)
        options.do_table_structure=True
        options.table_structure_options.mode=TableFormerMode.ACCURATE
        options.generate_page_images=True
        options.generate_picture_images=True
        options.images_scale=2.0
        options.generate_parsed_pages=profile=="refined"
        self.profile=profile
        self.config=options.model_dump(mode="json")
        self.converter=DocumentConverter(format_options={InputFormat.PDF:PdfFormatOption(pipeline_options=options)})
        self.converter.initialize_pipeline(InputFormat.PDF)

    def extract(self,pdf,page_number,image_path,info,destination):
        result=self.converter.convert(pdf,page_range=(page_number,page_number),raises_on_error=True)
        doc=result.document
        raw=doc.export_to_dict()
        write_json(destination/"raw_document.json",raw)
        (destination/"document.md").write_text(doc.export_to_markdown(),encoding="utf-8")
        width,height=info["width"],info["height"]
        out=dict(width=width,height=height,blocks=[],texts=[],tables=[],containers=[],
                 status=str(result.status),errors=[str(e) for e in result.errors])
        if self.profile=="refined":
            out["tokens"]=[]
            raw_tokens=[]
            for page in result.pages:
                for index,cell in enumerate(page.cells):
                    raw_tokens.append(cell.model_dump(mode="json"))
                    out["tokens"].append(dict(id=f"pipeline_{index}",bbox=box(cell.rect.to_bounding_box(),width,height),
                        text=cell.text,from_ocr=cell.from_ocr,confidence=cell.confidence,
                        source="docling_parsed_page",quad=cell.rect.model_dump(mode="json")))
            write_json(destination/"raw_page_tokens.json",raw_tokens)
        for item in doc.groups:
            out["containers"].append(dict(id=item.self_ref,type="container",label=str(item.label),
                parent_ref=item.parent.cref if item.parent else None,child_refs=[c.cref for c in item.children]))
        def provenance(item):
            entries=[p for p in item.prov if p.page_no==page_number]
            return box(entries[0].bbox,width,height) if entries else None
        for item in doc.texts:
            b=provenance(item)
            label=str(getattr(item.label,"value",item.label))
            block=dict(id=item.self_ref,type="heading" if "header" in label or label=="title" else "text",
                       label=label,bbox=b,text=item.text,
                       parent_ref=item.parent.cref if item.parent else None,
                       child_refs=[c.cref for c in item.children])
            out["blocks"].append(block)
            if b: out["texts"].append(dict(bbox=b,text=item.text,source_ref=item.self_ref))
        for item in doc.pictures:
            out["blocks"].append(dict(id=item.self_ref,type="figure",label="picture",bbox=provenance(item),
                parent_ref=item.parent.cref if item.parent else None,child_refs=[c.cref for c in item.children]))
        for n,item in enumerate(doc.tables):
            b=provenance(item)
            cells=[]
            for cell in item.data.table_cells:
                cb=box(cell.bbox,width,height) if cell.bbox else None
                cells.append(dict(row=cell.start_row_offset_idx,col=cell.start_col_offset_idx,
                    rowspan=cell.row_span,colspan=cell.col_span,text=cell.text,bbox=cb,
                    column_header=cell.column_header))
                if cb and cell.text:
                    out["texts"].append(dict(bbox=cb,text=cell.text,source_ref=item.self_ref,source="table_cell"))
            table=dict(id=item.self_ref,bbox=b,rows=item.data.num_rows,cols=item.data.num_cols,cells=cells,
                       parent_ref=item.parent.cref if item.parent else None)
            out["tables"].append(table)
            out["blocks"].append(dict(id=item.self_ref,type="table",label="table",bbox=b,parent_ref=table["parent_ref"]))
            markup=item.export_to_html(doc=doc)
            prefix="parser_table" if self.profile=="refined" else "table"
            (destination/f"{prefix}_{n:02}.html").write_text(markup,encoding="utf-8")
        return out


class CellHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.cells=[]; self.row=-1; self.col=0; self.occupied=set(); self.current=None
    def handle_starttag(self,tag,attrs):
        if tag=="tr": self.row+=1; self.col=0
        if tag in ("td","th"):
            attrs=dict(attrs)
            while (self.row,self.col) in self.occupied: self.col+=1
            rs,cs=int(attrs.get("rowspan",1)),int(attrs.get("colspan",1))
            self.current=dict(row=self.row,col=self.col,rowspan=rs,colspan=cs,text="",column_header=tag=="th")
            for r in range(self.row,self.row+rs):
                for c in range(self.col,self.col+cs): self.occupied.add((r,c))
            self.col+=cs
        if tag=="br" and self.current is not None: self.current["text"]+="\n"
    def handle_data(self,data):
        if self.current is not None: self.current["text"]+=data
    def handle_endtag(self,tag):
        if tag in ("td","th") and self.current is not None:
            self.cells.append(self.current); self.current=None


class PaddleAdapter:
    def __init__(self,device="cpu",threads=4,profile="baseline"):
        from paddleocr import PPStructureV3
        self.config=dict(device=device,cpu_threads=threads,lang="vi",ocr_version="PP-OCRv3",
            use_doc_orientation_classify=False,use_doc_unwarping=False,use_textline_orientation=True,
            use_table_recognition=True,use_formula_recognition=False,use_seal_recognition=False,
            use_chart_recognition=False,enable_mkldnn=False)
        self.pipeline=PPStructureV3(**self.config)
        self.profile=profile
        self.prediction_options=dict(use_wired_table_cells_trans_to_html=True,
            use_wireless_table_cells_trans_to_html=True) if profile=="refined" else {}
        self.config["prediction_options"]=self.prediction_options

    def extract(self,pdf,page_number,image_path,info,destination):
        import numpy as np
        result=next(iter(self.pipeline.predict(str(image_path),**self.prediction_options)))
        result.save_to_json(str(destination/"raw_paddle.json"))
        raw=json.loads((destination/"raw_paddle.json").read_text(encoding="utf-8"))
        raw=raw.get("res",raw)
        width,height=info["width"],info["height"]
        sx,sy=width/info["pixel_width"],height/info["pixel_height"]
        def convert(b):
            a=np.asarray(b,dtype=float)
            if a.size==4:
                a=a.reshape(-1); return [float(a[0]*sx),float(a[1]*sy),float(a[2]*sx),float(a[3]*sy)]
            a=a.reshape(-1,2)
            return [float(a[:,0].min()*sx),float(a[:,1].min()*sy),float(a[:,0].max()*sx),float(a[:,1].max()*sy)]
        out=dict(width=width,height=height,blocks=[],texts=[],tables=[],containers=[],status="success",errors=[])
        for n,block in enumerate(raw.get("parsing_res_list",[])):
            label=block["block_label"]
            kind="table" if label=="table" else "figure" if label in ("image","chart","figure","header_image","footer_image") else "text"
            out["blocks"].append(dict(id=f"block_{n}",type=kind,label=label,bbox=convert(block["block_bbox"]),
                text=block.get("block_content",""),parent_ref=None,child_refs=[]))
        ocr=raw.get("overall_ocr_res",{})
        polygons=ocr.get("rec_polys",ocr.get("dt_polys",[]))
        for n,(poly,text) in enumerate(zip(polygons,ocr.get("rec_texts",[]))):
            out["texts"].append(dict(bbox=convert(poly),text=text,source_ref=f"ocr_{n}"))
        out["tokens"]=[dict(t,from_ocr=True,source="paddle_overall_ocr",
            confidence=ocr.get("rec_scores",[None]*len(out["texts"]))[i]) for i,t in enumerate(out["texts"])]
        for n,t in enumerate(raw.get("table_res_list",[])):
            markup=t.get("pred_html","")
            parser=CellHTMLParser(); parser.feed(markup)
            cells=parser.cells
            boxes=t.get("cell_box_list",[])
            # Order association is only used when the parser returns one box per HTML cell.
            aligned=len(boxes)==len(cells)
            for i,cell in enumerate(cells):
                cell["bbox"]=convert(boxes[i]) if aligned else None
            table_box=t.get("table_bbox")
            if table_box is None and boxes:
                cb=[convert(b) for b in boxes]
                table_box_points=[min(b[0] for b in cb),min(b[1] for b in cb),max(b[2] for b in cb),max(b[3] for b in cb)]
            else: table_box_points=convert(table_box) if table_box is not None else None
            candidates=[b for b in out["blocks"] if b["type"]=="table"]
            match=max(candidates,key=lambda b:iou(table_box_points,b["bbox"]),default=None) if table_box_points else (candidates[n] if n<len(candidates) else None)
            table=dict(id=match["id"] if match else f"table_{n}",bbox=match["bbox"] if match else table_box_points,
                rows=max((c["row"]+c["rowspan"] for c in cells),default=0),
                cols=max((c["col"]+c["colspan"] for c in cells),default=0),cells=cells,
                cell_box_count=len(boxes),cell_box_alignment="ordered_1_to_1" if aligned else "unresolved",
                raw_cell_boxes=[convert(b) for b in boxes],parent_ref=None)
            out["tables"].append(table)
            prefix="parser_table" if self.profile=="refined" else "table"
            (destination/f"{prefix}_{n:02}.html").write_text(markup,encoding="utf-8")
        return out
