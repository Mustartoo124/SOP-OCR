"""Local routing: native/OCR prose; VLM only for selected structural regions.

Automatic detection is a heuristic proposal. Explicit per-page regions override it.
Coordinates of all region boxes are page-normalized x,y,w,h.
"""
import json
import os
from pathlib import Path
from PIL import Image
from .schema import Box, Component, Page, validate_page

def overlap(a,b):
    return min(a['x']+a['w'],b['x']+b['w'])>max(a['x'],b['x']) and min(a['y']+a['h'],b['y']+b['h'])>max(a['y'],b['y'])

def union(boxes):
    x=min(b['x'] for b in boxes); y=min(b['y'] for b in boxes)
    return dict(x=x,y=y,w=max(b['x']+b['w'] for b in boxes)-x,h=max(b['y']+b['h'] for b in boxes)-y)

def native_layout(page):
    def norm(r):
        x0=max(0,r[0]/page.rect.width*1000); y0=max(0,r[1]/page.rect.height*1000)
        x1=min(1000,r[2]/page.rect.width*1000); y1=min(1000,r[3]/page.rect.height*1000)
        return dict(x=x0,y=y0,w=max(.01,x1-x0),h=max(.01,y1-y0))
    lines=[]
    for block in page.get_text('dict')['blocks']:
        for line in block.get('lines',[]):
            text=''.join(s['text'] for s in line['spans'])
            if text.strip(): lines.append(dict(text=text,bbox=norm(line['bbox'])))
    regions=[]; warnings=[]
    try:
        for t in page.find_tables().tables:
            if t.row_count>=2 and t.col_count>=2: regions.append(norm(t.bbox))
    except Exception as exc:
        warnings.append(f'Native table detection failed: {type(exc).__name__}')
    # Multiple nontrivial vector shapes may be a flowchart. Include connected
    # drawing extents in one region, avoiding node-by-node splitting.
    drawings=[d for d in page.get_drawings() if d['rect'].width>8 and d['rect'].height>8]
    if len(drawings)>=3:
        regions.append(union([norm(d['rect']) for d in drawings]))
        warnings.append('Vector cluster routed as table/diagram candidate; verify the routing preview.')
    images=[norm(i['bbox']) for i in page.get_image_info()]
    if not regions and len(lines)>4:
        # Detect repeated multi-column alignment, a proposal for borderless tables.
        bins={}
        for line in lines:
            b=line['bbox']; key=round(b['y']/6)
            bins.setdefault(key,[]).append(b)
        aligned=[bs for bs in bins.values() if len(bs)>=3 and max(b['x'] for b in bs)-min(b['x'] for b in bs)>200]
        if len(aligned)>=3:
            regions.append(union([b for bs in aligned for b in bs]))
            warnings.append('Repeated text alignment routed as possible borderless table; heuristic, not a semantic classifier.')
    return dict(lines=lines,regions=regions,images=images,warnings=warnings)

def ocr_lines(path):
    try:
        import pytesseract
    except ImportError as exc:
        raise RuntimeError('Scan/image text requires local OCR: install sop_demo/requirements-ocr.txt and Tesseract with vie+eng language data. VLM text fallback is disabled.') from exc
    if os.getenv('SOP_TESSERACT'): pytesseract.pytesseract.tesseract_cmd=os.environ['SOP_TESSERACT']
    image=Image.open(path)
    try:
        data=pytesseract.image_to_data(image,lang=os.getenv('SOP_OCR_LANG','vie+eng'),output_type=pytesseract.Output.DICT)
    except Exception as exc:
        raise RuntimeError('Local OCR failed. Check Tesseract executable and SOP_OCR_LANG language data; no VLM fallback for prose.') from exc
    groups={}
    for i,text in enumerate(data['text']):
        if not text.strip() or float(data['conf'][i])<0: continue
        key=(data['block_num'][i],data['par_num'][i],data['line_num'][i])
        groups.setdefault(key,[]).append((i,text))
    lines=[]
    for words in groups.values():
        boxes=[dict(x=data['left'][i]/image.width*1000,y=data['top'][i]/image.height*1000,w=data['width'][i]/image.width*1000,h=data['height'][i]/image.height*1000) for i,_ in words]
        lines.append(dict(text=' '.join(t for _,t in words),bbox=union(boxes)))
    return lines

