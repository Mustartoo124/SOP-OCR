# Bàn giao dự án SOP sang máy công ty

Cập nhật ngày 17/11/2026. Tài liệu này mô tả yêu cầu, code thực tế và trạng thái kiểm chứng để tiếp tục ở máy khác. Đây là bản thử nghiệm, chưa phải pipeline đã chứng minh chất lượng trích xuất end-to-end.

**Bổ sung mới nhất, ưu tiên hơn mô tả baseline bên dưới:** đã thêm chế độ mặc định `hybrid` trong `routing.py`: prose native/OCR cục bộ, VLM chỉ xử lý ROI bảng/diagram. Đọc [HYBRID_VI.md](HYBRID_VI.md). Scan/ảnh yêu cầu manifest `--regions`; phần prose scan cần Tesseract. Các lệnh cũ cho ảnh phải thêm manifest hoặc chủ động chọn `--mode full-vlm`. Nhận diện vùng native dùng heuristic; chưa có layout detector tự động cho scan. Test routing bổ sung không thay thế kiểm chứng OCR/VLM live.

## 1. Bài toán và phạm vi đã thống nhất

Đầu vào là tài liệu SOP chứa text, bảng, flowchart và thông tin liên quan tới SIPOC/RACI. Định dạng dài hạn gồm PDF có text, PDF scan, Word và Excel. Giai đoạn hiện tại ưu tiên PDF và DOCX; PNG/JPEG được hỗ trợ để thử ảnh mẫu. Chưa triển khai Excel hoặc Word `.doc` cũ.

Pipeline sản phẩm gồm ba giai đoạn:

1. Đọc nội dung, hình học và quan hệ, tạo JSON trung gian theo schema thống nhất.
2. Engine đọc JSON để dựng lại tài liệu, người dùng sửa và xuất JSON đã chỉnh. Sản phẩm cuối hướng backend API cho UI khác; demo hiện tại dùng Streamlit gọi trực tiếp hàm Python, chỉ sửa text.
3. Chuyển JSON đã sửa sang format nghiệp vụ SIPOC/RACI. Chưa thuộc phạm vi hiện thực.

Ưu tiên độ chính xác hơn tốc độ; chi phí hợp lý, không mặc định chọn model đắt nhất. Có thể điều chỉnh kích thước để dễ xem nhưng cần giữ cấu trúc và quan hệ. Khi vị trí không rõ, hệ thống dùng cả hình học lẫn ngữ nghĩa; phần không chắc phải được ghi lại để con người sửa về sau.

Repo có phương pháp thử trước đó trong `playground/`. Hướng VLM mới nằm riêng tại `sop_demo/`; không cần đọc toàn bộ hướng cũ và không ghi đè code/kết quả của hướng cũ.

## 2. Yêu cầu khó nhất

Một hàng vật lý trong bảng gốc có thể chứa nhiều node lưu đồ và nhiều đoạn nội dung ở cột khác. JSON cần thêm các hàng logic để làm rõ quan hệ, nhưng **không cắt hoặc nhân bản lưu đồ theo từng hàng**.

Ví dụ `document/border.png`:

- Node “HCN Giao tại TTC: WV-PTNL-06-F1” và node “HCN Giao tại NM: WV-PTNL-06-F2” là hai node khác nhau, có mũi tên vào “Cung cấp hồ sơ thu mua STNL”.
- Mỗi node HCN liên quan một đoạn mô tả riêng ở cùng vùng ngang.
- Hai node dùng chung component “Hằng ngày” và nhóm trách nhiệm “Đại diện Trạm/KCS; Nhân viên tiếp nhận/Nhân viên Kho”.
- Hai hàng logic có hai cell mô tả riêng; cell thời gian/trách nhiệm dùng `rowspan` để biểu diễn chia sẻ. Lưu đồ là một diagram nguyên vẹn trong cell span qua các hàng.
- Bản gốc còn có các node và hàng khác cùng liên quan “Hằng ngày”; không được giới hạn cell đó ở đúng hai hàng chỉ vì ví dụ tập trung vào hai HCN.

Quan hệ theo mũi tên và quan hệ gióng ngang là hai loại độc lập. Không suy ra thứ tự flowchart từ vị trí trên/dưới; không coi tất cả nội dung trong cùng một hàng vật lý đều liên quan với nhau. Relation không liên tiếp vẫn lưu bằng tham chiếu nhiều–nhiều, không ép thành rowspan.

## 3. Các file đã triển khai

