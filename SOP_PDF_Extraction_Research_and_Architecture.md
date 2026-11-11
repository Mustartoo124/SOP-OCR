# SOP Document Extraction & Human-in-the-Loop Review

**Research background, technical options, architectural considerations, and evaluation framework**  
**Document focus:** PDF-first, extensible to DOCX/XLSX and other document sources  
**Language:** Vietnamese  
**Document date:** 2026-11-11  
**Document status:** Technical reference and design exploration, **not an implementation directive**

> **Mục đích sử dụng:** Tài liệu này tập hợp đề bài, phạm vi, các nhận định nghiên cứu, kiến trúc tham khảo, mô hình dữ liệu và phương án đánh giá để con người hoặc Coding Agent có thể hiểu đầy đủ ngữ cảnh. Mọi phương pháp, công cụ, thứ tự thử nghiệm và lựa chọn kiến trúc trong tài liệu đều là **phương án tham khảo**. Tài liệu **không giao nhiệm vụ**, không yêu cầu viết code, chạy lệnh, cài đặt, tải model hay thực thi một quy trình cụ thể. Quyết định thực hiện thuộc về người phụ trách dự án.

---

## 1. Business context và mục tiêu bài toán

### 1.1. Bối cảnh

Đầu vào của hệ thống là tài liệu SOP (Standard Operating Procedure) và các tài liệu quy trình liên quan. Tài liệu có thể tồn tại ở nhiều định dạng như PDF, DOCX, XLSX; phạm vi nghiên cứu hiện tại **ưu tiên PDF**. File PDF có thể thuộc dạng digital (có text layer và graphics objects), scan (hình ảnh của trang giấy) hoặc hybrid (pha trộn text/image, thậm chí khác nhau theo từng trang). Nguồn gốc PDF hỗn hợp: chuyển đổi từ ứng dụng văn phòng, công cụ xây dựng diagram hoặc scan tài liệu.

Một trang SOP có thể chứa đoạn văn, heading, danh sách, hình ảnh, bảng, hình vẽ kỹ thuật, flowchart, logo, chữ xoay, header/footer và các thành phần lồng nhau. Các hình có thể bắt nguồn từ SVG, PNG, VSD/VSDX hoặc định dạng khác ở tài liệu nguồn, nhưng **không thể mặc định PDF vẫn giữ được tệp nguồn gốc**: vector graphics có thể đã được chuyển thành PDF drawing operations, và đối tượng raster có thể đã được mã hóa lại thành image XObject.

### 1.2. Mục tiêu chức năng cuối cùng

Hệ thống được hình dung gồm các năng lực logic:

1. **Document ingestion:** tiếp nhận một tài liệu, xác định loại đầu vào và đặc điểm theo trang.
2. **Extraction và document understanding:** xác định các thành phần độc lập gồm text, image, diagram, table và thành phần con; trích xuất nội dung và cấu trúc cần thiết.
3. **Grounding trên tài liệu gốc:** lưu page number và bounding box để đánh dấu đúng thành phần trên trình xem tài liệu.
4. **Human-in-the-loop review:** người dùng xem nội dung đã trích xuất, sửa text, thay thế/xóa hình và diagram, chỉnh text trong ô bảng, kiểm tra quan hệ lồng nhau và phê duyệt kết quả.
5. **Structured output:** xuất một JSON thống nhất, có thể sử dụng ở downstream system, với asset hình ảnh tham chiếu riêng nếu cần.

**Đây không phải bài toán OCR đơn thuần**, cũng không phải yêu cầu PDF-to-Markdown. Chất lượng được hiểu là khả năng phân tách chính xác thành phần, bảo toàn cấu trúc, định vị được trên trang, cho phép chỉnh sửa và chuyển thành JSON sau review.

### 1.3. Phạm vi và yêu cầu đã được xác nhận

| Khía cạnh | Yêu cầu xác nhận |
|---|---|
| Loại PDF | Cả digital PDF và scanned PDF; có thể là hybrid |
| Nguồn PDF | Hỗn hợp; không giả định chỉ chuyển từ Office |
| Ngôn ngữ | Tiếng Việt và tiếng Anh |
| Diagram / flowchart | Phát hiện vùng, trích xuất thành ảnh riêng để xem, xóa hoặc thay thế; **không cần** chỉnh sửa node/mũi tên |
| Table | Sửa text ở từng ô; xóa bảng; xóa/thay hình hoặc diagram trong bảng |
| Vector | Có thể rasterize; không yêu cầu giữ định dạng vector gốc |
| Position | Bounding box cho **mọi** thành phần có thể nhận diện |
| Nested components | **Quan trọng**: bảng chứa text/image/diagram và các cấu trúc lồng nhau |
| Runtime | Ưu tiên phần mềm chạy local/self-hosted, không phụ thuộc API OCR/AI từ xa |
| Thiết bị/OS | Phương án không bị ràng buộc vào macOS, Windows hoặc Linux; có thể đánh giá CPU/GPU tùy hạ tầng |
| Ưu tiên tối ưu | Chất lượng trích xuất/cấu trúc trước tốc độ |
| Data schema | JSON schema tùy chỉnh, độc lập framework |
| Phạm vi nghiên cứu | So sánh công cụ + kiến trúc + các hướng thử nghiệm/đánh giá |

**Diễn giải về local/open-source:** Công cụ/mô hình có thể được tải và triển khai trên hạ tầng tự quản; xử lý tài liệu không cần gửi qua remote inference API. Khả năng offline hoàn toàn và điều khoản sử dụng thương mại cần kiểm tra riêng theo công cụ, model weights, dependency và deployment configuration. “Có source code công khai” không đồng nghĩa với “mọi model weights đều có giấy phép permissive”.

### 1.4. Ngoài phạm vi hiện tại

- Phục hồi diagram thành cấu trúc node/edge có thể chỉnh sửa chi tiết.
- Khôi phục chắc chắn định dạng gốc của hình ảnh/diagram (ví dụ biến PDF drawing trở lại SVG hay Visio gốc).
- Xuất ngược tài liệu đã sửa thành PDF/DOCX giữ nguyên layout 100%.
- Trích xuất business entity cụ thể hoặc quy tắc nghiệp vụ sau khi JSON đã được tạo.
- Dùng một framework duy nhất bằng mọi giá.

Các mục này có thể được xem là hướng mở rộng, không phải điều kiện thành công của nghiên cứu PDF-first.

---

## 2. Đặc điểm SOP mẫu và các failure modes

### 2.1. Mẫu A — Trang lịch sử tài liệu

