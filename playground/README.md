# Playground: SOP PDF extraction

Mục tiêu vòng này: quan sát chất lượng extraction độc lập của Docling và PP-StructureV3 trên cùng bộ PDF giả lập. Chưa thiết kế schema sản phẩm, UI biên tập hoặc phối hợp nhiều parser.

## Thử nghiệm refinement và đo thời gian

```powershell
# Chạy tuần tự hai engine, đủ 16 trang/engine, model đã cache, không cho tải mạng
.\.venv-docling\Scripts\python.exe -X utf8 playground/run_sequential.py --run-name refined_v1

# Đối chiếu, báo cáo và gói chia sẻ riêng; không ghi đè baseline
.\.venv-docling\Scripts\python.exe playground/compare_runs.py --run-name refined_v1
.\.venv-docling\Scripts\python.exe playground/report.py --run-name refined_v1
.\.venv-docling\Scripts\python.exe playground/findings.py --run-name refined_v1
.\.venv-docling\Scripts\python.exe playground/package.py --run-name refined_v1
```

Mở `output/benchmark/experiments/refined_v1/index.html`. Lượt này thêm native table/image/text recovery, reconstruction lưới đường kẻ bằng OpenCV và grouping các hình khép kín có connector để tạo diagram candidates. Native text được gán vào ô theo geometry thay vì lấy text đã ghép sẵn của parser. Crop luôn từ trang gốc; mask dùng phân tích được giữ riêng. Model chưa fine-tune và code không đọc ground truth trong inference.

Với Docling, `generate_parsed_pages=True` giữ native/OCR text cells trước table assembly. Ngưỡng OCR bằng 0 để giữ các kết quả điểm thấp; token <0.5 và các ô chứa token đó được đánh dấu `needs_review`, không coi điểm confidence là xác suất đúng đã hiệu chuẩn. Với Paddle, bật hai tùy chọn cells-to-HTML theo geometry để thử riêng khả năng này; output gốc vẫn có thể sai và được giữ trong `parser_evidence.json`/`parser_table_*.html`.

Giả định hiện tại: trang thẳng, bảng có đường kẻ, diagram có ít nhất hai hình khép kín nối bằng đường dẫn. Đây là luật thử nghiệm đã phát triển trên chính bộ 4 thiết kế trang; chưa có held-out accuracy hoặc bằng chứng tổng quát hóa trên SOP thực. Các hình/diagram được phát hiện bằng CV giữ cờ cần review. Hình nằm trọn một ô được liên kết cell; diagram trải nhiều row bands liên kết ở cấp table để tránh khẳng định quan hệ 1:1 với hàng.

`parent_ref` là liên kết sở hữu dùng cho đánh giá; danh sách children có thể suy từ liên kết này. Đây vẫn là evidence format thử nghiệm, chưa phải schema review/export sản phẩm. `token_ownership.json` giữ các token body/cell/figure metadata/needs_review; `suppressed_duplicates.json` giải thích những OCR candidates đã được native text thay thế. Raw source tokens vẫn giữ riêng.

`timing.json` đo process wall time của từng engine tuần tự; `initialization.json` đo khởi tạo model; `execution.json` và status từng trang tách input preparation, parser + raw export, refinement + debug export, evidence + crop export. Thời gian trang ở timing policy v2 bao gồm cả export. Ảnh 200 DPI đầu vào có sẵn trong cache của bộ thí nghiệm; không xem đây là phép đo rasterize tất cả file mới từ đầu. Không so trực tiếp các số này với lượt baseline cũ chạy xen kẽ. Không bao gồm thời gian viết code, smoke test, đánh giá hoặc nén ZIP trong process wall time inference.

## Môi trường độc lập

Windows, Python 3.11:

```powershell
python -m venv .venv-docling
.\.venv-docling\Scripts\python.exe -m pip install docling easyocr pymupdf pillow psutil scipy
python -m venv .venv-paddle
.\.venv-paddle\Scripts\python.exe -m pip install "paddleocr[doc-parser]" paddlepaddle pymupdf pillow psutil scipy
```

Các file `requirements-*.lock.txt` được ghi từ môi trường thực tế sau khi chạy, dùng để tái lập trên Windows. Với T4, tạo môi trường riêng và chọn build CUDA tương thích với runtime trên JupyterHub; không cài nguyên lock Windows cho Linux. Trên Mac, thay đường dẫn Python bằng `.venv-*/bin/python`; lựa chọn MPS/backend cần kiểm chứng riêng.

## Chạy

Chạy từ thư mục gốc repo. Lần đầu cần mạng để tải model; inference là local, không gửi tài liệu tới remote OCR/AI API. Cache nằm trong `.cache/` của repo.

```powershell
# Một trang khó để kiểm tra môi trường và adapter
.\.venv-docling\Scripts\python.exe playground/run.py --engine docling --fixtures sop_digital --pages 3
.\.venv-paddle\Scripts\python.exe playground/run.py --engine paddle --fixtures sop_digital --pages 3

# Toàn bộ 16 trang, bỏ qua trang thành công có cùng source/config/code fingerprint
.\.venv-docling\Scripts\python.exe playground/run.py --engine docling --resume
.\.venv-paddle\Scripts\python.exe playground/run.py --engine paddle --resume

# Đánh giá và tạo báo cáo HTML local
.\.venv-docling\Scripts\python.exe playground/report.py
.\.venv-docling\Scripts\python.exe playground/model_inventory.py
.\.venv-docling\Scripts\python.exe playground/package.py

# Kiểm tra các tình huống dễ chấm sai
.\.venv-docling\Scripts\python.exe -m unittest discover -s playground -p test_evaluate.py -v
```