| File | Chức năng |
|---|---|
| `schema.py` | Pydantic models và kiểm tra ID, tham chiếu, cell overlap/span |
| `document.schema.json` | JSON Schema sinh từ `Document` trong `schema.py` |
| `ingest.py` | DOCX → PDF; PDF → ảnh trang + native text/bbox; crop ảnh component |
| `word_to_pdf.ps1` | Word COM export read-only, tắt macro, không sửa tài liệu nguồn |
| `extract.py` | Client LiteLLM, prompt, trích xuất, review/repair hữu hạn, CLI và lưu kết quả |
| `probe.py` | Thử đọc tiêu đề và ba node trên `border.png` bằng request ngắn |
| `render.py` | Dựng bảng HTML cell gộp và SVG node/connector từ JSON |
| `app.py` | UI chọn file/model/trang, mở kết quả, đối chiếu, sửa text, xuất JSON |
| `make_example.py` | Tạo ví dụ schema viết tay một phần, được gắn nhãn rõ |
| `test_schema.py`, `test_app.py` | 7 test về toàn vẹn cấu trúc, render an toàn và sửa text |
| `research.md` | Nguồn nghiên cứu và kết quả thử route thực tế |
| `requirements.txt` | Các dependency trực tiếp; chưa phải lockfile tái lập chính xác |

Schema dùng hệ tọa độ trang 0–1000. `bbox` của component là `{x,y,w,h}`; riêng native evidence từ PDF hiện là `[x0,y0,x1,y1]`, cần chú ý nếu sửa prompt hoặc thêm xử lý hình học.

`components` chứa text/node/ảnh; `diagrams` chứa node IDs và edges có source, target, label, points, label_position; `tables` chứa columns/rows/cells; `relations` chứa loại, basis, confidence, rationale. `source_band` ghi nhóm hàng vật lý nguồn; `anchor_ids` ghi node liên quan hàng logic. ID duy nhất trong một trang; tham chiếu xuyên trang theo `pN:id`.

Ảnh lưu bên ngoài JSON qua đường dẫn tương đối. Khi chuyển output sang máy khác, mang cả `assets/` cùng JSON, không chỉ JSON.

## 4. Trạng thái thực tế

Đã kiểm tra thành công:

- Render một PDF mẫu 9 trang; trích được native text evidence.
- Xuất DOCX mẫu sang PDF bằng Word COM; render và xem trang đầu. Chưa kiểm tra trực quan toàn bộ trang DOCX.
- 7 test tự động đạt, gồm chỉnh text mà không đổi relation/cell span.
- Streamlit AppTest khởi tạo và thao tác sửa text được. Chưa nghiệm thu trực quan UI trong trình duyệt.

Chưa đạt:

- Chưa có JSON đầy đủ từ VLM được kiểm tra đạt yêu cầu trên hai ảnh mẫu hoặc một tài liệu PDF/DOCX hoàn chỉnh.
- Chưa chọn được model thắng bằng benchmark. Tên model mặc định chỉ là ứng viên thử.
- Chưa có OCR engine bổ trợ, crop review tự động hoặc pipeline nhiều pass; hiện là baseline full-page + review/repair.
- Chưa tự nối bảng/lưu đồ xuyên trang, chưa có API HTTP, chỉnh relation, Excel hoặc chuyển đổi SIPOC/RACI giai đoạn 3.
- Chưa bảo tồn toàn bộ font/rich text/màu; đường cong connector xấp xỉ polyline; ảnh là crop PNG, không đảm bảo giữ nguyên media nhúng.

Lỗi đã gặp trên proxy ở máy hiện tại:

| Route | Kết quả |
|---|---|
| `qwen.qwen3-vl-235b-a22b` | Probe đọc ảnh thành công, nhưng yêu cầu schema đầy đủ trả arrays rỗng |
| `global.anthropic.claude-sonnet-5` | Probe thành công; request đầy đủ non-streaming gặp nginx 504 |
| `global.anthropic.claude-sonnet-4-6` | Request đầy đủ non-streaming gặp nginx 504 |
| `azure/gpt-4o` | Probe thành công; route giới hạn 4096 completion tokens |
| `gpt-4o`, `claude-sonnet` | Alias có trong danh sách nhưng thiếu credential upstream |

Đã thêm streaming trong code sau các lỗi 504, nhưng lần chạy xác minh bị từ chối nên chưa kiểm chứng live. Máy công ty có thể khắc phục vấn đề truy cập, nhưng lỗi upstream credential/token limit/prompt không tự biến mất chỉ vì chuyển máy. Cần probe lại deployment thực tế.