Tài liệu minh họa có header công ty, metadata tài liệu, logo, bảng lịch sử phát hành rất lớn, nhiều cột/hàng, ô gộp theo chiều dọc/ngang, text nhiều dòng, nội dung màu khác nhau, phần chữ xoay dọc, vị trí có thể chồng lên nhau hoặc có annotation/watermark. Những thách thức:

- Phát hiện ranh giới bảng đủ chính xác, gồm cả các cell border mảnh.
- Xác định đúng ô gộp `rowspan`/`colspan`; tránh tạo ô ảo/lặp text từ vùng ô đã merge.
- Không làm sai thứ tự đọc khi text trải trên nhiều dòng/ô.
- Phân biệt chữ trong bảng với chữ header/footer/watermark hoặc text xoay.
- Bảo toàn tiếng Việt có dấu và các mã SOP như `QP-74-02-F6`.
- Cho phép review text trong từng ô mà không đánh mất cấu trúc bảng.

### 2.2. Mẫu B — Trang quy trình thực hiện

Trang minh họa chứa một **bảng nhiều cột đóng vai trò bố cục**, trong đó cột “Lưu đồ” có flowchart gồm các hình khối, mũi tên và các nhánh. Các cột bên cạnh chứa mô tả chi tiết, trách nhiệm, thời gian và biểu mẫu liên quan. Những thách thức:

- Một vùng lớn có thể là table về mặt layout, nhưng một cột chứa diagram liên tục qua nhiều hàng.
- Flowchart có thể được tạo từ nhiều PDF vector drawing operations, không có một embedded image duy nhất.
- Các hình chữ nhật trong flowchart dễ nhầm với đường kẻ table grid.
- OCR có thể coi chữ bên trong node là paragraph độc lập, gây **duplicate content** nếu diagram cũng được xuất dưới dạng ảnh.
- Một diagram có thể có bbox cắt qua nhiều cell về mặt hình học. Không nên gán cứng cho một cell nếu không đủ bằng chứng.
- Các vùng mô tả chi tiết và sơ đồ có liên hệ về vị trí, nhưng không nhất thiết tương ứng 1:1 với hàng của bảng.

### 2.3. Các lớp khó khác

- PDF không có text layer hoặc text layer sai/ẩn.
- Trang bị xoay; ảnh scan bị nghiêng, bóng, nhiễu, mờ.
- OCR nhầm `0/O`, `1/I`, dấu tiếng Việt hoặc ký tự nối trong mã tài liệu.
- Biểu mẫu có nhiều đường kẻ và vùng text rất nhỏ.
- Bảng bị chia nhiều trang, thiếu header ở trang sau.
- Hình/diagram giao với bảng, watermark hoặc ghi chú.
- PDF digital có cùng đối tượng image xuất hiện nhiều lần thông qua reference/transform khác nhau.
- Diagram được tạo từ text và vector path, không thể tách bằng image extraction API đơn giản.
- Có text từ furniture layer (header/footer) nhưng không thuộc luồng đọc chính.
- Mất các thành phần khi parser chỉ xuất Markdown thay vì raw structured output.

---

## 3. Phân biệt các loại extraction

| Năng lực | Định nghĩa | Quan hệ với yêu cầu |
|---|---|---|
| Native PDF text extraction | Đọc text layer, glyph/word/span và tọa độ | Quan trọng với digital PDF |
| OCR | Nhận dạng text từ pixel image | Bắt buộc với scan hoặc vùng hình chứa chữ cần OCR |
| Layout analysis | Phân vùng text/table/figure/header/... trên trang | Cốt lõi để có bbox và type |
| Table detection | Xác định vùng table | Chưa đủ để sửa từng ô |
| Table structure recognition | Khôi phục row, column, merged cells, cell geometry | Cốt lõi cho cell-level editing |
| Embedded image extraction | Lấy raster image objects được nhúng | Hữu ích nhưng không bao phủ vector diagram |
| Diagram region detection | Khoanh vùng toàn bộ sơ đồ, dù raster hay vector | **Bắt buộc theo yêu cầu** |
| Region rasterization/cropping | Render vùng đã chọn thành PNG | Cách biểu diễn diagram phù hợp |
| Structural diagram reconstruction | Khôi phục nodes, edges, labels | Không yêu cầu |
| Reading order reconstruction | Xác định luồng nội dung hợp lý | Quan trọng với downstream JSON |
| Nested component association | Gán text/image/diagram vào table/cell/container | **Bắt buộc theo yêu cầu** |

**Định nghĩa thành công với diagram:** Một vùng diagram được phát hiện đầy đủ, có bbox đúng trên tài liệu gốc, được xuất thành asset raster rõ nét, liên kết với parent/container hợp lý và cho phép người review thay/xóa. Đây không đồng nghĩa với việc hiểu ý nghĩa từng node hoặc mỗi mũi tên.

---

## 4. Thông tin tham chiếu từ thử nghiệm DOCX bằng Docling

Nội dung dưới đây là **bối cảnh tham khảo**, không phải blueprint bắt buộc cho PDF. Dữ liệu do người phụ trách cung cấp dựa trên code và file output đã tồn tại; thử nghiệm này không được khẳng định là đã chạy lại.

### 4.1. Luồng tham khảo

Một script `run_docling.py` nhận `.docx` và `.pdf`, gọi `DocumentConverter().convert(path)` của Docling 2.130.0 và ghi các file đầu ra:

- `document.json`: cây `DoclingDocument` với `texts`, `tables`, `pictures`, `groups`, `body`.
- `document.md`: Markdown export.
- `document.doctags`: định dạng token layout.
- `summary.json`: đếm thành phần và nhãn.

Đối với DOCX, parser khai thác cấu trúc Office gốc, không nhất thiết chạy OCR hay visual layout model như PDF. Do đó **không thể ngoại suy độ chính xác và bbox của DOCX sang PDF**.

### 4.2. Quan sát từ DOCX

- Text/heading/list được ghi trong `texts[]` và `groups[]` theo label.
- Table có `table_cells`, `row_span`, `col_span`, hàng/cột.
- Picture có item riêng nhưng nội dung hình chưa được OCR mô tả.
- Header/footer thuộc `content_layer: furniture`.
- `prov` của file DOCX được quan sát là rỗng, nên không có page/bbox hữu dụng để highlight vị trí trong Word gốc.
- Có rủi ro list item bị bỏ sót, chỉ được phản ánh trong terminal warning.

