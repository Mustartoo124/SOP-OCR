"""Deterministic synthetic SOP fixtures. Labels come from authoring, never inference."""
from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
import math
from pathlib import Path
import random

import fitz
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
from pypdf import PdfReader
from pypdf.generic import ContentStream
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/pdf"
W, H = 595.2756, 841.8898
INK, BLUE, LIGHT = "#233448", "#17657B", "#EAF2F5"


def fonts(directory: str | None):
    candidates = [Path(directory)] if directory else [
        Path("C:/Windows/Fonts"), Path("/System/Library/Fonts/Supplemental"),
        Path("/usr/share/fonts/truetype/dejavu"),
    ]
    for base in candidates:
        for regular, bold in [("arial.ttf", "arialbd.ttf"), ("Arial.ttf", "Arial Bold.ttf"),
                              ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf")]:
            if (base / regular).exists() and (base / bold).exists():
                pdfmetrics.registerFont(TTFont("Body", str(base / regular)))
                pdfmetrics.registerFont(TTFont("Bold", str(base / bold)))
                return base / regular, base / bold
    raise RuntimeError("Use --font-dir with Arial or DejaVuSans TTF files supporting Vietnamese")


class Scene:
    def __init__(self, c, page):
        self.c, self.page, self.items = c, page, []

    def add(self, kind, box, parent=None, **extra):
        item = dict(id=f"p{self.page}_{len(self.items)+1:03}", type=kind,
                    page=self.page, bbox=list(box), parent_id=parent, **extra)
        self.items.append(item)
        return item["id"]

    def rect(self, box, fill=None, stroke="#A7B8C5", width=.55):
        x0, y0, x1, y1 = box
        self.c.setLineWidth(width)
        self.c.setStrokeColor(stroke)
        if fill:
            self.c.setFillColor(fill)
        self.c.rect(x0, H-y1, x1-x0, y1-y0, stroke=1, fill=bool(fill))

    def line(self, x0, y0, x1, y1, color=BLUE, width=.9):
        self.c.setStrokeColor(color)
        self.c.setLineWidth(width)
        self.c.line(x0, H-y0, x1, H-y1)

    def text(self, text, x, y, width, size=10, bold=False, parent=None,
             kind="text", color=INK, **extra):
        font = "Bold" if bold else "Body"
        lines = []
        for paragraph in text.split("\n"):
            current = ""
            for word in paragraph.split():
                candidate = (current + " " + word).strip()
                if current and pdfmetrics.stringWidth(candidate, font, size) > width:
                    lines.append(current)
                    current = word
                else:
                    current = candidate
            lines.append(current)
        line_height = size * 1.38
        box = [x, y, x + max(pdfmetrics.stringWidth(t, font, size) for t in lines),
               y + (len(lines)-1)*line_height + size*1.16]
        self.c.setFont(font, size)
        self.c.setFillColor(color)
        for i, line in enumerate(lines):
            self.c.drawString(x, H-y-size-i*line_height, line)
        return self.add(kind, box, parent, text=text, rendered_lines=lines, **extra)

    def cell(self, table, box, row, col, text="", rowspan=1, colspan=1, header=False, size=8.5):
        cell = self.add("table_cell", box, table, row=row, col=col,
                        rowspan=rowspan, colspan=colspan)
        self.rect(box, fill=LIGHT if header else "#FFFFFF")
        if text:
            self.text(text, box[0]+6, box[1]+7, box[2]-box[0]-12, size,
                      bold=header, parent=cell)
        return cell

    def arrow(self, points):
        for a, b in zip(points, points[1:]):
            self.line(*a, *b)
        a, b = points[-2:]
        angle = math.atan2(b[1]-a[1], b[0]-a[0])
        for sign in (-1, 1):
            self.line(b[0], b[1], b[0]-5*math.cos(angle+sign*.5), b[1]-5*math.sin(angle+sign*.5))

    def header(self, title, code):
        logo = self.add("image", [38, 27, 92, 68], representation="vector_logo", layer="furniture")
        self.rect([38, 27, 92, 68], fill=BLUE, stroke=BLUE)
        self.text("NOVA", 43, 39, 46, 13, bold=True, color="#FFFFFF", parent=logo,
                  role="figure_label", recognition_target=False)
        self.text("CÔNG TY TNHH THIẾT BỊ NOVA", 105, 28, 445, 10.5, bold=True, layer="furniture")
        self.text("Hệ thống quản lý chất lượng / Quality Management System", 105, 45, 445, 8.4, layer="furniture")
        self.text(f"{code} | Phiên bản 03 | Ngày hiệu lực: 15/10/2026", 105, 61, 445, 8.3, layer="furniture")
        self.line(38, 81, 557, 81)
        self.text(title, 38, 98, 519, 15, bold=True, kind="heading", level=1)
        self.line(38, 783, 557, 783, width=.5)
        self.text("TÀI LIỆU GIẢ LẬP - Chỉ dùng kiểm thử trích xuất", 38, 794, 430, 8, layer="furniture")
        self.text(f"Trang {self.page}/4", 501, 794, 58, 8, layer="furniture")


def photo(font_path):
    im = Image.new("RGB", (640, 320), "#E9EEF0")
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((28, 40, 290, 280), 14, fill="#D1DADF", outline="#637789", width=4)
    d.rectangle((65, 75, 252, 155), fill="#233448")
    d.text((88, 90), "24.8 C", font=ImageFont.truetype(str(font_path), 33), fill="#83E2CA")
    for x in [100, 165, 230]:
        d.ellipse((x-13, 196, x+13, 222), fill="#17657B")
    d.text((325, 80), "QC-017", font=ImageFont.truetype(str(font_path), 36), fill="#233448")
    d.text((325, 143), "THIẾT BỊ MẪU", font=ImageFont.truetype(str(font_path), 23), fill="#233448")
    d.text((325, 193), "0/O - 1/I", font=ImageFont.truetype(str(font_path), 26), fill="#233448")
    return im


def basic(s, asset):
    s.header("QUY TRÌNH KIỂM SOÁT THIẾT BỊ", "QP-74-02")
    s.text("1. Mục đích / Purpose", 38, 142, 510, 11.5, True, kind="heading", level=2)
    s.text("Bảo đảm thiết bị được kiểm tra, hiệu chuẩn và ghi nhận trước khi sử dụng. "
           "Áp dụng cho bộ phận Sản xuất và Đảm bảo chất lượng (QA).", 38, 169, 519)
    s.text("2. Trách nhiệm", 38, 225, 510, 11.5, True, kind="heading", level=2)
    for i, text in enumerate([
        "1. Nhân viên kiểm tra mã thiết bị QC-017 và tình trạng tem hiệu chuẩn.",
        "2. Trưởng bộ phận xác nhận kết quả theo biểu mẫu QP-74-02-F6.",
        "3. QA lưu hồ sơ; phân biệt mã 0/O, 1/I và số lô A-001-2026.",
    ]):
        s.text(text, 48, 254+i*30, 499, 9.8, kind="list_item", order=i)
    s.text("3. Acceptance criteria", 38, 366, 510, 11.5, True, kind="heading", level=2)
    s.text("Temperature: 20-25 °C. Relative humidity: 40-70%. Record every deviation "
           "and obtain QA approval before releasing the equipment.", 38, 393, 519)
    box = [96, 461, 500, 663]
    picture = s.add("image", box, representation="embedded_raster", expected_label_text="QC-017; THIẾT BỊ MẪU; 0/O - 1/I")
    s.c.drawImage(ImageReader(asset), box[0], H-box[3], box[2]-box[0], box[3]-box[1])
    s.text("Hình 1. Minh họa thiết bị và nhãn nhận dạng.", 119, 678, 400, 9,
           kind="caption", associated_with=picture)
    s.text("Lưu ý: Bản sao không có chữ ký phê duyệt chỉ dùng để tham khảo.", 38, 729, 519, 9)


def history(s):
    s.header("LỊCH SỬ BAN HÀNH VÀ PHÊ DUYỆT", "QP-74-02")
    s.text("Các ô gộp, nội dung nhiều dòng và chữ xoay phải được bảo toàn khi trích xuất.", 38, 137, 519, 9)
    x = [62, 104, 169, 227, 397, 474, 557]
    y = [177, 225, 291, 357, 423, 489, 555, 621, 687]
    table = s.add("table", [62,177,557,687], rows=8, cols=6, grid_policy="complete")
    for j, t in enumerate(["Lần sửa", "Ngày", "Mục", "Nội dung thay đổi", "Người soạn", "Phê duyệt"]):
        s.cell(table, [x[j],y[0],x[j+1],y[1]], 0,j,t,header=True)
    changes = [
        ("01", "12/03/2024", "Toàn bộ", "Ban hành lần đầu. Bổ sung hướng dẫn kiểm tra thiết bị.", "Nguyễn An", "Trần Bình"),
        (None,"12/03/2024","Phụ lục", "Biểu mẫu QP-74-02-F6 và danh mục thiết bị QC-017.","Lê Hà","Trần Bình"),
        ("02","08/06/2025","4.2", "Sửa tần suất hiệu chuẩn từ 12 tháng thành 6 tháng.","Đỗ Huy","Vũ Mai"),
        ("03","15/10/2026","5.1", "Bổ sung lưu đồ xử lý sai lệch; kiểm tra 0/O và 1/I.","Phạm Mỹ","Vũ Mai"),
        ("03","15/10/2026","5.2", "Phân công trách nhiệm QA và bộ phận Sản xuất.","Phạm Mỹ","Vũ Mai"),
        ("03","15/10/2026","6", "Hồ sơ lưu tối thiểu 03 năm. Record retention: 3 years.","Nguyễn An","Trần Bình"),
        ("03","15/10/2026","Ghi chú", "Dấu tiếng Việt: ă, â, ê, ô, ơ, ư, đ.\nĐã kiểm tra và phê duyệt.","Lê Hà / Trần Bình",None),
    ]
    for row, values in enumerate(changes, 1):
        for col, text in enumerate(values):
            if text is None:
                continue
            span = 2 if row==1 and col==0 else 1
            col_span = 2 if row==7 and col==4 else 1
            s.cell(table, [x[col],y[row],x[col+col_span],y[row+span]], row,col,text,
                   rowspan=span,colspan=col_span,size=8.3)
    s.rect([38,177,56,687], fill=LIGHT)
    s.c.saveState()
    s.c.translate(50,H-580)
    s.c.rotate(90)
    s.c.setFont("Bold",9)
    s.c.setFillColor(BLUE)
    s.c.drawString(0,0,"LỊCH SỬ TÀI LIỆU - DOCUMENT HISTORY")
    s.c.restoreState()
    label="LỊCH SỬ TÀI LIỆU - DOCUMENT HISTORY"
    label_width=pdfmetrics.stringWidth(label,"Bold",9)
    s.add("text", [41,580-label_width,52,582], text=label, rotation_degrees=270)
    approval = s.add("table", [62,710,557,758], rows=1, cols=1, grid_policy="complete")
    s.cell(approval,[62,710,557,758],0,0,"Xác nhận / Approval: Nội dung này là dữ liệu giả lập, không phải hồ sơ doanh nghiệp.",size=9)


def flowchart(s):
    s.header("QUY TRÌNH THỰC HIỆN / WORKFLOW", "QP-74-02")
    s.text("Lưu đồ vector gồm text, hình khối và mũi tên; không có một ảnh nhúng tương ứng.",38,137,519,9)
    x, y = [38,218,287,465,557], [174,215,330,445,560,675]
    table = s.add("table", [38,174,557,675], rows=5, cols=4,
                  grid_policy="partial_layout_grid", note="Do not infer a rowspan for the left diagram region. Row cells are explicit only in columns 1-3.")
    for j,t in enumerate(["Lưu đồ", "Trách nhiệm", "Diễn giải", "Biểu mẫu"]):
        s.cell(table,[x[j],y[0],x[j+1],y[1]],0,j,t,header=True)
    s.rect([38,215,218,675])
    region = s.add("container", [38,215,218,675],table,role="diagram_column")
    descriptions = [
        ("Sản xuất", "Tiếp nhận thiết bị. Kiểm tra mã, tem hiệu chuẩn và tình trạng bên ngoài.", "QP-74-02-F6"),
        ("Kỹ thuật", "Đo thông số theo hướng dẫn. Ghi nhận nhiệt độ 20-25 °C và mã QC-017.", "HD-74-01"),
        ("QA", "Đối chiếu tiêu chí. Nếu không đạt: cách ly và lập phiếu xử lý sai lệch.", "NC-01"),
        ("QA / Kho", "Phê duyệt thiết bị đạt yêu cầu. Cập nhật danh mục và lưu hồ sơ.", "DM-THIETBI"),
    ]
    for r, row in enumerate(descriptions, 1):
        for j,t in enumerate(row,1):
            s.cell(table,[x[j],y[r],x[j+1],y[r+1]],r,j,t,size=8.6)
    diagram = s.add("diagram",[48,231,208,650],region,representation="vector_paths_and_text",
                    overlaps_row_intervals=[1,2,3,4],recognition_policy="atomic_asset_with_internal_text_metadata")
    def node(box,label,diamond=False):
        if diamond:
            a,b,c,d=box
            p=s.c.beginPath(); p.moveTo((a+c)/2,H-b); p.lineTo(c,H-(b+d)/2)
            p.lineTo((a+c)/2,H-d); p.lineTo(a,H-(b+d)/2); p.close()
            s.c.setFillColor(LIGHT); s.c.setStrokeColor(BLUE); s.c.drawPath(p,fill=1,stroke=1)
        else:
            s.rect(box,fill=LIGHT,stroke=BLUE,width=.9)
        tx=(box[0]+box[2]-pdfmetrics.stringWidth(label,"Body",8.7))/2 if diamond else box[0]+12
        ty=(box[1]+box[3])/2-5 if diamond else box[1]+9
        s.text(label,tx,ty,box[2]-box[0]-24,8.7,
               parent=diagram,role="diagram_label",recognition_target=False)
    node([77,235,193,272],"Tiếp nhận thiết bị")
    node([77,316,193,356],"Kiểm tra / Đo")
    node([70,401,200,464],"Đạt yêu cầu?",True)
    node([77,521,193,562],"Phê duyệt, lưu hồ sơ")
    node([77,612,193,649],"Kết thúc")
    for a,b in [(272,316),(356,401),(464,521),(562,612)]:
        s.arrow([(135,a),(135,b)])
    s.arrow([(70,432),(51,432),(51,336),(77,336)])
    s.text("Không",52,387,47,7.6,parent=diagram,role="diagram_label",recognition_target=False)
    s.text("Có",144,482,34,8,parent=diagram,role="diagram_label",recognition_target=False)
    s.text("Ghi chú: Sơ đồ chạy liên tục qua các khoảng hàng bên phải; không suy ra quan hệ 1:1.",38,702,519,9)


def nested(s, asset):
    s.header("BIỂU MẪU KIỂM TRA VÀ HƯỚNG DẪN", "QP-74-02-F6")
    s.text("Một ô chứa text, ảnh raster và sơ đồ vector. Phần hướng dẫn phía dưới là vùng scan.",38,137,519,9)
    table=s.add("table",[38,174,557,494],rows=3,cols=2,grid_policy="complete")
    s.cell(table,[38,174,166,214],0,0,"Hạng mục",header=True)
    s.cell(table,[166,174,557,214],0,1,"Thông tin / Minh họa",header=True)
    s.cell(table,[38,214,166,434],1,0,"Thiết bị và thao tác\nEquipment & action",size=9)
    cell=s.cell(table,[166,214,557,434],1,1)
    s.text("Đối chiếu nhãn QC-017 trước khi kết nối nguồn.",177,226,366,9,parent=cell)
    box=[177,267,380,369]
    s.add("image",box,cell,representation="embedded_raster",expected_label_text="QC-017; THIẾT BỊ MẪU; 0/O - 1/I")
    s.c.drawImage(ImageReader(asset),box[0],H-box[3],box[2]-box[0],box[3]-box[1])
    diagram=s.add("diagram",[404,263,542,393],cell,representation="vector_paths_and_text")
    for box,label in [([409,267,539,303],"Kiểm tra nhãn"),([409,353,539,389],"Kết nối nguồn")]:
        s.rect(box,fill=LIGHT,stroke=BLUE)
        s.text(label,box[0]+10,box[1]+10,110,8.8,parent=diagram,role="diagram_label",recognition_target=False)
    s.arrow([(474,303),(474,353)])
    s.text("Ảnh và sơ đồ là hai thành phần độc lập trong cùng ô.",177,407,366,8.5,parent=cell)
    s.cell(table,[38,434,166,494],2,0,"Kết quả",size=9)
    s.cell(table,[166,434,557,494],2,1,"Đạt / Không đạt: __________\nNgười kiểm tra: Nguyễn Thị Mỹ",size=9)
    region=s.add("container",[38,531,557,729],role="scan_insert_region")
    s.text("4. Hướng dẫn an toàn / Safety instructions",49,545,495,11,True,parent=region,kind="heading",level=2)
    s.text("Ngắt nguồn trước khi vệ sinh. Không sử dụng khi dây dẫn bị hở hoặc vỏ máy nứt. "
           "Thông báo ngay cho bộ phận Kỹ thuật nếu phát hiện bất thường.",49,578,495,10,parent=region)
    s.text("Disconnect power before cleaning. Record the issue in QP-74-02-F6. "
           "Do not release equipment until QA has approved the corrective action.",49,639,495,10,parent=region)
    s.text("Hotline nội bộ (giả lập): 028-0000-017 | Revision 03",49,704,495,9,parent=region)
    s.rect([38,531,557,729],stroke="#8195A4")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render_image(page,dpi=160):
    pix=page.get_pixmap(dpi=dpi,alpha=False)
    return Image.frombytes("RGB",[pix.width,pix.height],pix.samples)


def raster_pdf(pages,path):
    c=canvas.Canvas(str(path),pagesize=(W,H),invariant=1)
    c.setTitle("Synthetic SOP extraction fixture - image-only")
    for im in pages:
        c.drawImage(ImageReader(im),0,0,W,H)
        c.showPage()
    c.save()


def generate(font_dir=None):
    regular,bold=fonts(font_dir)
    OUT.mkdir(parents=True,exist_ok=True)
    preview=OUT/"previews"; preview.mkdir(exist_ok=True)
    asset=photo(regular)
    digital=OUT/"sop_digital.pdf"
    c=canvas.Canvas(str(digital),pagesize=(W,H),invariant=1)
    c.setTitle("Synthetic SOP extraction fixture - Vietnamese / English")
    annotations=[]
    for page,draw in enumerate([lambda s:basic(s,asset),history,flowchart,lambda s:nested(s,asset)],1):
        scene=Scene(c,page); draw(scene)
        annotations.append(dict(page_number=page,width=W,height=H,components=scene.items))
        c.showPage()
    c.save()
    source=fitz.open(digital)
    clean=[render_image(p) for p in source]
    raster_pdf(clean,OUT/"sop_scan_clean.pdf")
    degraded=[]
    for i,im in enumerate(clean):
        im=im.convert("L")
        # Geometry is intentionally preserved, so paired labels remain valid.
        im=ImageEnhance.Contrast(im).enhance(.67).filter(ImageFilter.GaussianBlur(.38))
        d=ImageDraw.Draw(im); rng=random.Random(7402+i)
        for _ in range(2400):
            x,y=rng.randrange(im.width),rng.randrange(im.height)
            d.point((x,y),fill=rng.randrange(135,245))
        b=io.BytesIO(); im.save(b,format="JPEG",quality=48)
        degraded.append(Image.open(io.BytesIO(b.getvalue())).convert("RGB"))
    raster_pdf(degraded,OUT/"sop_scan_degraded.pdf")
    hybrid=fitz.open()
    hybrid.insert_pdf(source,from_page=0,to_page=0)
    page=hybrid.new_page(width=W,height=H)
    b=io.BytesIO(); clean[1].save(b,format="PNG")
    page.insert_image(page.rect,stream=b.getvalue())
    hybrid.insert_pdf(source,from_page=2,to_page=3)
    scan_box=fitz.Rect(38,531,557,729)
    pix=source[3].get_pixmap(dpi=160,clip=scan_box,alpha=False)
    hybrid[3].add_redact_annot(scan_box,fill=(1,1,1))
    hybrid[3].apply_redactions()
    hybrid[3].insert_image(scan_box,stream=pix.tobytes("png"))
    hybrid.save(OUT/"sop_hybrid.pdf",garbage=4,deflate=True)
    hybrid.close()
    fixtures=[]
    for name,types in [
        ("sop_digital.pdf",["digital"]*4),
        ("sop_scan_clean.pdf",["scan"]*4),
        ("sop_scan_degraded.pdf",["scan_degraded"]*4),
        ("sop_hybrid.pdf",["digital","scan","digital","hybrid"]),
    ]:
        path=OUT/name
        gt=copy.deepcopy(annotations)
        for p,t in zip(gt,types):
            p["source_kind"]=t
            for item in p["components"]:
                if t.startswith("scan"):
                    item["rendered_representation"]="page_raster"
                elif t=="hybrid" and item["bbox"][1]>=531 and item["bbox"][3]<=729:
                    item["rendered_representation"]="scan_insert"
                else:
                    item["rendered_representation"]=item.get("representation","native_text_or_geometry")
        payload=dict(annotation_version="fixture-1",synthetic=True,source_pdf=name,
                     sha256=digest(path),coordinate_system="pdf_points_top_left_unrotated",
                     policy="authoring-derived visible semantic regions; not a product export schema",
                     pages=gt)
        (OUT/(path.stem+".ground_truth.json")).write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
        doc=fitz.open(path)
        for i,p in enumerate(doc):
            render_image(p,100).save(preview/f"{path.stem}_p{i+1}.png")
        fixtures.append(dict(file=name,sha256=digest(path),pages=len(doc),page_types=types))
        doc.close()
    source.close()
    manifest=dict(synthetic=True,seed=7402,fixtures=fixtures,
                  generation_versions={"pymupdf":fitz.VersionBind,
                      "reportlab":__import__("reportlab").Version,"pillow":Image.__version__,
                      "pypdf":__import__("pypdf").__version__},
                  fonts={"regular_sha256":digest(regular),"bold_sha256":digest(bold)},
                  limitations=["4 independent page designs, 16 paired pages; not 16 independent samples",
                               "No representative real-world accuracy estimate",
                               "No deskew, perspective, watermark, multi-page table, or hidden OCR layer case yet",
                               "Ground truth is authoring intent; inspect overlays before scoring models"])
    (OUT/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"Created 4 PDFs / 16 paired pages in {OUT}")


def verify():
    report=[]
    for path in sorted(OUT.glob("sop_*.pdf")):
        gt=json.loads(path.with_suffix(".ground_truth.json").read_text(encoding="utf-8"))
        doc=fitz.open(path)
        native=[len(p.get_text().strip()) for p in doc]
        assert len(doc)==4 and gt["sha256"]==digest(path)
        pypdf_chars=[len(p.extract_text().strip()) for p in PdfReader(path).pages]
        if "scan_" in path.stem:
            assert native==[0]*4 and pypdf_chars==[0]*4
            reader=PdfReader(path)
            for page in reader.pages:
                operations=ContentStream(page.get_contents(),reader).operations
                assert not any(op in {b"Tj",b"TJ",b"'",b'"'} for operands,op in operations), "Scan fixture contains text-show operators"
                resources=page["/Resources"]
                xobjects=list(resources["/XObject"].values())
                assert len(xobjects)==1 and xobjects[0].get_object()["/Subtype"]=="/Image"
        if path.stem=="sop_digital":
            assert all(n>300 for n in native)
            assert "QP-74-02-F6" in doc[0].get_text()
            assert "Nguyễn" in doc[1].get_text()
            assert len(doc[2].get_images())==0, "Vector flowchart must not be an embedded image"
            assert len(doc[2].get_drawings())>25
        if path.stem=="sop_hybrid":
            assert native[0]>300 and native[1]==0 and native[2]>300 and native[3]>300
            assert "Disconnect power" not in doc[3].get_text(), "Hybrid insert leaked hidden native text"
        for pg in gt["pages"]:
            items=pg["components"]; ids={it["id"] for it in items}
            assert len(ids)==len(items)
            byid={it["id"]:it for it in items}
            for it in items:
                a,b,c,d=it["bbox"]
                assert 0<=a<c<=W and 0<=b<d<=H,it
                if it["parent_id"]:
                    parent=byid[it["parent_id"]]
                    pa,pb,pc,pd=parent["bbox"]
                    assert a>=pa-.5 and b>=pb-.5 and c<=pc+.5 and d<=pd+.5,(it,parent)
            for table in [it for it in items if it["type"]=="table" and it.get("grid_policy")=="complete"]:
                occupied=set()
                for cell in [it for it in items if it["parent_id"]==table["id"] and it["type"]=="table_cell"]:
                    for r in range(cell["row"],cell["row"]+cell["rowspan"]):
                        for col in range(cell["col"],cell["col"]+cell["colspan"]):
                            assert (r,col) not in occupied
                            assert r<table["rows"] and col<table["cols"]
                            occupied.add((r,col))
                assert len(occupied)==table["rows"]*table["cols"]
            page=doc[pg["page_number"]-1]
            pix=page.get_pixmap(dpi=100,alpha=False)
            im=Image.frombytes("RGB",[pix.width,pix.height],pix.samples)
            draw=ImageDraw.Draw(im); scale=pix.width/W
            colors={"table":"#D93333","table_cell":"#DBA800","diagram":"#C02EC7","image":"#00A366"}
            for it in items:
                if it["type"] in colors:
                    draw.rectangle([round(v*scale) for v in it["bbox"]],outline=colors[it["type"]],width=2)
            im.save(OUT/"previews"/f"{path.stem}_p{pg['page_number']}_overlay.png")
        report.append(dict(file=path.name,native_text_chars=native,pypdf_text_chars=pypdf_chars,
                           checks="passed: source hash, page count, bounds, parent containment, complete-grid occupancy, PDF modality"))
        doc.close()
    (OUT/"validation.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))


if __name__=="__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("--font-dir"); ap.add_argument("--verify-only",action="store_true")
    args=ap.parse_args()
    if not args.verify_only:
        generate(args.font_dir)
    verify()
