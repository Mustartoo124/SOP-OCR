# SOP VLM experiment

Demo độc lập với `playground/`. Mục tiêu: đọc PDF/DOCX thành một biểu diễn trung gian có thể dựng lại và chỉnh sửa, trước bước ánh xạ SIPOC/RACI.

Chuyển sang máy công ty: xem [bản bàn giao đầy đủ](HANDOFF_VI.md) và [prompt trigger chạy pipeline](TRIGGER_PROMPT_VI.md).

**Nâng cấp mới:** mặc định `hybrid`: native/OCR cho prose, VLM cho vùng bảng/diagram. Xem [HYBRID_VI.md](HYBRID_VI.md) trước khi chạy. Các lệnh ảnh/scan dưới đây cần bổ sung `--regions sop_demo/regions-full-structure.example.json` nếu toàn ảnh là bảng/diagram; hoặc chủ động `--mode full-vlm` để chạy baseline cũ. Scan có prose cần manifest vùng riêng và Tesseract.

## Chạy

Từ root repo, dùng Python hiện có:

```powershell
.\.venv\Scripts\python.exe -m pip install -r sop_demo/requirements.txt
.\.venv\Scripts\python.exe -m streamlit run sop_demo/app.py --server.address 127.0.0.1
```

Mở http://localhost:8501. Chọn file, model, các trang muốn thử rồi bấm **Trích xuất**. Có thể mở kết quả đã lưu, chỉnh text theo component và tải JSON. UI gọi trực tiếp hàm Python, chưa cần API.

**Trạng thái kiểm chứng:** chưa có output VLM đầy đủ đạt yêu cầu vì các route gặp lỗi/giới hạn ghi trong [research.md](research.md). Streaming đã được thêm nhưng chưa kiểm chứng live sau khi quyền chạy thử bị từ chối. Chạy `python -m sop_demo.make_example` để tạo ví dụ viết tay một phần của `border.png`, dùng thử UI mà không gọi model; ví dụ có cảnh báo rõ ràng, không dùng làm số liệu benchmark.

CLI:

```powershell
.\.venv\Scripts\python.exe -m sop_demo.extract --list-models
.\.venv\Scripts\python.exe -m sop_demo.extract document/border.png --out sop_demo/runs/border
.\.venv\Scripts\python.exe -m sop_demo.extract "document/example.pdf" --pages 2,3 --out sop_demo/runs/example
.\.venv\Scripts\python.exe -m unittest sop_demo.test_schema -v
```

`.env`: `LITELLM_BASE_URL`, `LITELLM_API_KEY`; tuỳ chọn `SOP_MODEL`. Không dùng model text-only `LITELLM_MODEL` làm mặc định. Model mặc định của demo là `global.anthropic.claude-sonnet-5`; tên này là deployment alias của proxy đang thử, không phải tên portable cho mọi proxy.

PDF được render 144 DPI với PyMuPDF, ảnh gửi model giới hạn cạnh dài 2200 px. Giữ ảnh gốc render để đối chiếu. DOCX: ưu tiên renderer `SOP_SOFFICE`/`soffice`; trên Windows nếu không có, dùng Word COM cài sẵn, read-only, macro disabled. Không chuyển DOCX thành plain text vì sẽ mất shape, connector, layout. Môi trường không có renderer cần cài renderer hoặc export PDF trước. `.doc` và Excel chưa được hỗ trợ trong demo này.

## JSON contract

`document.schema.json` được sinh từ Pydantic trong `schema.py`; `validate_document()` kiểm tra thêm toàn vẹn tham chiếu, ID, span và chồng lấn cell. JSON Schema tự nó không đủ kiểm tra các ràng buộc này.

Tọa độ dùng hệ trang chuẩn hóa 0–1000; bbox là `{x,y,w,h}`, không phải tọa độ hai góc. ID duy nhất trong trang. Quan hệ xuyên trang dùng `pN:id`.

| Thành phần | Ý nghĩa |
|---|---|
| `components` | Text, node lưu đồ, ảnh; text có một chủ sở hữu duy nhất, bbox bảo tồn vị trí nguồn |
| `diagrams` | Node IDs, edge có hướng, loại quan hệ, nhãn và polyline điểm uốn; độc lập với hàng bảng |
| `tables.columns` | Thứ tự cột, tên, vai trò và vị trí nguồn |
| `tables.rows` | Hàng liên kết suy luận, `source_band` chỉ nhóm hàng vật lý gốc, `anchor_ids` chỉ node liên quan |
| `tables.cells` | Chỉ số row/column zero-based, rowspan/colspan, component IDs hoặc diagram ID |
| `relations` | Liên kết ngữ nghĩa nhiều–nhiều, cơ sở suy luận, confidence và rationale |
| `page_images` / `asset_ref` | Đường dẫn tương đối tới ảnh trang và ảnh vùng, đóng gói cùng JSON |
| `warnings` / `provenance` | Điểm chưa chắc chắn, model, token usage, số lần gọi và trạng thái liên kết xuyên trang |