Một output tham khảo của tài liệu `QP-75-01` có `texts: 81`, `tables: 5`, `pictures: 2`; các label đếm được `text: 47`, `list_item: 22`, `table: 3`, `picture: 1`. Chênh lệch liên quan đến những mục ở furniture layer; đây **không phải số đo chất lượng trích xuất**.

### 4.3. Giao diện review tham khảo

UI HTML mẫu có khả năng relabel text, sửa heading level, di chuyển/gộp/thêm text, sửa text trong table cells, toggle column header, di chuyển bảng, caption/decorative cho picture, restore orphan blocks; thông tin được ghi vào `document.reviewed.json` và `edits.log.jsonl` với reviewer, timestamp, before/after. Giới hạn đã thấy:

- Không sửa trực tiếp nội dung paragraph thông thường.
- Không có undo/redo tương tác hoàn chỉnh.
- Không cập nhật Markdown export sau review.
- Chưa có reviewed human-readable export tự động.
- Có nguy cơ file output cũ còn tồn tại nếu conversion mới thất bại.

**Bài học kiến trúc:** Phân biệt immutable raw result, reviewed state, edit history và final export. PDF review cần bboxes và page image overlay; schema/UI không nên bị khóa vào `DoclingDocument`.

---

## 5. Tổng hợp công cụ và hướng nghiên cứu

> **Tính chất thông tin:** Đây là tổng hợp khả năng được công bố trong tài liệu dự án/công cụ và các nhận định thiết kế, **không phải benchmark đã thực hiện trên tài liệu SOP thực tế**. API, tên model, backend hỗ trợ và licensing có thể thay đổi theo phiên bản; ngày tra cứu trong quá trình nghiên cứu là tháng 11/2026. Link tài liệu chính thức ở cuối file.

### 5.1. Bảng đối chiếu

| Công cụ / nhóm | Giá trị tiềm năng | Giới hạn/rủi ro với SOP | Vai trò có thể xem xét |
|---|---|---|---|
| **Docling** | PDF parsing, layout, OCR integration, table structure, structured document JSON, provenance | Flowchart trong cell có thể bị chia nhỏ; bảng phức tạp và nested relation cần kiểm chứng | Parser cấu trúc chính hoặc baseline |
| **PaddleOCR PP-StructureV3** | OCR, document layout, table recognition, table HTML/cell geometry, modular processing | Reading order/parent-child, language/config và backend compatibility cần xác nhận trên môi trường cụ thể | Layout-first alternative |
| **MinerU** | End-to-end document parsing, structured outputs; các tính năng ảnh/bảng đang phát triển | Khác biệt JSON/schema, tài nguyên và license; cấu trúc cell-nested cần đo | Challenger và fallback candidate |
| **PyMuPDF** | PDF native text, embedded images, vector paths, page render/crop, coordinates | Không tự suy luận semantics của một flowchart | PDF geometry/native extraction utility |
| **pdfplumber** | Word/line/table geometry từ PDF, inspection | Giới hạn trên scan và bảng phức tạp | Digital table fallback/diagnostics |
| **Camelot** | Table extraction trên text-based PDF có grid phù hợp | Không phải OCR cho scan; giới hạn layout | Digital table fallback |
| **Surya** | OCR, layout, reading order, table recognition | Model/weights license và dạng output thay đổi theo version | OCR/layout/table challenger |
| **Table Transformer (TATR)** | Table detection/structure recognition | Cần ghép OCR/text vào cells; repository archived 2026 | Specialized table baseline/fallback |
| **Marker** | Document-to-structured-output/Markdown | Lỗi column ordering và table fidelity cần benchmark; không mặc định có geometry chi tiết mọi level | Converter challenger |
| **OpenCV / image processing** | Lines, contours, grouping, image pre/post-processing | Heuristic dễ nhầm table grid với diagram | Hỗ trợ diagram detection, scan cleanup |
| **PDF.js** | PDF display và tương tác overlay trong browser | Không phải parser OCR | Review frontend option |

### 5.2. Docling

**Khả năng đáng chú ý:** `StandardPdfPipeline`, `PdfPipelineOptions`, cấu hình OCR/table structure, page images/picture images, document layout/provenance, xuất `DoclingDocument` và JSON. Trong PDF, provenance/bboxes có thể được tạo tùy nội dung và cấu hình, khác với quan sát DOCX `prov` rỗng.

**Đề xuất về vai trò:** Một parser cấu trúc để phân tách text/table/picture và reading order. PyMuPDF có thể bổ sung native objects, page render và diagram crop. Điểm chưa được xác nhận là việc flowchart vector nằm trong table được đóng thành đúng **một** picture và được đặt đúng parent.

**Lưu ý:** Không có cơ sở để cho rằng mọi OCR engine tích hợp cho kết quả tiếng Việt giống nhau. Native text/OCR arbitration cần được kiểm tra bằng output thật, không mặc định lúc nào cũng lấy OCR.

### 5.3. PaddleOCR / PP-StructureV3

**Khả năng đáng chú ý:** Layout detection, OCR, table recognition, tiền xử lý hình ảnh, kết quả table có thể chứa HTML và thông tin hình học cell; các module liên quan có thể cấu hình và đánh giá độc lập.

**Đề xuất về vai trò:** Phân tích dựa trên ảnh trang (image-first), đặc biệt khi tài liệu scan. Với digital PDF, native-text recovery có thể giảm lỗi OCR nếu text layer đáng tin cậy.

**Điểm cần xác minh theo version:** mức chi tiết cell box, merged cells, nested figures, hệ ngôn ngữ OCR, format JSON/HTML, acceleration backend và package compatibility. Không đồng nhất “chạy được trên một thiết bị” với “mọi module đều tận dụng GPU trên thiết bị ấy”.

### 5.4. MinerU

**Khả năng đáng quan tâm:** Pipeline parse PDF với JSON/Markdown và các hướng nhận diện hình/bảng, bao gồm thông tin về image-in-table trong các phiên bản mới. Hữu ích làm challenger trên trang SOP phức tạp.

**Điểm cần xác minh:** output có đủ bbox ở cấp cell không, cách biểu diễn table/figure, nested relation, tài nguyên thực tế, khả năng self-host và điều khoản license của source/weights. Không coi các tuyên bố tính năng là bằng chứng accuracy trên SOP.

### 5.5. PyMuPDF

Các nhóm API có ích về mặt kỹ thuật:

- Text: text/words/blocks/dict và vị trí chữ.
- Image: tham chiếu và bytes ảnh nhúng, cùng placement trên page.
- Drawings: vector paths như line/rect/curve.
- Geometry: page dimensions, transforms, clip rectangles.
- Rendering: render cả trang hoặc vùng thành pixmap/PNG.
- Table recognition: các khả năng geometry-based trong một số phiên bản.

