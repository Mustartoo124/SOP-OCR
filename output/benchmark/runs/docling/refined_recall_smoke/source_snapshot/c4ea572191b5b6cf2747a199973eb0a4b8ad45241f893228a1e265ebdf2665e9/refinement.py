"""Geometry-assisted extraction experiment. No fixture labels, names, or fixed ROIs."""
from __future__ import annotations
import copy
import html
import inspect
from pathlib import Path
import time

import cv2
import numpy as np
import pymupdf as fitz

from common import area,intersection,iou,write_json

VERSION="geometry-v1"


def union(boxes):
    return [min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes)]


def inside(b,container,tolerance=0):
    return b[0]>=container[0]-tolerance and b[1]>=container[1]-tolerance and b[2]<=container[2]+tolerance and b[3]<=container[3]+tolerance


def cluster(values,tolerance):
    groups=[]
    for value in sorted(values):
        if groups and value-np.mean(groups[-1])<=tolerance: groups[-1].append(value)
        else: groups.append([value])
    return [float(np.mean(g)) for g in groups]


def cell_grid(rectangles,tolerance=1.0):
    rectangles=list({tuple(round(v,3) for v in b) for b in rectangles if b and area(b)>1})
    if not rectangles: return None
    xs=cluster([b[k] for b in rectangles for k in (0,2)],tolerance)
    ys=cluster([b[k] for b in rectangles for k in (1,3)],tolerance)
    cells=[]; occupied=set()
    for b in rectangles:
        c0,c1=[min(range(len(xs)),key=lambda i:abs(xs[i]-b[k])) for k in (0,2)]
        r0,r1=[min(range(len(ys)),key=lambda i:abs(ys[i]-b[k])) for k in (1,3)]
        if c0==c1 or r0==r1: return None
        slots={(r,c) for r in range(r0,r1) for c in range(c0,c1)}
        if slots&occupied:return None
        occupied|=slots
        cells.append(dict(row=r0,col=c0,rowspan=r1-r0,colspan=c1-c0,bbox=list(b),text=""))
    if len(occupied)!=(len(xs)-1)*(len(ys)-1): return None
    return dict(rows=len(ys)-1,cols=len(xs)-1,cells=sorted(cells,key=lambda c:(c["row"],c["col"])),xs=xs,ys=ys,grid_valid=True)


def raster_tables(image,width,height):
    gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
    binary=cv2.adaptiveThreshold(gray,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY_INV,39,9)
    ih,iw=gray.shape; sx,sy=iw/width,ih/height
    horizontal=cv2.morphologyEx(binary,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_RECT,(max(35,int(iw*.25)),1)))
    vertical=cv2.morphologyEx(binary,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_RECT,(1,max(35,int(ih*.12)))))
    mask=cv2.bitwise_or(horizontal,vertical)
    count,labels,stats,_=cv2.connectedComponentsWithStats(cv2.dilate(mask,np.ones((3,3),np.uint8)),8)
    tables=[]
    for label in range(1,count):
        x,y,w,h,pixels=stats[label]
        if w/sx<100 or h/sy<40: continue
        hm=horizontal[y:y+h,x:x+w]; vm=vertical[y:y+h,x:x+w]
        xp=np.where((vm>0).sum(axis=0)>h*.35)[0]
        yp=np.where((hm>0).sum(axis=1)>w*.3)[0]
        xs=cluster([float(v+x) for v in xp],2.5*sx)
        ys=cluster([float(v+y) for v in yp],2.5*sy)
        if len(xs)<2 or len(ys)<2 or (len(xs)-1)*(len(ys)-1)<2: continue
        nr,nc=len(ys)-1,len(xs)-1
        parent=list(range(nr*nc))
        def find(a):
            while parent[a]!=a: parent[a]=parent[parent[a]]; a=parent[a]
            return a
        def merge(a,b):parent[find(a)]=find(b)
        def v_support(xx,a,b):
            strip=vertical[max(0,round(a)+3):min(ih,round(b)-3),max(0,round(xx)-2):min(iw,round(xx)+3)]
            return np.mean(np.any(strip>0,axis=1)) if strip.size else 1
        def h_support(yy,a,b):
            strip=horizontal[max(0,round(yy)-2):min(ih,round(yy)+3),max(0,round(a)+3):min(iw,round(b)-3)]
            return np.mean(np.any(strip>0,axis=0)) if strip.size else 1
        for r in range(nr):
            for c in range(nc):
                if c+1<nc and v_support(xs[c+1],ys[r],ys[r+1])<.5:merge(r*nc+c,r*nc+c+1)
                if r+1<nr and h_support(ys[r+1],xs[c],xs[c+1])<.5:merge(r*nc+c,(r+1)*nc+c)
        groups={}
        for r in range(nr):
            for c in range(nc):groups.setdefault(find(r*nc+c),[]).append((r,c))
        rectangles=[]; valid=True
        for positions in groups.values():
            rs=[p[0] for p in positions]; cs=[p[1] for p in positions]
            r0,r1,c0,c1=min(rs),max(rs)+1,min(cs),max(cs)+1
            if len(positions)!=(r1-r0)*(c1-c0):valid=False;break
            rectangles.append([xs[c0]/sx,ys[r0]/sy,xs[c1]/sx,ys[r1]/sy])
        grid=cell_grid(rectangles,tolerance=.9) if valid else None
        if grid:
            grid.update(bbox=[xs[0]/sx,ys[0]/sy,xs[-1]/sx,ys[-1]/sy],method="raster_line_intersections",needs_review=False)
            tables.append(grid)
    return tables,binary,horizontal,vertical