**Ví dụ đúng với yêu cầu HCN:** hai hàng logic r1/r2 có anchor là hai node HCN TTC/NM; hai cell mô tả riêng; cell thời gian chỉ chứa một component “Hằng ngày”, `rowspan=2`; cell trách nhiệm dùng chung tương tự. Một cell lưu đồ chứa diagram duy nhất và span qua toàn bộ các hàng liên quan. Hai node cùng có relation tới component thời gian/trách nhiệm đó. Các mũi tên vẫn thuộc diagram, không thuộc hàng.

Không ép mọi relation thành merge: liên kết không liên tiếp hoặc liên kết chéo được lưu trong `relations`; rowspan chỉ dùng cho dải liên tiếp. Diễn giải flowchart theo mũi tên không đồng nhất với liên kết gióng ngang.

`source_bbox` và tọa độ node bảo tồn bố cục nguồn; bảng HTML dùng hàng logic và cell gộp. Hai chế độ xem phục vụ hai mục đích này. Renderer SVG hỗ trợ rectangle, rounded, diamond, document, parallelogram, predefined và ellipse; đây là tái dựng cấu trúc, chưa phải bản sao typography hoàn hảo.

## Pipeline hiện thực

1. Render trang; trích text native cùng bbox nếu PDF có text. Lưu ảnh trang.
2. Gửi ảnh + native evidence + schema + quy tắc relation tới VLM; dữ liệu trong tài liệu không được xem là instruction.
3. Validate cấu trúc và đồ thị tham chiếu. Từ chối output rỗng trên trang có nội dung và output bị cắt do token limit.
4. Mặc định một lượt model rà soát toàn trang; thêm tối đa một lần repair. `--no-review` bỏ visual review, vẫn cho một lần repair nếu JSON lỗi.
5. Lưu raw response, usage, JSON trang, JSON tài liệu và crop ảnh. Các run nằm trong `sop_demo/runs/`, không commit.
6. UI đọc cùng contract; text sửa vẫn giữ ID, edge, relation và hình học; lưu `document.edited.json` riêng.

Structured output phụ thuộc route/provider. `--response-mode prompt` là mặc định tương thích; có thể chọn `json` hoặc `schema` nếu deployment hỗ trợ. Không tự chuyển model hoặc retry vô hạn vì sẽ phát sinh chi phí khó thấy.

`SOP_MAX_TOKENS` mặc định 16000. Route Azure GPT-4o đang thử chỉ cho 4096; hạ biến này chỉ tránh lỗi tham số, không bảo đảm đủ chỗ cho schema dài. Streaming nhằm giữ kết nối qua proxy; cần deployment hỗ trợ `stream_options.include_usage`.

## Giới hạn cần biết

- Chưa có bộ ground truth đầy đủ nên không tuyên bố accuracy từ việc JSON hợp lệ. Confidence do model tự báo, không phải xác suất đã hiệu chuẩn.
- Model có thể bỏ nội dung hoặc nhận sai chiều mũi tên dù schema hợp lệ. Full-page review không đảm bảo phát hiện hết lỗi. Cần đối chiếu mẫu gán nhãn trước khi đưa vào production.
- Trang được xử lý riêng; schema có quan hệ xuyên trang nhưng demo chưa tự nối flow/table qua trang. Trạng thái này có trong provenance, không suy đoán nối chỉ vì cùng tên.
- Không có editor relation, layout hoặc node; chưa có API HTTP, chưa chuyển sang JSON SIPOC/RACI cuối.
- Không giữ chính xác font/style rich text, màu và đường cong connector tùy ý. Connector được xấp xỉ polyline; ảnh được lưu dạng crop PNG, không phải toàn bộ file media nhúng nguyên gốc.
- Khi một trang lỗi, các JSON trang đã hoàn thành còn ở thư mục run; chưa có resume tự động. Token usage được ghi nhưng giá proxy không được giả định bằng bảng giá hãng.

## Hướng cải thiện độ chính xác

Bước tiếp theo nên là tách inventory hình học/text, tracing connector và suy luận hàng/relation thành các pass nhỏ; crop lưu đồ có padding để nhìn rõ arrowhead rồi quy đổi tọa độ crop về trang. Giữ full-page context để tránh mất liên kết cột. Đối chiếu text native/OCR với text VLM; dùng vector PDF để làm bằng chứng vị trí nếu có, không coi vector detection là hiểu ngữ nghĩa. Dùng model mạnh hơn chỉ trên vùng có tranh chấp và lưu cả phương án trước/sau.

Đánh giá riêng: text CER, node recall, directed-edge precision/recall kèm nhãn nhánh, cell span accuracy, relation precision/recall, tỷ lệ phải sửa và tổng chi phí/trang. Hai ảnh mẫu thích hợp làm bộ golden ban đầu nhưng không đủ đại diện mọi SOP.

Backend sau này có thể bọc `prepare()`, `run()`, `validate_document()` và edit theo ID thành các endpoint job/upload/document/patch; contract này không phụ thuộc Streamlit.