**Điểm cốt lõi:** Image extraction từ PDF chỉ lấy những image objects có sẵn. Flowchart được tạo từ path + text sẽ không xuất hiện như một image duy nhất; cần region detection và rasterization.

### 5.6. Specialized tools

- **Surya:** có thể so sánh OCR, layout và table recognition. Mã nguồn và weights có thể dùng điều khoản khác nhau; output geometry phải được xác minh với version cụ thể.
- **TATR:** có giá trị tham chiếu cho table structure metrics và cell detection. Không trực tiếp cung cấp OCR text đầy đủ trong từng ô; repository đã được lưu trữ (archived) năm 2026.
- **pdfplumber/Camelot:** có thể cho kết quả hữu ích trên bảng digital có đường kẻ; không thay thế OCR của scan.
- **Marker:** hữu ích để so sánh việc chuyển tài liệu thành structured text nhưng không phải mặc nhiên đáp ứng UI edit cell-level và diagram detection.

### 5.7. Chú ý về licensing và bảo mật

- Giấy phép source code, package phân phối, model weights và tài nguyên downstream có thể khác nhau.
- PyMuPDF có ràng buộc AGPL/commercial license tùy cách phân phối/sử dụng; cần review pháp lý.
- Một số model OCR/document understanding có usage terms riêng, không đồng nhất với repository license.
- “Local inference” vẫn có thể tải model, kiểm tra phiên bản, telemetry hoặc các remote resources khi khởi tạo. Khả năng **data stays on-premise** là thuộc tính của cấu hình triển khai thực tế.
- Không có yêu cầu loại trừ công cụ chỉ vì tên thương mại của tổ chức phát triển; tiêu chí chính là khả năng chạy local/self-hosted và phù hợp giấy phép.

---

## 6. Các kiến trúc giải pháp tham khảo

### 6.1. Common logical stages

```text
Source PDF
  |
  v
Document Preflight (page types, text layer, images, vector paths, metadata)
  |
  v
Parsing / Layout / OCR / Table Recognition
  |
  v
Native Object Recovery + Geometry Normalization + Deduplication
  |
  v
Component Segmentation + Nested Relationship Resolution
  |
  v
Table / Diagram Specialized Refinement
  |
  v
Normalized Component Graph + Raster Assets
  |
  v
Human Review State + Edit History
  |
  v
Final JSON + Referenced Assets
```

Đây là sơ đồ logic, **không phải thứ tự bắt buộc của code**; nhiều bước có thể chạy song song, đảo thứ tự hoặc không cần thiết trong một trường hợp cụ thể.

### 6.2. Phương án A — Native-aware parsing

**Thành phần tham khảo:** Docling + PyMuPDF + table/diagram refinement.

**Ý tưởng:** Tận dụng native PDF objects khi digital text đủ tin cậy, dùng Docling để phân vùng/ngữ nghĩa/tables, tổng hợp các kết quả trong một normalized component graph.

**Lợi ích tiềm năng:** chất lượng ký tự và tọa độ trên digital PDF; dùng sẵn table model; dễ trace về PDF gốc.

**Rủi ro:** native text và layout/OCR có thể trùng; geometry fusion có thể khó trên scan hoặc trang bị rotation; Docling picture classification không đảm bảo gom diagram chính xác.

### 6.3. Phương án B — Image-first parsing

**Thành phần tham khảo:** Page rendering + PP-StructureV3 + PyMuPDF native recovery + table/diagram refinement.

**Ý tưởng:** Mọi trang được nhìn dưới dạng ảnh cho layout/OCR/table. Những vùng digital có text layer đáng tin có thể được so khớp và phục hồi native text.

**Lợi ích tiềm năng:** một kiểu input hình ảnh nhất quán cho scan và digital; dễ hoán đổi OCR/layout/table models.

**Rủi ro:** tổn thất OCR không cần thiết trên digital PDF nếu bỏ qua native text; transform ảnh/PDF có thể lệch; table model cần chuyển đổi từ HTML và polygons/cell boxes.

### 6.4. Phương án C — Challenger / hybrid routing

**Thành phần tham khảo:** MinerU hoặc parser khác, dùng như đối chứng trên các page khó. Một hướng dài hạn là chọn parser theo page/region type (native digital, scan, complex table, diagram).

**Lợi ích:** giải quyết được các loại trang parser chính làm kém; giảm phụ thuộc một model.

**Rủi ro:** độ phức tạp vận hành và fusion tăng; nhiều model có thể tạo output mâu thuẫn; khó giải thích nếu không có provenance và evaluation.

### 6.5. Điểm chung giữa các phương án

- Cùng một **custom schema**.
- Có reference đến **source page và bbox**.
- Có representation cho **nested components**.
- Diagram xuất thành **raster asset** khi cần.
- Có review state tách khỏi raw extraction.
- So sánh bằng **cùng dataset/ground truth** thay vì cảm nhận chất lượng của Markdown output.

---

## 7. Thiết kế xử lý text và OCR

### 7.1. Preflight phân loại trang

Các tín hiệu hữu ích để mô tả trang:

- Text layer coverage và chất lượng chuỗi Unicode.
- Tỉ lệ vùng raster image phủ trang.
- Số lượng vector paths / drawing density.
- Phát hiện page rotation, skew, clipping hoặc độ phân giải ảnh.
- Mức độ trùng nhau giữa text layer và ảnh.

Trang digital/scan/hybrid có thể cần xử lý **theo vùng**, không phải chỉ theo file. Một trang digital vẫn có thể chứa hình scan với chữ bên trong.

### 7.2. Native text vs OCR

- Native text thường bảo toàn text chính xác trên digital PDF có encoding tốt, nhưng có thể sai thứ tự hoặc ký tự nếu font encoding bất thường.
- OCR xử lý pixels, có thể phục hồi chữ khi không có text layer nhưng nhạy với DPI, noise, font, dấu tiếng Việt và layout.
- Kết quả kết hợp có nguy cơ trùng text nếu không có deduplication.
- OCR vùng diagram có thể hữu ích làm metadata/search text, nhưng không nên tự động biến thành paragraph cấp cao nếu diagram đã được giữ dạng ảnh.

### 7.3. Text block model

Text component có thể chứa `plain_text`, `lines`, `spans`, `language`, `bbox`, `reading_order`, `source_method`, `confidence` (nếu model có cung cấp). Tách logical blocks (paragraph/list/heading) khỏi visual spans để người review chỉnh nội dung mà vẫn biết vị trí gốc.

