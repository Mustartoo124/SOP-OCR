"""Safe standalone HTML/SVG renderer of canonical JSON (no original-image overlay)."""
import html
from pathlib import Path
import base64

def esc(s): return html.escape(str(s),quote=True)

def svg(page, diagram=None):
    selected=set(diagram.node_ids) if diagram else {c.id for c in page.components}
    b=diagram.bbox if diagram else None
    view=f'{b.x} {b.y} {b.w} {b.h}' if b else '0 0 1000 1000'
    parts=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view}" width="100%" style="background:white" role="img">',
           '<defs><marker id="arrow" markerWidth="7" markerHeight="7" refX="6" refY="3" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L6,3 L0,6 Z" fill="#334155"/></marker></defs>']
    if not diagram:
        for t in page.tables:
            for cell in t.cells:
                bb=cell.source_bbox
                parts.append(f'<rect x="{bb.x}" y="{bb.y}" width="{bb.w}" height="{bb.h}" fill="none" stroke="#cbd5e1" stroke-width=".6"/>')
    diagrams=[diagram] if diagram else page.diagrams
    for d in diagrams:
        for edge in d.edges:
            points=' '.join(f'{p.x},{p.y}' for p in edge.points)
            parts.append(f'<polyline points="{points}" fill="none" stroke="#334155" stroke-width="1.1" marker-end="url(#arrow)"/>')
            if edge.label:
                pos=edge.label_position or edge.points[len(edge.points)//2]
                parts.append(f'<text x="{pos.x}" y="{pos.y-3}" font-size="10" paint-order="stroke" stroke="white" stroke-width="3" fill="#111">{esc(edge.label)}</text>')
    for c in page.components:
        if c.id not in selected: continue
        x,y,w,h=c.bbox.x,c.bbox.y,c.bbox.w,c.bbox.h
        style='fill="#effbff" stroke="#334155" stroke-width="1"'
        if c.kind=='flow_node':
            if c.shape=='diamond': parts.append(f'<polygon points="{x+w/2},{y} {x+w},{y+h/2} {x+w/2},{y+h} {x},{y+h/2}" {style}/>')
            elif c.shape=='ellipse': parts.append(f'<ellipse cx="{x+w/2}" cy="{y+h/2}" rx="{w/2}" ry="{h/2}" {style}/>')
            elif c.shape=='document': parts.append(f'<path d="M{x},{y} H{x+w} V{y+h*.85} Q{x+w*.75},{y+h*.65} {x+w/2},{y+h*.85} T{x},{y+h*.85} Z" {style}/>')
            elif c.shape=='parallelogram': parts.append(f'<polygon points="{x+w*.12},{y} {x+w},{y} {x+w*.88},{y+h} {x},{y+h}" {style}/>')
            else:
                parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{h/2 if c.shape=="rounded" else 0}" {style}/>')
                if c.shape=='predefined':
                    for xx in [x+w*.08,x+w*.92]: parts.append(f'<path d="M{xx},{y} V{y+h}" stroke="#334155"/>')
        font=max(6,min(11,(w*h/max(len(c.text),1)*1.35)**.5))
        align='center' if c.kind=='flow_node' else 'left'
        parts.append(f'<foreignObject x="{x+2}" y="{y+1}" width="{max(w-4,1)}" height="{max(h-2,1)}"><div xmlns="http://www.w3.org/1999/xhtml" style="font:{font}px Arial;white-space:pre-wrap;overflow-wrap:anywhere;text-align:{align};height:100%;display:flex;align-items:center;justify-content:{"center" if align=="center" else "flex-start"}">{esc(c.text or ("[Image]" if c.kind=="image" else ""))}</div></foreignObject>')
    parts.append('</svg>')
    return ''.join(parts)

def logical_table(page, table, assets_root=None):
    components={c.id:c for c in page.components}; diagrams={d.id:d for d in page.diagrams}
    starts={(c.row,c.column):c for c in table.cells}
    occupied={(r,k) for c in table.cells for r in range(c.row,c.row+c.rowspan) for k in range(c.column,c.column+c.colspan)}
    parts=['<table style="border-collapse:collapse;width:100%;table-layout:fixed;font:14px Arial"><colgroup>']
    total=sum(c.width for c in table.columns)
    parts.extend(f'<col style="width:{c.width/total*100}%">' for c in table.columns)
    parts.append('</colgroup><thead><tr>')
    parts.extend(f'<th style="border:1px solid #aaa;padding:8px;background:#e8f0f7">{esc(c.title)}</th>' for c in table.columns)
    parts.append('</tr></thead><tbody>')
    for r,row in enumerate(table.rows):
        parts.append(f'<tr data-row="{esc(row.id)}">')
        for col in range(len(table.columns)):
            cell=starts.get((r,col))
            if cell:
                parts.append(f'<td rowspan="{cell.rowspan}" colspan="{cell.colspan}" style="vertical-align:middle;border:1px solid #aaa;padding:6px;overflow-wrap:anywhere">')
                if cell.diagram_id: parts.append(svg(page,diagrams[cell.diagram_id]))
                for cid in cell.component_ids:
                    c=components[cid]
                    parts.append(f'<div style="white-space:pre-wrap" title="{esc(cid)}">{esc(c.text)}</div>')
                    if c.kind=='image' and c.asset_ref and assets_root:
                        root=Path(assets_root).resolve(); path=(root/c.asset_ref).resolve()
                        if path.is_relative_to(root) and path.is_file():
                            encoded=base64.b64encode(path.read_bytes()).decode()
                            parts.append(f'<img style="width:100%" src="data:image/png;base64,{encoded}">')
                parts.append('</td>')
            elif (r,col) not in occupied: parts.append('<td style="border:1px solid #aaa"></td>')
        parts.append('</tr>')
    parts.append('</tbody></table>')
    return ''.join(parts)
