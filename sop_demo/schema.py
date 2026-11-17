"""Canonical intermediate representation; coordinates are page-normalized 0..1000."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

class Model(BaseModel):
    model_config = ConfigDict(extra='forbid')

class Box(Model):
    x: float = Field(ge=0, le=1000)
    y: float = Field(ge=0, le=1000)
    w: float = Field(gt=0, le=1000)
    h: float = Field(gt=0, le=1000)
    @model_validator(mode='after')
    def bounds(self):
        if self.x+self.w > 1001 or self.y+self.h > 1001:
            raise ValueError('bbox outside page')
        return self

class Point(Model):
    x: float = Field(ge=0, le=1000)
    y: float = Field(ge=0, le=1000)

class Component(Model):
    id: str
    kind: Literal['text','flow_node','image']
    text: str
    bbox: Box
    shape: Literal['rectangle','rounded','diamond','document','parallelogram','predefined','ellipse','none'] = 'none'
    confidence: float = Field(default=0.8, ge=0, le=1)
    asset_ref: str | None = None

class Edge(Model):
    id: str
    source: str
    target: str
    label: str = ''
    points: list[Point] = Field(min_length=2)
    label_position: Point | None = None
    kind: Literal['sequence','input','association'] = 'sequence'
    confidence: float = Field(default=0.8, ge=0, le=1)

class Diagram(Model):
    id: str
    bbox: Box
    node_ids: list[str]
    edges: list[Edge]

class Column(Model):
    id: str
    title: str
    role: Literal['flowchart','description','responsibility','timing','reference','stage','other']
    x: float = Field(ge=0, le=1000)
    width: float = Field(gt=0, le=1000)

class Row(Model):
    id: str
    y: float = Field(ge=0, le=1000)
    height: float = Field(gt=0, le=1000)
    source_band: str
    anchor_ids: list[str]

class Cell(Model):
    id: str
    row: int = Field(ge=0)
    column: int = Field(ge=0)
    rowspan: int = Field(default=1, ge=1)
    colspan: int = Field(default=1, ge=1)
    component_ids: list[str]
    diagram_id: str | None = None
    source_bbox: Box

class Table(Model):
    id: str
    bbox: Box
    columns: list[Column] = Field(min_length=1)
    rows: list[Row] = Field(min_length=1)
    cells: list[Cell]

class Relation(Model):
    id: str
    source: str
    target: str
    kind: Literal['aligned_with','describes','responsible_for','timing_for','reference_for','continues','contains','other']
    basis: Literal['geometry','semantics','both','explicit']
    confidence: float = Field(ge=0, le=1)
    rationale: str

class Page(Model):
    number: int = Field(ge=1)
    components: list[Component]
    diagrams: list[Diagram]
    tables: list[Table]
    relations: list[Relation]
    warnings: list[str]

class Document(Model):
    schema_version: Literal['1.0'] = '1.0'
    source_name: str
    source_sha256: str
    pages: list[Page]
    page_images: dict[str,str]
    cross_page_relations: list[Relation] = []
    provenance: dict = {}

def validate_page(page: Page):
    """Hard integrity constraints, distinct from semantic accuracy."""
    objects = page.components + page.diagrams + page.tables + page.relations
    objects += [e for d in page.diagrams for e in d.edges]
    objects += [o for t in page.tables for o in t.rows+t.columns+t.cells]
    ids = [o.id for o in objects]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate IDs within page')
    components = {c.id:c for c in page.components}
    diagrams = {d.id:d for d in page.diagrams}
    known = set(ids)
    def refs(values, allowed):
        missing = set(values)-set(allowed)
        if missing: raise ValueError(f'Dangling references: {sorted(missing)}')
    for d in page.diagrams:
        refs(d.node_ids, components)
        for e in d.edges: refs([e.source,e.target],d.node_ids)
    for r in page.relations: refs([r.source,r.target],known)
    for t in page.tables:
        occupied = set()
        for row in t.rows: refs(row.anchor_ids,components)
        for c in t.cells:
            refs(c.component_ids,components)
            if c.diagram_id: refs([c.diagram_id],diagrams)
            if c.row+c.rowspan>len(t.rows) or c.column+c.colspan>len(t.columns):
                raise ValueError(f'Cell span outside table: {c.id}')
            for r in range(c.row,c.row+c.rowspan):
                for col in range(c.column,c.column+c.colspan):
                    if (r,col) in occupied: raise ValueError(f'Overlapping cells: {c.id}')
                    occupied.add((r,col))
    return page

def validate_document(doc: Document):
    numbers = [p.number for p in doc.pages]
    if len(numbers)!=len(set(numbers)): raise ValueError('Duplicate page numbers')
    for p in doc.pages: validate_page(p)
    qualified = {f'p{p.number}:{c.id}' for p in doc.pages for c in p.components+p.diagrams+p.tables}
    for rel in doc.cross_page_relations:
        if rel.source not in qualified or rel.target not in qualified:
            raise ValueError('Invalid cross-page relation; use pN:id')
    return doc