---

## 8. Thiết kế xử lý bảng (tables)

### 8.1. Ba cấp độ khác nhau

1. **Table region:** xác định bounding rectangle/polygon.
2. **Table structure:** rows, columns, grid, merged cells, cell bboxes.
3. **Cell content:** text, text blocks, image/diagram references và nested containers.

Một parser chỉ trả Markdown table hoặc ảnh của toàn bộ bảng **chưa đáp ứng** nhu cầu sửa text từng ô và quản lý image/diagram trong bảng.

### 8.2. Cấu trúc dữ liệu bảng tham khảo

- `table`: `rows`, `cols`, `cell_ids`, `bbox`, layout/grid metadata.
- `table_cell`: `row`, `col`, `rowspan`, `colspan`, `bbox`, `child_ids`, text content khi phù hợp.
- `text` / `image` / `diagram` components được liên kết với cell bằng parent-child relation.
- Cell đại diện cho ô gộp **một lần**, không nhân bản text trong mỗi vị trí mà nó phủ.

### 8.3. Nested objects và ambiguous association

Một diagram có thể trải qua nhiều row trong một cột, hoặc các đường kẻ có thể là ranh giới flowchart chứ không phải grid table. Vì vậy có thể cần `container/region` nằm dưới `table` mà không gán cứng cho một cell khi thiếu bằng chứng. Cơ chế `needs_review` có ích hơn việc tạo quan hệ giả chính xác.

### 8.4. Những phương pháp bổ sung

- Geometry-based table parsing từ native PDF line/grid.
- Table structure recognition từ raster page image.
- HTML-to-cell-grid normalization.
- Text token–cell assignment dựa trên geometric intersection + reading order.
- Line-based refinement và merged-cell validation.

### 8.5. Validation rules tham khảo

- Cell không vượt quá bounds bất hợp lý ngoài table.
- Mỗi `rowspan/colspan` hợp lệ và không gây grid occupancy conflict.
- Không có nội dung bị nhân đôi giữa merged cells.
- Text child có quan hệ cha–con nhất quán.
- Cell OCR trống nhưng visually có text được đánh dấu review candidate.
- Diagram/image nằm trong table được giữ làm child/reference thay vì mất khi render table HTML.

---

## 9. Thiết kế xử lý image và diagram

### 9.1. Image extraction

Có thể lấy ảnh nhúng bằng API xử lý PDF và xác định ảnh đó được hiển thị ở đâu trên trang. Tuy nhiên, source xref/image bytes không phải lúc nào cũng tương ứng 1:1 với một visual image region trên trang; có thể có clipping, scaling, masks, transformations hoặc reused references.

### 9.2. Diagram detection — hướng D1: layout regions

**Ý tưởng:** Dùng layout detector để lấy candidate regions (`figure`, `image`, `chart`, ...) rồi tinh chỉnh vùng bằng geometry, text, lines và proximity. Candidate gần nhau có thể được nhóm nếu cùng một sơ đồ; candidate không liên quan được tách.

**Ưu điểm:** dùng được cho scan/digital; tích hợp dễ với document parsing.

**Hạn chế:** detector có thể bỏ qua flowchart hoặc tách nhiều node thành nhiều vùng; nhãn `chart` không đồng nghĩa flowchart.

### 9.3. Diagram detection — hướng D2: vector path grouping

**Ý tưởng:** Trên digital PDF, dùng vector paths và text boxes để tìm tập hình khối/đường nối có quan hệ. Graph/proximity grouping cho các drawing elements có thể giúp tìm vùng sơ đồ lớn, sau đó render thành PNG.

**Ưu điểm:** khai thác thông tin vector sắc nét, hữu ích khi flowchart không có embedded image.

**Hạn chế:** dễ nhầm table grid và diagram connectors; PDF paths không mang sẵn semantic node/edge; không áp dụng trực tiếp khi scan chỉ còn pixels.

### 9.4. Hướng bổ sung cho scan

Các phép phân tích line/contour/connected components trên raster image có thể hỗ trợ grouping hình khối. Đây là lớp refinement khác với xử lý vector paths; chất lượng cần được đo riêng trong tài liệu scan.

### 9.5. Cropping và rasterization

Một asset diagram có thể bao gồm:

- `source_page` và `bbox` theo tọa độ chuẩn.
- `asset_path` trỏ đến PNG.
- Render resolution/DPI và padding.
- Information về detection method, crop revision và review status.
- Optional OCR text metadata để hỗ trợ tìm kiếm, không nhân bản nội dung document.

**Manual bbox adjustment** là khả năng review rất hữu ích nếu tự động crop thiếu mũi tên hoặc thừa vùng text/border. Kết quả thay đổi crop nên đồng bộ bbox, asset và edit history.

### 9.6. Phát hiện diagram nằm trong bảng

Một representation có thể bao gồm cả `table` và `diagram` với quan hệ `parent_id` trỏ vào `table_cell` hoặc `table_region`. Tính giao nhau hình học chỉ là một tín hiệu; không đủ để khẳng định ownership. Các trường hợp diagram trải qua nhiều cell hoặc khó phân biệt border nên được đánh dấu cần kiểm tra.

---

## 10. Coordinate systems, bounding boxes và reading order

### 10.1. Bbox representation

Một định dạng nội bộ thuận tiện là `[x0, y0, x1, y1]` theo **page points**, gốc tọa độ **top-left** sau khi thống nhất quy tắc rotation. Đây là **lựa chọn thiết kế**, không phải yêu cầu chuẩn bắt buộc từ PDF.

Mỗi region cần page index, bbox, coordinate space, normalized rotation; hỗ trợ polygons nếu layout detector trả vùng xiên. Mapping từ pixel sang PDF points phụ thuộc render scale, crop, rotation và deskew transforms. Nếu chỉ có scaling không xoay/deskew, có thể dùng quan hệ đơn giản `x_pdf = x_pixel / scale_x`, `y_pdf = y_pixel / scale_y`; với các phép biến đổi khác, cần dùng transformation matrix đầy đủ.

### 10.2. Overlay consistency

Vị trí highlight cần khớp với PDF viewer sau khi zoom, rotate và thay đổi viewport. Có thể lưu transforms/metadata để kiểm tra vị trí giữa raw page coordinates, parser coordinates, rendered bitmap và frontend viewport.

### 10.3. Reading order