def native_evidence(page):
    tables=[]
    if page.get_drawings():
        kwargs=dict(strategy="lines_strict")
        if "use_layout" in inspect.signature(page.find_tables).parameters:kwargs["use_layout"]=False
        for table in page.find_tables(**kwargs).tables:
            grid=cell_grid(table.cells,tolerance=.6)
            if grid and grid["rows"]*grid["cols"]>1:
                grid.update(bbox=list(table.bbox),method="native_pdf_grid",needs_review=False)
                tables.append(grid)
    directions={}
    for b in page.get_text("dict")["blocks"]:
        if b["type"]==0:
            for line_number,line in enumerate(b["lines"]): directions[(b["number"],line_number)]=list(line["dir"])
    words=[]
    for i,w in enumerate(page.get_text("words")):
        words.append(dict(id=f"native_{i}",bbox=list(w[:4]),text=w[4],from_ocr=False,
            direction=directions.get((w[5],w[6]),[1,0]),source="native_pdf_word"))
    return tables,words,page.get_image_info(xrefs=True)


def images_in_tables(image,tables,known,width,height,grid_mask,figure_hints=()):
    gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY); ih,iw=gray.shape; sx,sy=iw/width,ih/height
    white=float(np.percentile(gray,95))
    mask=np.uint8(gray<white-8)*255
    mask[cv2.dilate(grid_mask,np.ones((5,5),np.uint8))>0]=0
    mask=cv2.morphologyEx(mask,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
    count,labels,stats,_=cv2.connectedComponentsWithStats(mask,8)
    result=[]
    for i in range(1,count):
        x,y,w,h,pixels=stats[i]; b=[x/sx,y/sy,(x+w)/sx,(y+h)/sy]
        if w/sx<35 or h/sy<20 or pixels/(w*h)<.55:continue
        if any(iou(b,k["bbox"])>.5 or inside(b,k["bbox"],2) for k in known):continue
        owners=[(t,c) for t in tables for c in t["cells"] if inside(b,c["bbox"],-2)]
        hinted=any(intersection(b,f["bbox"])/max(1,min(area(b),area(f["bbox"])))>.7 for f in figure_hints)
        if not owners and not (hinted and not any(intersection(b,t["bbox"])/max(1,area(b))>.5 for t in tables)):continue
        patch=gray[y:y+h,x:x+w]
        if np.mean(patch<white-25)<.14:continue
        result.append(dict(bbox=b,label="image",method="interior_raster_tone_region",needs_review=True))
    filtered=[]
    for candidate in sorted(result,key=lambda r:area(r["bbox"]),reverse=True):
        if not any(inside(candidate["bbox"],kept["bbox"],2) for kept in filtered):filtered.append(candidate)
    return filtered


def diagrams_in_tables(image,tables,images,width,height,binary,grid_mask):
    ih,iw=binary.shape; sx,sy=iw/width,ih/height
    working=binary.copy()
    working[cv2.dilate(grid_mask,np.ones((5,5),np.uint8))>0]=0
    for picture in images:
        a,b,c,d=picture["bbox"]
        cv2.rectangle(working,(round(a*sx)-2,round(b*sy)-2),(round(c*sx)+2,round(d*sy)+2),0,-1)
    working=cv2.morphologyEx(working,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
    contours,_=cv2.findContours(working,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)
    candidates=[]
    for contour in contours:
        x,y,w,h=cv2.boundingRect(contour)
        b=[x/sx,y/sy,(x+w)/sx,(y+h)/sy]
        if w/sx<28 or h/sy<14 or w/h<.4 or w/h>8:continue
        polygon=cv2.approxPolyDP(contour,.018*cv2.arcLength(contour,True),True)
        if not (4<=len(polygon)<=8 and cv2.isContourConvex(polygon)):continue
        if cv2.contourArea(contour)/(w*h)<.4:continue
        owners=[t for t in tables if inside(b,t["bbox"],1)]
        if not owners:continue
        owner=min(owners,key=lambda t:area(t["bbox"]))
        if any(iou(b,c["bbox"])>.72 for c in owner["cells"]):continue
        if any(iou(b,k["bbox"])>.8 for k in candidates):continue
        candidates.append(dict(bbox=b,table_id=owner["id"]))
    parent=list(range(len(candidates)))
    def find(a):
        while parent[a]!=a:parent[a]=parent[parent[a]];a=parent[a]
        return a
    def merge(a,b):parent[find(a)]=find(b)
    for i,a in enumerate(candidates):
        for j,b in enumerate(candidates[:i]):
            if a["table_id"]!=b["table_id"]:continue
            upper,lower=sorted([a["bbox"],b["bbox"]],key=lambda r:r[1])
            overlap=max(0,min(upper[2],lower[2])-max(upper[0],lower[0]))
            if overlap/min(upper[2]-upper[0],lower[2]-lower[0])<.4:continue
            gap=lower[1]-upper[3]
            if gap<0 or gap>2.5*max(upper[3]-upper[1],lower[3]-lower[1]):continue
            center=(max(upper[0],lower[0])+min(upper[2],lower[2]))/2
            strip=working[max(0,round(upper[3]*sy)-2):min(ih,round(lower[1]*sy)+3),max(0,round(center*sx)-5):min(iw,round(center*sx)+6)]
            if strip.size and np.mean(np.any(strip>0,axis=1))>.55:merge(i,j)
    _,labels,stats,_=cv2.connectedComponentsWithStats(working,8)
    groups={}
    for i,node in enumerate(candidates):groups.setdefault(find(i),[]).append(node)
    diagrams=[]
    for nodes in groups.values():
        if len(nodes)<2:continue
        boxes=[n["bbox"] for n in nodes]; component_ids=set()
        for node in nodes:
            a,b,c,d=node["bbox"]; x0,y0,x1,y1=round(a*sx),round(b*sy),round(c*sx),round(d*sy)
            border=labels[max(0,y0-4):min(ih,y1+4),max(0,x0-4):min(iw,x1+4)]
            for label in np.unique(border):
                if label and stats[label,cv2.CC_STAT_AREA]>60:component_ids.add(int(label))
        table=next(t for t in tables if t["id"]==nodes[0]["table_id"])
        for label in component_ids:
            x,y,w,h,_=stats[label]; cb=[x/sx,y/sy,(x+w)/sx,(y+h)/sy]
            if inside(cb,table["bbox"],1) and area(cb)<area(table["bbox"])*.65:boxes.append(cb)
        a,b,c,d=union(boxes); tb=table["bbox"]
        crop=[max(tb[0]+1,a-6),max(tb[1]+1,b-6),min(tb[2]-1,c+6),min(tb[3]-1,d+6)]
        diagrams.append(dict(bbox=crop,label="diagram",method="closed_shapes_with_connectors",table_id=table["id"],
            node_count=len(nodes),needs_review=True))
    return diagrams,working,candidates


def compose_text(tokens):
    lines=[]
    for token in sorted(tokens,key=lambda t:(t["bbox"][1],t["bbox"][0])):
        b=token["bbox"]
        line=next((line for line in lines if abs(line[0]["bbox"][1]-b[1])<max(2,min(line[0]["bbox"][3]-line[0]["bbox"][1],b[3]-b[1])*.45)),None)
        if line is None:lines.append([token])
        else:line.append(token)
    return "\n".join(" ".join(t["text"] for t in sorted(line,key=lambda t:t["bbox"][0])) for line in lines)


def table_html(table):
    starts={(c["row"],c["col"]):c for c in table["cells"]}
    rows=[]
    for row in range(table["rows"]):
        cells=[]
        for col in range(table["cols"]):
            c=starts.get((row,col))
            if c is not None:
                cells.append(f'<td rowspan="{c["rowspan"]}" colspan="{c["colspan"]}">{html.escape(c["text"]).replace(chr(10),"<br>")}</td>')
        rows.append("<tr>"+"".join(cells)+"</tr>")
    return "<table><tbody>"+"".join(rows)+"</tbody></table>"


def refine(pdf,page_number,image_path,evidence,destination):
    start=time.perf_counter(); out=copy.deepcopy(evidence)
    write_json(destination/"parser_evidence.json",evidence)
    image=cv2.imread(str(image_path)); height,width=evidence["height"],evidence["width"]
    cv_tables,binary,horizontal,vertical=raster_tables(image,width,height)
    with fitz.open(pdf) as doc:
        native_tables,native_tokens,placements=native_evidence(doc[page_number-1])
    tables=[]
    for candidate in native_tables+cv_tables:
        if not any(iou(candidate["bbox"],existing["bbox"])>.65 for existing in tables):tables.append(candidate)
    # A geometric grid is accepted only when complete rectangular occupancy was reconstructed.
    for candidate in evidence["tables"]:
        if candidate.get("bbox") and not any(iou(candidate["bbox"],t["bbox"])>.5 for t in tables):
            candidate=copy.deepcopy(candidate);candidate["method"]="parser_fallback";candidate["needs_review"]=True
            tables.append(candidate)
    for i,t in enumerate(tables):
        t["id"]=f"geometry_table_{i}";t["parent_ref"]=None
        for j,c in enumerate(t["cells"]):c["id"]=f"{t['id']}_cell_{j}"
    known=[]
    for i,p in enumerate(placements):
        b=list(p["bbox"])
        if area(b)/ (width*height)>.75:continue
        if any(iou(b,t["bbox"])>.7 for t in tables):continue
        in_table=any(inside(b,t["bbox"],1) for t in tables)
        parser_figure=any(k["type"]=="figure" and k.get("bbox") and iou(b,k["bbox"])>.45 for k in evidence["blocks"])
        if in_table or parser_figure:
            known.append(dict(bbox=b,label="image",method="native_image_placement",xref=p.get("xref"),needs_review=False))
    old_figures=[b for b in evidence["blocks"] if b["type"]=="figure" and b.get("bbox")]
    pictures=known+images_in_tables(image,tables,known,width,height,cv2.bitwise_or(horizontal,vertical),old_figures)
    diagrams,working,nodes=diagrams_in_tables(image,tables,pictures,width,height,binary,cv2.bitwise_or(horizontal,vertical))
    figures=pictures+diagrams
    for old in old_figures:
        if any(iou(old["bbox"],t["bbox"])>.65 for t in tables):continue
        if any(iou(old["bbox"],f["bbox"])>.45 for f in figures):continue
        figures.append(dict(bbox=old["bbox"],label=old["label"],method="parser_figure",needs_review=False))
    # Native words are authoritative in their own regions; OCR is retained in raster/scan regions.
    ocr_tokens=evidence.get("tokens",evidence["texts"])
    tokens=copy.deepcopy(native_tokens)
    for i,t in enumerate(ocr_tokens):
        if not t.get("from_ocr",True):continue
        if any(intersection(t["bbox"],n["bbox"])/max(1,area(n["bbox"]))>.65 for n in native_tokens):continue
        token=copy.deepcopy(t);token.update(id=f"ocr_{i}",from_ocr=True,source="pipeline_ocr")
        tokens.append(token)
    for i,t in enumerate(tokens):t["id"]=f"token_{i}"
    for token in tokens:
        token["needs_review"]=bool(token.get("from_ocr") and token.get("confidence") is not None and token["confidence"]<.5)
    figure_blocks=[]; containers=[]
    for i,f in enumerate(figures):
        f.update(id=f"recovered_figure_{i}",type="figure",parent_ref=None,child_refs=[])
        owners=[(t,c) for t in tables for c in t["cells"] if c.get("bbox") and inside(f["bbox"],c["bbox"],2)]
        if owners:
            table,cell=min(owners,key=lambda tc:area(tc[1]["bbox"]))
            if f["label"]=="diagram" and cell["rowspan"]>1:
                f["parent_ref"]=table["id"];f["association"]="table_region_crosses_row_bands"
            else:
                f["parent_ref"]=cell["id"];f["association"]="contained_in_geometric_cell"
        else:
            owners=[t for t in tables if inside(f["bbox"],t["bbox"],2)]
            if owners:f["parent_ref"]=min(owners,key=lambda t:area(t["bbox"]))["id"]
        figure_blocks.append(f)
    for token in tokens:
        b=token["bbox"];token["owner_kind"]="body";token["owner_id"]=None
        figure=next((f for f in figures if intersection(b,f["bbox"])/max(1,area(b))>.75),None)
        if figure:
            token.update(owner_kind="figure_metadata",owner_id=figure["id"]);continue
        candidates=[]
        for table in tables:
            for cell in table["cells"]:
                cb=cell.get("bbox")
                if not cb:continue
                center=((b[0]+b[2])/2,(b[1]+b[3])/2)
                if cb[0]<=center[0]<=cb[2] and cb[1]<=center[1]<=cb[3]:
                    fraction=intersection(b,cb)/max(1,area(b))
                    if fraction>.65:candidates.append((fraction,cell))
        if candidates:
            candidates.sort(key=lambda p:p[0],reverse=True)
            if len(candidates)==1 or candidates[0][0]-candidates[1][0]>.15:
                token.update(owner_kind="table_cell",owner_id=candidates[0][1]["id"])
            else:token["owner_kind"]="needs_review"
        elif any(intersection(b,t["bbox"])/max(1,area(b))>.5 for t in tables):token["owner_kind"]="needs_review"
    for table in tables:
        for cell in table["cells"]:
            owned=[t for t in tokens if t["owner_id"]==cell["id"]]
            cell["text"]=compose_text(owned);cell["token_ids"]=[t["id"] for t in owned]
            cell["needs_review"]=bool(cell.get("needs_review") or any(t["needs_review"] for t in owned))
            containers.append(dict(id=cell["id"],type="table_cell",label="table_cell",parent_ref=table["id"],
                row=cell["row"],col=cell["col"],rowspan=cell["rowspan"],colspan=cell["colspan"],child_refs=[]))
    blocks=[]
    for b in evidence["blocks"]:
        b=copy.deepcopy(b)
        if b["type"] in ("table","figure"):continue
        bb=b.get("bbox")
        if bb and any(intersection(bb,t["bbox"])/max(1,area(bb))>.55 for t in tables):continue
        if bb and any(intersection(bb,f["bbox"])/max(1,area(bb))>.7 for f in figures):continue
        if bb:
            native=[t for t in native_tokens if intersection(t["bbox"],bb)/max(1,area(t["bbox"]))>.7]
            if len(native)>=max(1,len(b.get("text","").split())*.55):
                b["text"]=compose_text(native);b["text_method"]="native_geometry_recovery"
        blocks.append(b)
    for table in tables:blocks.append(dict(id=table["id"],type="table",label="table",bbox=table["bbox"],parent_ref=None,method=table["method"]))
    blocks+=figure_blocks
    for f in figures:f["metadata_text"]=compose_text([t for t in tokens if t["owner_id"]==f["id"]])
    out.update(blocks=blocks,tables=tables,containers=containers,tokens=tokens,
        texts=[dict(bbox=t["bbox"],text=t["text"],source_ref=t["id"],source=t["source"]) for t in tokens if t["owner_kind"]!="figure_metadata"],
        refinement=dict(version=VERSION,assumptions="upright ruled tables; diagram candidates require connected closed shapes",
            native_words=len(native_tokens),ocr_tokens=sum(t["from_ocr"] for t in tokens),
            unassigned_token_count=sum(t["owner_kind"]=="needs_review" for t in tokens),seconds=time.perf_counter()-start))
    cv2.imwrite(str(destination/"grid_mask.png"),cv2.bitwise_or(horizontal,vertical))
    cv2.imwrite(str(destination/"diagram_working_mask.png"),working)
    write_json(destination/"geometry_candidates.json",dict(tables=tables,figures=figures,nodes=nodes,image_placements=placements))
    write_json(destination/"token_ownership.json",tokens)
    for i,table in enumerate(tables):(destination/f"table_{i:02}.html").write_text(table_html(table),encoding="utf-8")
    return out