def plan(info, overrides=None):
    layout=info.get('layout',dict(lines=[],regions=[],images=[],warnings=[]))
    warnings=list(layout['warnings'])
    declared=overrides is not None and str(info['number']) in overrides
    if declared:
        regions=[Box.model_validate(b).model_dump() for b in overrides[str(info['number'])]]
    else:
        regions=layout['regions']
    native=layout['lines']
    # Full-page scans and image inputs need region declarations: never silently
    # decide a borderless table is prose just because there are no native vectors.
    raster_page=not native or any(b['w']*b['h']>600000 for b in layout['images'])
    if raster_page and not declared:
        raise RuntimeError(f'Page {info["number"]}: scan/image requires --regions manifest (table/diagram boxes; [] confirms prose-only). No automatic full-page VLM fallback.')
    lines=native
    engine='native_pdf'
    # No OCR needed when the explicitly selected structural ROI covers the page.
    full_structure=regions and union(regions)['w']>=999 and union(regions)['h']>=999
    if raster_page and not full_structure:
        lines=ocr_lines(info['image']); engine='tesseract'
    elif raster_page:
        lines=[]; engine='none_full_structural_region'
    if regions:
        # One enclosing crop preserves cross-column relations and connectors.
        roi=union(regions)
        roi=dict(x=max(0,roi['x']-4),y=max(0,roi['y']-4),w=min(1000,roi['x']+roi['w']+4)-max(0,roi['x']-4),h=min(1000,roi['y']+roi['h']+4)-max(0,roi['y']-4))
        # Expand to retain complete text lines touched by the structural region.
        for _ in range(len(lines)+1):
            touched=[line['bbox'] for line in lines if overlap(line['bbox'],roi)]
            expanded=union([roi]+touched)
            if expanded==roi: break
            roi=expanded
    else: roi=None
    outside=[line for line in lines if not roi or not overlap(line['bbox'],roi)]
    if layout['images'] and not raster_page:
        warnings.append('Embedded raster images outside structural regions are preserved as images; inspect for unclassified raster diagrams and declare --regions when needed.')
    warnings.append('Hybrid routing is heuristic. Review routing.json/region crop for missed borderless tables or diagrams; no automatic VLM fallback on uncertain prose.')
    return dict(roi=roi,lines=outside,all_lines=lines,text_engine=engine,warnings=warnings,declared=declared,images=layout['images'] if not raster_page else [])

def map_page(page, roi):
    """Transform a crop-local Page into page coordinates, preserving all references."""
    def box(b):
        b.x=roi['x']+b.x*roi['w']/1000; b.y=roi['y']+b.y*roi['h']/1000
        b.w*=roi['w']/1000; b.h*=roi['h']/1000
    def point(p):
        p.x=roi['x']+p.x*roi['w']/1000; p.y=roi['y']+p.y*roi['h']/1000
    for c in page.components: box(c.bbox)
    for d in page.diagrams:
        box(d.bbox)
        for e in d.edges:
            for p in e.points: point(p)
            if e.label_position: point(e.label_position)
    for t in page.tables:
        box(t.bbox)
        for col in t.columns:
            col.x=roi['x']+col.x*roi['w']/1000; col.width*=roi['w']/1000
        for row in t.rows:
            row.y=roi['y']+row.y*roi['h']/1000; row.height*=roi['h']/1000
        for c in t.cells: box(c.source_bbox)
    return validate_page(page)

def extract_hybrid(info,out,model,review,response_mode,extractor,overrides=None):
    routing=plan(info,overrides)
    (out/f'page-{info["number"]}-routing.json').write_text(json.dumps(routing,ensure_ascii=False,indent=2),encoding='utf-8')
    roi=routing['roi']; attempts=[]
    page=Page(number=info['number'],components=[],diagrams=[],tables=[],relations=[],warnings=[])
    if roi:
        image=Image.open(info['image'])
        # Use actual rounded pixel crop as transform origin to avoid drift.
        coords=(int(roi['x']*image.width/1000),int(roi['y']*image.height/1000),min(image.width,int((roi['x']+roi['w'])*image.width/1000+.999)),min(image.height,int((roi['y']+roi['h'])*image.height/1000+.999)))
        roi=dict(x=coords[0]/image.width*1000,y=coords[1]/image.height*1000,w=(coords[2]-coords[0])/image.width*1000,h=(coords[3]-coords[1])/image.height*1000)
        dest=out/'assets'/f'page-{info["number"]}-structure.png'; image.crop(coords).save(dest)
        evidence=[]
        for line in routing['all_lines']:
            b=line['bbox']
            if overlap(b,roi):
                evidence.append(dict(text=line['text'],bbox=[(b['x']-roi['x'])/roi['w']*1000,(b['y']-roi['y'])/roi['h']*1000,(b['x']+b['w']-roi['x'])/roi['w']*1000,(b['y']+b['h']-roi['y'])/roi['h']*1000]))
        crop_info=dict(info,image=dest,native_text=evidence)
        page,attempts=extractor(crop_info,out,model,review,response_mode)
        map_page(page,roi)
    # Prefix locals without colliding with any model-owned ID.
    payload=page.model_dump_json()
    prefix='local_'
    while prefix in payload: prefix='_'+prefix
    for i,line in enumerate(routing['lines']):
        page.components.append(Component(id=f'{prefix}text_{i}',kind='text',text=line['text'],bbox=line['bbox']))
    for i,b in enumerate(routing['images']):
        if not roi or not overlap(b,roi): page.components.append(Component(id=f'{prefix}image_{i}',kind='image',text='',bbox=b))
    page.warnings.extend(routing['warnings'])
    validate_page(page)
    audit=dict(number=info['number'],text_engine=routing['text_engine'],local_text_count=len(routing['lines']),vlm_region=roi,vlm_calls=len(attempts),regions_explicit=routing['declared'])
    return page,attempts,audit