Reading order nên lưu độc lập với vị trí render. Với bảng, thứ tự nội dung có thể theo row/column hoặc semantic flow và cần quy định rõ. Header/footer/watermark (furniture) có thể lưu riêng để không chen vào body reading order.

---

## 11. Custom JSON schema — mô hình thông tin tham khảo

### 11.1. Nguyên tắc

- Framework-agnostic: có thể thay Docling/PaddleOCR/MinerU mà UI không phụ thuộc raw output.
- Stable component IDs (ổn định qua edit revisions).
- Tách `document/pages`, `components`, `assets`, `review`, `provenance`.
- Quan hệ cha–con và thứ tự đọc là thông tin hạng nhất.
- Schema hỗ trợ raw extraction, reviewed state và final approved output.
- Ảnh/diagram dùng asset references thay vì Base64 trong JSON mặc định.

### 11.2. Ví dụ dữ liệu minh họa

> Mọi tọa độ, ID, số trang và cấu trúc cell dưới đây **chỉ là ví dụ**, không phải kết quả trích xuất từ SOP thật.

```json
{
  "schema_version": "1.0",
  "document": {
    "id": "sop_001",
    "source": {
      "filename": "example_sop.pdf",
      "format": "pdf",
      "sha256": "<source-file-hash>"
    },
    "page_count": 8
  },
  "pages": [
    {
      "page_number": 2,
      "width": 595,
      "height": 842,
      "coordinate_system": "pdf_points_top_left",
      "rotation_normalized": true
    }
  ],
  "components": [
    {
      "id": "table_001",
      "type": "table",
      "parent_id": null,
      "page": 2,
      "bbox": [18, 50, 575, 790],
      "reading_order": 4,
      "status": "reviewed",
      "table": {
        "rows": 5,
        "cols": 5,
        "cell_ids": ["cell_001", "cell_002"]
      },
      "source": {
        "parser": "docling",
        "parser_version": "<version>",
        "confidence": null
      }
    },
    {
      "id": "cell_001",
      "type": "table_cell",
      "parent_id": "table_001",
      "page": 2,
      "bbox": [25, 80, 180, 360],
      "row": 0,
      "col": 0,
      "rowspan": 3,
      "colspan": 1,
      "child_ids": ["diagram_001"],
      "status": "reviewed"
    },
    {
      "id": "diagram_001",
      "type": "diagram",
      "parent_id": "cell_001",
      "page": 2,
      "bbox": [35, 90, 170, 340],
      "asset": {
        "path": "assets/diagram_001.png",
        "mime_type": "image/png"
      },
      "status": "reviewed"
    }
  ],
  "review": {
    "state": "approved",
    "revision": 3
  }
}
```

### 11.3. Component types có thể có

| Type | Fields đặc trưng |
|---|---|
| `text` / `paragraph` | text, spans, language, label, reading_order |
| `heading` | text, level |
| `list` / `list_item` | parent, children, order |
| `table` | rows, cols, cell_ids, geometry |
| `table_cell` | row, col, rowspan, colspan, text/children |
| `image` | asset path, source info, bbox |
| `diagram` | raster asset, crop provenance, optional extracted text |
| `container` / `region` | child_ids, semantic label (nếu có) |
| `furniture` | header/footer/watermark metadata |

Các field `confidence` nên là `null` khi không có score đáng tin từ parser. Confidence của OCR không tự động đại diện confidence của table structure hoặc nested relationships.

### 11.4. Dạng output package tham khảo

```text
output_package/
  document.json
  manifest.json
  assets/
    diagram_001.png
    image_001.png
    table_preview_001.png
  reviews/
    edits.jsonl
  debug/
    page_001_overlay.png
    raw_parser_a.json
    raw_parser_b.json
```

Đây chỉ là **ví dụ cách tổ chức dữ liệu**, không phải yêu cầu tạo cây thư mục hay file ở thời điểm đọc tài liệu. JSON chính có thể tham chiếu assets bằng đường dẫn tương đối; package có thể được lưu trên filesystem/object storage self-hosted tùy hệ thống.

### 11.5. Raw / reviewed / final lifecycle

- `raw extraction`: nguyên trạng parser output và normalized snapshot, bất biến.
- `reviewed working state`: bản được người dùng hiệu chỉnh.
- `edit history`: append-only events có reviewer, timestamp, target, operation, before/after.
- `final approved export`: JSON chính thức đã qua validation và đủ assets.

Các thao tác `soft-delete`, undo/redo và revision history giúp truy vết và phục hồi khi reviewer nhầm. Không nên giả định việc đổi nhãn là đủ; nội dung paragraph, text trong cell, bbox crop, thay ảnh và quan hệ lồng nhau đều có thể cần sửa.

---

## 12. Human-in-the-loop review — UX và data flow tham khảo

### 12.1. Mô hình giao diện

Một bố cục khả dĩ gồm:

- **PDF viewer** hiển thị tài liệu gốc và overlay bounding boxes.
- **Component tree/list** cho text/table/image/diagram, nested parents/children và review status.
- **Property / content editor** hiển thị text editor, cell grid, image/diagram preview, crop controls và metadata theo loại component.
- **Review controls** như approve, delete, replace, adjust bbox, restore và revision history.

PDF.js là một lựa chọn frontend viewer, không phải giải pháp extraction. Kiến trúc frontend/backend và UI framework không phải nội dung cố định của research.

### 12.2. Ma trận tính năng tham khảo

| Đối tượng | Tương tác có giá trị |
|---|---|
| Paragraph/text | Xem và sửa text, đổi label, xóa, xác minh bbox |
| Heading/list | Sửa content/level và reading order |
| Table | Xem dưới dạng grid, sửa text trong cell, xóa bảng |
| Cell | Hiển thị colspan/rowspan, children, thay/xóa nested image/diagram |
| Image | Preview, xóa, thay thế |
| Diagram | Preview PNG, chỉnh bbox/crop, xóa, thay thế |
| Nested relation | Xem parent/children và sửa association không đúng |
| Document | Review progress, approve, export JSON |
| History | Theo dõi before/after, undo/redo theo thiết kế revision |

Thêm/bớt hàng/cột, chỉnh sửa từng node của diagram và xuất ngược PDF không thuộc yêu cầu cốt lõi hiện tại.

### 12.3. Trường hợp review cần đặc biệt chú ý

- Bbox có thể đúng nhưng table semantics sai.
- Diagram preview bị cắt thiếu arrow/label hoặc chứa thừa table border.
- Một text item xuất hiện hai lần: OCR text và embedded diagram OCR.
- Cell được gộp sai khiến editor hiển thị một text trên nhiều ô.
- Component chưa được parser gắn vào reading order (`orphan`).
- Chỉnh một child làm thay đổi validity của parent table/container.