`--download-only` khởi tạo model mà chưa inference. `--device cpu --threads 4` là cấu hình mặc định. Chạy T4 dùng `--device cuda` cho Docling và `--device gpu:0` cho Paddle, sau khi cài đúng runtime. Có thể đặt `--run-name` để lưu một thí nghiệm khác. Trang thất bại có `status.json` và `error.log`; không được tính như kết quả thành công. Raw output cũ chỉ được dùng lại nếu status thành công và fingerprint còn khớp.

Nếu tải EasyOCR bị gián đoạn, `--engine docling --prefetch-easyocr` dùng downloader resume với URL chính thức và kiểm tra MD5 trọng số trước khi khởi tạo lại. Inference source được snapshot theo hash; mỗi trang có parser log và runtime warnings. Lần chạy lại lưu artifacts trước đó vào `history/`.

## Cấu hình baseline

- Docling: standard PDF pipeline, native-aware, EasyOCR `vi/en`, không force OCR toàn trang, TableFormer accurate, CPU 4 threads, picture classification/description mặc định không bật. Không bổ sung vector grouping hay native-text fusion ngoài pipeline sẵn có.
- Paddle: PP-StructureV3 image-first từ page render 200 DPI; OCR tiếng Việt; OCR version/model thực tế được ghi trong config. Bật table recognition và textline orientation; tắt unwarping/page rotation (fixture đều thẳng), formula, seal, chart interpretation. MKLDNN tắt để giảm phụ thuộc backend Windows trong vòng thử đầu. Không khôi phục native text sau OCR.
- Ảnh overlay và crop dùng chung render 200 DPI. Detector/OCR có thể resize nội bộ; config/version được lưu để giải thích khác biệt.

## Output

`output/benchmark/index.html` là báo cáo local, mở trực tiếp bằng browser. Đi kèm:

- `inputs/`: render đầu vào và source hash/scale.
- `runs/<engine>/<run-name>/environment.json`, `config.json`, `initialization.json`.
- Mỗi PDF/trang: raw parser JSON, evidence JSON, overlay regions/cells, HTML bảng, crop ảnh/vùng bảng, status và evaluation.
- `evaluation.json`: tổng hợp phép đo và các cờ cần review.
- `REPORT.md`: nhận định sau khi chạy và kiểm tra output thực tế.
- `page_manifest.json`: danh sách/hash artifacts của trang hiện tại; các file không được liệt kê có thể thuộc lần chạy trước.
- `package_manifest.json`: artifacts được đóng gói; không chứa model, virtualenv hoặc archived retries. `package.py` chỉ đóng gói khi đủ 32 trang thành công, đồng nhất fingerprint theo engine và không có link HTML bị thiếu.

Evidence chỉ là adapter phục vụ thử nghiệm; raw JSON giữ lại mọi thông tin parser để tránh giới hạn của adapter trở thành kết luận sai về model.

HTML bảng gốc được giữ nguyên. File `.view.html` chỉ thêm style xem grid, không sửa text/rowspan/colspan. Với Paddle, `ordered_1_to_1` là giả định theo thứ tự khi số lượng khớp, chưa xác minh association. Geometry chưa gán được vào HTML cell được hiển thị bằng chỉ số `raw`.

## Cách đọc kết quả

1. Detection dùng matching 1:1, tối đa số cặp có IoU >= 0.5 rồi tối ưu IoU; báo số expected/predicted/matched. Logo furniture được ghi riêng trong từng target, không ngầm xem là body figure.
2. Bảng chuẩn kiểm tra exact logical grid `(row,col,rowspan,colspan)`, không chỉ số hàng/cột. Bảng bố cục trang 3 không bị ép thành grid chuẩn. So sánh text ô theo đúng index/span khi có cell tương ứng.
3. Image và diagram được so vùng với output `figure/picture/image`. Match vùng không đồng nghĩa parser đã nhận đúng loại diagram. Crop phủ <95% bbox nhãn sẽ được gắn cờ để kiểm tra, chưa đủ kết luận mất nội dung vì nhãn có padding.
4. Nested association chỉ tính khi có parent link do parser trả về; hình nằm trong bảng về hình học không tự động được coi là có đúng ownership/cell.
5. Text dùng localized normalized token recall để tìm vùng nghi mất chữ. Đây **không phải CER/WER**: phụ thuộc bbox/segmentation, cho phép nhiều line cùng khớp một paragraph và có thể bị ảnh hưởng khi text bị gộp. Chữ xoay yêu cầu xem riêng. Không lấy cờ tự động làm số đo accuracy cuối cùng.
6. Thời gian trang gồm chuẩn bị render và extraction; model startup/download ghi riêng. Peak RSS là process tree sample mỗi 200 ms, không phải VRAM hoặc peak bộ nhớ tuyệt đối. Không kết luận tốc độ giữa các cấu hình máy khác nhau.

Chỉ có 4 thiết kế trang và 16 biến thể theo cặp. Bộ này kiểm tra lỗi kỹ thuật ban đầu, không chứng minh độ chính xác trên SOP thực hay khả năng tổng quát hóa sang template khác.

## Nguồn API chính thức đã đối chiếu

- https://docling-project.github.io/docling/_generated/examples/custom_convert/
- https://docling-project.github.io/docling/_generated/examples/export_figures/
- https://docling-project.github.io/docling/reference/pipeline_options/
- https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/PP-StructureV3.html