Các run Qwen cũ có `document.json` rỗng đã được tạo trước khi bổ sung kiểm tra trang không trắng. Đó là **kết quả thất bại**, không dùng để đánh giá demo thành công. `manual-schema-example` là ví dụ viết tay một phần, tuyệt đối không báo là output model.

## 5. Mang gì sang máy công ty

Mang toàn bộ `sop_demo/` và tài liệu trong `document/`. Nếu dùng Git, kiểm tra các file mới đã có trong checkout: chưa có commit/push nào được thực hiện trong phiên này. Không cần mang `.venv/`; tạo môi trường mới trên máy đích.

`.env` và `sop_demo/runs/` nằm trong `.gitignore`, vì vậy clone/pull sẽ không tự mang chúng sang. Tạo `.env` bằng credential của công ty. Nếu muốn đối chiếu raw response cũ, copy riêng các thư mục run cần thiết; không bắt buộc để chạy code. Những thay đổi/xóa file có sẵn trước phiên trong repo không phải phần demo này và chưa được khôi phục hay commit.

Các đường dẫn trong lệnh bên dưới đều tương đối từ repo root; không phụ thuộc `D:\github\SOP-OCR` trên máy cũ.

## 6. Thiết lập và chạy thủ công trên Windows

Mở PowerShell tại root repo. Khuyến nghị Python 3.11 hoặc 3.12:

```powershell
py -3.12 -m venv .venv-sop
.\.venv-sop\Scripts\python.exe -m pip install -r sop_demo/requirements.txt
.\.venv-sop\Scripts\python.exe -m unittest sop_demo.test_schema sop_demo.test_app -v
```

Nếu không có Python 3.12, dùng bản Python tương thích đã cài để tạo venv. Không cần activate; gọi executable trực tiếp như trên.

Tạo hoặc cập nhật `.env` ở root, không ghi đè các cấu hình khác đã có:

```dotenv
LITELLM_BASE_URL=https://YOUR-COMPANY-LITELLM-ENDPOINT/v1
LITELLM_API_KEY=YOUR-COMPANY-KEY
SOP_MODEL=YOUR-VISION-DEPLOYMENT-ALIAS
SOP_MAX_TOKENS=16000
```

Endpoint và alias phải theo proxy công ty. `/v1` ở trên chỉ là ví dụ; không thêm lần nữa nếu endpoint đã có. `SOP_MODEL` là biến demo dùng; `LITELLM_MODEL` hiện không được dùng để chọn model demo. Biến môi trường đang có trong shell có thể ưu tiên hơn `.env` do `load_dotenv()` không override mặc định.

DOCX cần Microsoft Word cài đặt/kích hoạt trên Windows hoặc LibreOffice headless. Nếu dùng LibreOffice, cấu hình `SOP_SOFFICE` tới executable phù hợp. Nếu không có renderer, tạm export Word sang PDF thủ công để thử đường PDF, và báo rõ đường DOCX chưa được xác minh.

Kiểm tra route trước:

```powershell
.\.venv-sop\Scripts\python.exe -m sop_demo.extract --list-models
$sopModel = 'YOUR-VISION-DEPLOYMENT-ALIAS'
.\.venv-sop\Scripts\python.exe -m sop_demo.probe $sopModel
```

Chạy hai ảnh trước khi chạy tài liệu dài; dùng tên thư mục mới cho mỗi lần để tránh ghi đè evidence:

```powershell
.\.venv-sop\Scripts\python.exe -m sop_demo.extract document/border.png --model $sopModel --out sop_demo/runs/company-border-01
.\.venv-sop\Scripts\python.exe -m sop_demo.extract document/no_border.png --model $sopModel --out sop_demo/runs/company-no-border-01
```

Mặc định review bật; tối đa 3 call/trang nếu cần sửa JSON. `--no-review` dùng tối đa 2 call gồm repair khi cần, không đồng nghĩa chỉ luôn gọi một lần. API/network error hiện dừng run, không tự retry/fallback.

Chọn một vài trang PDF/DOCX có bảng và flowchart bằng UI, hoặc CLI:

```powershell
.\.venv-sop\Scripts\python.exe -m sop_demo.extract "document/YOUR-FILE.pdf" --pages 2,3 --model $sopModel --out sop_demo/runs/company-pdf-01
.\.venv-sop\Scripts\python.exe -m sop_demo.extract "document/YOUR-FILE.docx" --pages 2 --model $sopModel --out sop_demo/runs/company-docx-01
```