---

## 13. Benchmark, ground truth và evaluation design

### 13.1. Mục đích benchmark

Xác định phương pháp nào trích xuất **đủ các thành phần**, phục hồi quan hệ và hỗ trợ chỉnh sửa tốt trên SOP thực, không chỉ so sánh CER hay Markdown nhìn đẹp. Không có số liệu accuracy/latency từ benchmark SOP thật trong tài liệu này.

### 13.2. Dataset tham khảo

Một bộ POC nhỏ có thể chứa khoảng 20–30 trang gán nhãn thủ công, cân đối giữa:

| Nhóm | Trang tham khảo | Loại tình huống |
|---|---:|---|
| Digital basic | 4 | Heading, paragraph, lists |
| Digital complex table | 5 | Merged cells, nhiều dòng, rotated text |
| Digital diagram | 5 | Vector diagrams và flowchart trong table |
| Scanned PDF | 5 | Việt/Anh, scan noise, tables |
| Hybrid/edge cases | 5 | Mixed text/image, watermark, complex nesting |
| **Tổng minh họa** | **24** | Không phải mức bắt buộc |

Nếu có DOCX/XLSX gốc, có thể đối chiếu cấu trúc để hỗ trợ annotation. Tuy nhiên benchmark PDF parser không được lén dùng source Office trong quá trình inference.

### 13.3. Ground-truth annotation fields

- Page number và normalized bbox/polygon.
- Component type và reading order.
- Text transcription chính xác.
- Table region + row/column indices + merged-cell structure.
- Cell text và nested image/diagram references.
- Diagram region bbox và asset completeness.
- Parent-child relationships.
- Optional furniture classification.

### 13.4. Metric gợi ý

| Năng lực | Metric tham khảo | Ghi chú |
|---|---|---|
| OCR | CER, WER | Đặc biệt cho tiếng Việt có dấu và mã SOP |
| Detection/layout | Precision, recall, F1, bbox IoU | Tách theo class, không chỉ aggregate |
| Table structure | GriTS, TEDS, cell F1 | Cần chọn implementation phù hợp ground truth |
| Diagram | Region recall/precision, IoU, crop completeness | Mục tiêu là cả vùng sơ đồ, không phải node accuracy |
| Nested relationships | Parent-child precision/recall/F1 | Kiểm tra table/cell/container associations |
| Reading order | Pairwise order accuracy / sequence distance | Có thể đánh giá riêng body và furniture |
| Human review | Edit success, state consistency, JSON validity | Đánh giá chức năng, không chỉ model |
| Efficiency | Seconds/page, peak RAM/VRAM, startup/model loading | So sánh khi giữ cùng điều kiện |

### 13.5. Trọng số quyết định minh họa

| Nhóm | Trọng số tham khảo |
|---|---:|
| Table structure & cell content | 25% |
| Layout & bounding boxes | 20% |
| Diagram extraction | 20% |
| OCR text quality | 15% |
| Nested relationships | 15% |
| Reading order | 5% |

Các trọng số trên là một gợi ý theo ưu tiên **quality-first**, không phải kết luận đã được thống nhất và không thể thay thế ngưỡng đạt tối thiểu. Một pipeline OCR rất tốt vẫn có thể không phù hợp nếu không trích xuất được diagram hoặc table cells.

### 13.6. Test matrix tham khảo

| Scenario | Native-aware / Docling | Image-first / PaddleOCR | Challenger / MinerU |
|---|---|---|---|
| Digital text | Có thể so sánh | Có thể so sánh | Có thể so sánh |
| Vietnamese OCR | Có thể so sánh | Có thể so sánh | Có thể so sánh |
| Merged cells | Có thể so sánh | Có thể so sánh | Có thể so sánh |
| Nested diagram | Có thể so sánh | Có thể so sánh | Có thể so sánh |
| Rotated text/header/footer | Có thể so sánh | Có thể so sánh | Có thể so sánh |
| JSON schema fidelity | Có thể so sánh | Có thể so sánh | Có thể so sánh |
| Edit and asset lifecycle | Đánh giá sau normalization | Đánh giá sau normalization | Đánh giá sau normalization |

Các pipeline chỉ so sánh công bằng nếu cùng dataset, cùng annotation policy, cùng quy tắc normalize và cùng định nghĩa metrics.

---

## 14. Các hướng thử nghiệm và tiêu chí quan sát (không phải kế hoạch thực thi)

Phần này mô tả **những hướng có thể được kiểm tra** và dữ liệu có ý nghĩa để quan sát; không chỉ định việc triển khai, không quy định thứ tự hoặc môi trường thực hiện.

### 14.1. Document preflight

**Câu hỏi:** Có thể phân loại vùng digital/scan/hybrid và phát hiện rủi ro text layer trước parsing không?  
**Đầu ra quan sát hữu ích:** số trang, page dimensions, text coverage, image regions, vector density, rotation/deskew warnings.

### 14.2. Baseline document parsers

**Câu hỏi:** Docling, PP-StructureV3, MinerU khác nhau thế nào về text/table/picture bboxes, merged cells và nested components?  
**Đầu ra quan sát hữu ích:** raw JSON, normalized JSON, visual overlay, timing, memory, failure log, per-component metrics.

### 14.3. Diagram extraction comparison

**Câu hỏi:** Layout detection alone và vector geometry grouping có khác nhau ra sao trên flowchart vector nằm trong bảng?  
**Đầu ra quan sát hữu ích:** diagram region bounding boxes, crop PNG, completeness (có bị mất arrow/node label không), false positive với table grid.

### 14.4. Table reconstruction comparison

**Câu hỏi:** Model table recognition hoặc native lines có phục hồi đúng merged cells và text placement không?  
**Đầu ra quan sát hữu ích:** cell grid visualization, per-cell text, row/col spans, errors với nested diagrams, metric structure.

### 14.5. Human review fidelity

**Câu hỏi:** Khi thay text trong cell, xóa diagram hoặc đổi bbox crop, reviewed JSON/assets có nhất quán với view và log không?  
**Đầu ra quan sát hữu ích:** before/after state, export schema validation, stable IDs, audit trail, undo/redo correctness.

### 14.6. Portability và runtime

