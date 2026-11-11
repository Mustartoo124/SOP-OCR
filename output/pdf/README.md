# Bộ SOP giả lập cho thử nghiệm extraction

Đây là dữ liệu tổng hợp, không phải tài liệu doanh nghiệp hoặc benchmark accuracy trên SOP thực.
Mục tiêu hiện tại: kiểm tra việc tìm đủ thành phần, nhận đúng bảng/ô gộp, tách hình/sơ đồ và định vị trên trang.
Các nhãn JSON ở đây chỉ phục vụ kiểm thử; chưa chốt schema đầu ra sản phẩm.

Kiểm tra lại hai file scan: xem [báo cáo cấu trúc PDF](SCAN_AUDIT.md) và [kết quả audit](scan_audit.json). Việc chọn/copy được chữ trong trình xem có OCR không chứng minh file có text layer; hai file hiện tại chứa ảnh trang và không có lệnh vẽ chữ.

## Các file

| PDF | Nội dung |
|---|---|
| `sop_digital.pdf` | 4 trang có native text, vector graphics và ảnh raster nhúng |
| `sop_scan_clean.pdf` | Cùng 4 trang, rasterize 160 DPI, không có text layer |
| `sop_scan_degraded.pdf` | Cùng 4 trang, giảm tương phản, blur nhẹ, nhiễu điểm và JPEG |
| `sop_hybrid.pdf` | Trang 1/3 digital, trang 2 scan, trang 4 digital chứa vùng scan không có hidden text |

Đây là **4 thiết kế trang độc lập, với 16 trang ở các biến thể tương ứng**. Không tính chúng là 16 mẫu độc lập.

1. Text Việt/Anh, heading, danh sách, logo vector, ảnh thiết bị raster có chữ và caption.
2. Bảng lịch sử 6 cột, nhiều dòng, ô gộp dọc/ngang, mã SOP, dấu tiếng Việt, chữ xoay.
3. Bảng bố cục có lưu đồ vector liên tục qua các khoảng hàng mô tả. Sơ đồ không có embedded image riêng.
4. Một ô chứa text, ảnh raster và sơ đồ vector riêng; bên dưới có khối hướng dẫn làm scan insert ở bản hybrid.

## Nhãn chuẩn và kiểm tra

Mỗi PDF có file `.ground_truth.json`, cùng page number và bbox `[x0, y0, x1, y1]` theo PDF points, gốc trên trái, trang không xoay.
Nhãn được ghi trực tiếp trong lúc tạo tài liệu, không được suy ra từ parser đang thử nghiệm.

- `text`, `heading`, `list_item`, `caption`, `table`, `table_cell`, `image`, `diagram`, `container`.
- Mỗi ô gộp chỉ có một nhãn; `rowspan/colspan` và grid occupancy được kiểm tra.
- Chữ trong diagram/logo được lưu dưới parent với `recognition_target: false`; không coi là paragraph độc lập.
- Ảnh raster có `expected_label_text` để đối chiếu chữ bên trong; chưa có bbox chữ con cấp pixel.
- Trang 3 dùng `grid_policy: partial_layout_grid`: chỉ gán ô chắc chắn ở các cột mô tả. Vùng lưu đồ là container; không tự khẳng định rowspan hoặc liên hệ nghiệp vụ 1:1.
- Các bbox là vùng nội dung theo ý đồ tác giả, không phải segmentation mask hay biên glyph chính xác.
- `manifest.json` lưu hash, biến thể trang, version thư viện và hạn chế.
- `validation.json` là kiểm tra tính toàn vẹn của bộ mẫu, **không phải kết quả accuracy extraction**.
- `previews/` có bản render và overlay: đỏ=bảng, vàng=ô, tím=sơ đồ, xanh lá=hình.

Scan suy giảm hiện giữ nguyên hình học nên dùng chung tọa độ chuẩn. Chưa có skew, perspective, watermark, bảng xuyên trang, text layer OCR sai hoặc nhiều họ template. Các trường hợp này cần thêm trước khi đánh giá rộng hơn. Không đưa các bản digital/scan của cùng một trang vào hai nhóm train/test khác nhau.

## Tái tạo

Từ thư mục gốc repo, Python 3.11+:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-fixtures.txt
.\.venv\Scripts\python.exe scripts/generate_sop_fixtures.py
.\.venv\Scripts\python.exe scripts/generate_sop_fixtures.py --verify-only
.\.venv\Scripts\python.exe scripts/inspect_native.py
.\.venv\Scripts\python.exe scripts/audit_scan_pdfs.py
```

macOS/Linux dùng `.venv/bin/python`. Script tự tìm Arial trên Windows/macOS hoặc DejaVu Sans trên Linux; có thể truyền `--font-dir`. Scan sạch/suy giảm được tạo từ bản render của digital; hybrid thay vùng hướng dẫn bằng raster sau khi loại native text trong vùng.

## Hướng thử nghiệm trên hạ tầng hiện có

- Windows CPU / 32 GB RAM: tạo mẫu, kiểm tra native geometry, text, crop và thử baseline nhỏ.
- MacBook M4 / 24 GB unified memory: có thể thử CPU; chỉ dùng MPS/Metal cho module/backend đã xác nhận hỗ trợ. Không giả định mọi model đều tận dụng GPU.
- JupyterHub / NVIDIA T4: môi trường ưu tiên thử model CUDA nặng hơn; kiểm tra VRAM và phiên bản runtime thực tế trước khi chọn batch/model.

`inspect_native.py` ghi text/word boxes, số raster occurrences, vector paths và table candidates bằng PyMuPDF vào `diagnostics/`. Script không đọc ground truth và không chạy OCR hay nhận diện diagram; kết quả chỉ mô tả giới hạn của native extraction.

Lần kiểm tra tạo mẫu đầu tiên: PyMuPDF tìm table candidate 8x6 ở trang lịch sử và 5x4 ở trang lưu đồ digital. Trang lưu đồ có 42 vector paths và 0 raster occurrences; việc tìm ra table không đồng nghĩa đã tách được diagram. Các trang scan có 0 native text và không có table candidates. Bản hybrid có lần lượt 847, 0, 862, 579 ký tự native theo trang. Tất cả 16 trang đã được render độc lập bằng Poppler 26.09.0 và kiểm tra trực quan; các overlay được tạo bằng PyMuPDF để đối chiếu nhãn.

Bước tiếp theo phù hợp là chạy Docling và PP-StructureV3 độc lập trên bộ mẫu này, giữ raw output và overlay từng thành phần. Chấm riêng độ đầy đủ text, cấu trúc ô gộp, vùng diagram/crop và nested association. Chưa có baseline model OCR/layout nào được chạy trong lần tạo mẫu này.