`--pages` đếm từ 1 theo trang PDF render, không theo số trang in trong tài liệu. Thay file và trang theo mẫu thật. Bỏ `--pages` để chạy toàn bộ sau khi kiểm tra trang mẫu đạt yêu cầu. Với DOCX, quá trình chuyển sang PDF vẫn xử lý cả tài liệu trước khi chọn trang render.

Mở UI:

```powershell
.\.venv-sop\Scripts\python.exe -m streamlit run sop_demo/app.py --server.address 127.0.0.1
```

Truy cập `http://localhost:8501`, mở run vừa tạo, đối chiếu ảnh nguồn và bản dựng, chỉnh text, lưu/tải `document.edited.json`. Nếu chỉ thử UI không gọi model:

```powershell
.\.venv-sop\Scripts\python.exe -m sop_demo.make_example
```

Output trong mỗi run: `document.json`, `page-N.json`, `page-N-attempt-K.txt`, `page-N-usage.json`, `assets/page-N.png`, crop ảnh nếu có. Với DOCX còn có PDF trung gian. Nếu lỗi API trước khi nhận đủ stream, hiện có thể chưa lưu raw response; cần bổ sung diagnostic nếu gặp lại.

## 7. Những điểm cần kiểm tra hoặc sửa tiếp

1. **Streaming:** kiểm tra `stream_options.include_usage` được route hỗ trợ. Nếu provider từ chối, điều chỉnh tương thích có chủ đích; không fallback âm thầm rồi kết luận token usage đầy đủ.
2. **Review sau repair:** vòng lặp hiện trả về khi output hợp lệ ở attempt sau attempt đầu, nên trường hợp attempt đầu invalid rồi repair thành công có thể chưa trải qua visual review độc lập dù `review_enabled=true`. Sửa state machine/provenance nếu cần bảo đảm semantics “đã review”.
3. **Logging:** `validation_error` được thêm sau lần ghi usage hiện tại; lỗi cuối có thể không xuất hiện trong file usage. Lưu log sau validation và khi exception để không mất bằng chứng.
4. **Giới hạn output:** giảm max_tokens chỉ tránh lỗi tham số, không giải quyết thiếu chỗ cho JSON. Nếu model chỉ cho output ngắn, tách inventory, graph và table/relation thành pass nhỏ với ID ổn định rồi merge/validate.
5. **Ảnh scan:** thiếu native text là bình thường. Model phải đọc ảnh; không được coi native text rỗng là trang rỗng. Với chữ nhỏ nên crop có overlap/padding và chuyển tọa độ về hệ trang.
6. **Toàn vẹn và độ chính xác:** JSON hợp lệ chỉ là kiểm tra cấu trúc. Phải xem đủ node, hướng mũi tên, nhãn nhánh, nội dung text, cell share và relation với ảnh nguồn.
7. **Tính tổng quát:** sửa pipeline phải chạy lại `no_border.png` và trang PDF/DOCX khác; không hard-code toạ độ/text của `border.png` để tạo output “đúng”.

Không coi đây là danh sách lỗi đã sửa: các mục trên là việc bàn giao cần agent tiếp tục đánh giá. Nếu sửa schema, đồng bộ `document.schema.json`, renderer, tests và tài liệu, nêu migration nếu thay contract.

## 8. Tiêu chí nghiệm thu lần chạy tiếp theo

- Có output VLM thật, không rỗng, không bị cắt, vượt kiểm tra schema và integrity.
- Với `border.png`: phân biệt hai HCN, giữ node/mũi tên vào bước cung cấp hồ sơ; hai mô tả riêng; thời gian/trách nhiệm dùng chung bằng tham chiếu và span phù hợp toàn bộ ảnh.
- Flowchart không bị chia hoặc nhân bản theo hàng; các nhánh loop/đạt/không đạt được đối chiếu với nguồn.
- Với `no_border.png`: không dựa duy nhất vào đường kẻ ngang để phân hàng; kiểm tra kết hợp nội dung và hình học.
- Chạy được mẫu PDF và DOCX, lưu assets có ref hợp lệ, UI dựng lại và sửa text không mất relation.
- Báo cáo số trang/call, model, usage có thật, các lỗi còn tồn tại. Chưa có ground truth thì chỉ báo kiểm tra thủ công, không đưa accuracy % hay “model tốt nhất” không có chứng cứ.
- Chưa tự nối xuyên trang thì tiếp tục công khai giới hạn đó; không đánh dấu toàn bộ bài toán đa trang đã giải quyết.

Prompt bàn giao đầy đủ ở [TRIGGER_PROMPT_VI.md](TRIGGER_PROMPT_VI.md). Dán nội dung file đó vào agent tại root repo trên máy công ty.