Công cụ có thể khác nhau về package, model acceleration, dependency và hiệu năng giữa CPU/GPU/hệ điều hành. Tài liệu này **không ưu tiên bất kỳ OS hay thiết bị nào**. Khi so sánh hiệu năng, metadata môi trường như CPU/GPU, RAM/VRAM, OS, library/model versions, batch config và DPI là các biến quan trọng, tránh kết luận tốc độ từ những cấu hình không tương đương.

---

## 15. Những quyết định kỹ thuật còn mở

Các mục sau được để ở dạng **decision points**; không có lựa chọn nào được coi là chỉ thị bắt buộc:

1. Parser chính là Docling, PaddleOCR, MinerU hay một tổ hợp theo vùng/trang?
2. OCR engine/model nào có chất lượng tiếng Việt tốt nhất trên dataset SOP?
3. Native-text recovery có cải thiện chất lượng digital PDF đủ để tăng độ phức tạp fusion không?
4. Diagram detection bằng layout có đủ hay cần vector grouping/CV refinement?
5. Khi diagram trải nhiều table cells, parent là cell, table region hay một container riêng?
6. Granularity JSON của text là paragraph, line, span hay kết hợp?
7. Raw-to-reviewed versioning, soft deletion, asset lifecycle và audit model được thiết kế mức nào?
8. Frontend review cần loại thao tác nào trước, loại nào để mở rộng?
9. Ngưỡng metric/criteria nào được coi là đủ cho sản phẩm nội bộ?
10. Cần triển khai offline chặt chẽ đến mức nào và license của từng model/package có phù hợp không?
11. Mục tiêu về trang/phút, RAM/VRAM, batch throughput và độ lớn tài liệu là bao nhiêu khi có dữ liệu vận hành thật?

---

## 16. Kết luận nghiên cứu (provisional)

- **Không có căn cứ để kết luận một OCR engine hoặc PDF parser đơn lẻ đáp ứng toàn bộ yêu cầu.** Bài toán kết hợp native parsing, OCR, layout analysis, table structure recognition, diagram region extraction và human review.
- **Docling + PyMuPDF** là một hướng baseline hợp lý vì có structured document model và các tiện ích PDF geometry. Đây là ưu tiên khám phá, **không phải kết luận về accuracy**.
- **PP-StructureV3 + PyMuPDF** là hướng đối chứng image-first đáng chú ý với table/layout OCR modules, đặc biệt để đánh giá scan và cell recognition.
- **MinerU** là challenger có giá trị trên các trang khó. Các tuyên bố về xử lý ảnh trong bảng cần được kiểm chứng ở cấp JSON/geometry/editability.
- **Diagram region detection + crop** cần được xem như năng lực riêng; native image extraction không giải quyết được flowchart tạo từ PDF vectors.
- **Table cells + nested objects** là tiêu chí khả thi bắt buộc; một output Markdown đẹp chưa đủ.
- **Custom normalized JSON** giảm phụ thuộc model/framework và tạo nền tảng cho review UI.
- **Độ chính xác trên SOP thực tế chưa được đo**. Chỉ có benchmark có gán nhãn và overlay review mới cho phép lựa chọn kỹ thuật có căn cứ.

Mọi lựa chọn trong tài liệu này có thể được thay đổi theo kết quả nghiên cứu và môi trường mà người phụ trách quyết định sử dụng.

---

## 17. Nguồn tham khảo chính thức

Các đường dẫn dưới đây phục vụ việc xác minh đặc tính, API, model, benchmark và giấy phép theo phiên bản hiện hành. Chúng không phải bảo đảm rằng mọi tính năng đều tồn tại hoặc có cùng hành vi trong mọi bản phát hành.

1. **Docling repository:** https://github.com/docling-project/docling  
   **Docling documentation:** https://docling-project.github.io/docling/  
   **Pipeline options:** https://docling-project.github.io/docling/reference/pipeline_options/
2. **PaddleOCR repository:** https://github.com/PaddlePaddle/PaddleOCR  
   **PP-StructureV3 documentation:** https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/PP-StructureV3.html
3. **MinerU repository / release information:** https://github.com/opendatalab/MinerU
4. **PyMuPDF page API:** https://pymupdf.readthedocs.io/en/latest/page.html  
   **PyMuPDF project:** https://pymupdf.readthedocs.io/
5. **pdfplumber:** https://github.com/jsvine/pdfplumber
6. **Camelot:** https://camelot-py.readthedocs.io/
7. **Surya:** https://github.com/datalab-to/surya
8. **Table Transformer:** https://github.com/microsoft/table-transformer
9. **Marker:** https://github.com/datalab-to/marker
10. **PDF.js:** https://mozilla.github.io/pdf.js/
11. **OpenCV:** https://docs.opencv.org/

---

## 18. Thuật ngữ

| Thuật ngữ | Ý nghĩa trong phạm vi dự án |
|---|---|
| SOP | Standard Operating Procedure, tài liệu quy trình chuẩn |
| Digital PDF | PDF chứa text/vector objects có thể khai thác trực tiếp |
| Scanned PDF | PDF chứa ảnh scan của trang tài liệu, thường cần OCR |
| Hybrid PDF | PDF hoặc trang có hỗn hợp text/image/scan |
| OCR | Optical Character Recognition, nhận diện chữ từ pixel |
| Layout analysis | Nhận diện loại/vị trí các vùng trên trang |
| Bounding box (bbox) | Hộp tọa độ xác định vị trí thành phần |
| Table structure recognition | Phục hồi hàng/cột/ô và ô gộp |
| Native extraction | Đọc text/graphics/images trực tiếp từ PDF objects |
| Rasterization | Chuyển vùng vector/PDF thành ảnh pixel |
| Diagram region | Vùng bao một flowchart/sơ đồ hoàn chỉnh |
| Nested component | Một thành phần nằm trong container/table/cell khác |
| Reading order | Thứ tự nội dung khi đọc/xuất có cấu trúc |
| Human-in-the-loop | Con người review và điều chỉnh output tự động |
| Provenance | Thông tin nguồn gốc parser, trang, tọa độ và cách trích xuất |
| Ground truth | Annotation chuẩn dùng để chấm chất lượng |
| CER / WER | Character/word error rate |
| IoU | Intersection over Union, độ giao nhau của hai vùng |
| TEDS / GriTS | Các metric đánh giá cấu trúc table |

---

**Ghi chú cuối:** Tài liệu có chủ ý chỉ mô tả *what/why/options/risks/evidence/evaluation*, không mô tả *agent must do*. Việc lựa chọn công cụ, xây dựng playground, thực thi benchmark, lựa chọn OS/hardware, độ sâu thử nghiệm và kế hoạch triển khai thuộc quyền quyết định của người phụ trách.
