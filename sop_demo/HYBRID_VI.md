# Hybrid routing cho text, bảng và diagram

Nâng cấp theo yêu cầu: không cần VLM cho text thông thường. Chế độ mặc định mới là `hybrid`; baseline cũ vẫn có thể chọn chủ động bằng `--mode full-vlm` để đối chiếu.

## Đường xử lý

| Loại vùng | Cách xử lý |
|---|---|
| Text trong PDF có text | PyMuPDF lấy text line và bbox cục bộ |
| Text trong DOCX | Render Word/LibreOffice sang PDF để giữ hình học, rồi lấy native text; chưa đọc paragraph OOXML trực tiếp |
| Text trong scan/ảnh | Tesseract OCR cục bộ với `vie+eng`; không fallback sang VLM |
| Bảng hoặc diagram | Crop vùng cấu trúc, gửi ảnh + text evidence trong vùng cho VLM, giữ schema cũ |
| Ảnh nhúng ngoài vùng cấu trúc | Lưu crop và ref, cảnh báo kiểm tra xem có diagram chưa được phân loại |

Text nằm **trong bảng/node** vẫn có thể do VLM đọc cùng vùng cấu trúc, vì cần hiểu cell/node/quan hệ. Text native/OCR trong vùng được gửi làm evidence. Text ngoài vùng không gửi trong evidence cho VLM và được ghép lại thành component riêng sau khi trích xuất vùng cấu trúc.

Không tạo client/API call khi trang chỉ có prose. `provenance.routing` ghi text engine, số component text cục bộ, ROI và số VLM call theo trang. JSON giữ nguyên schema version 1.0; chưa thêm trường provenance vào từng component. Các relation liên quan prose ngoài ROI chưa được tự suy luận.

## Nhận diện vùng và giới hạn

PDF native dùng bảng do PyMuPDF phát hiện, cụm vector shape và alignment text lặp lại để đề xuất ROI. Đây là heuristic, không phải model document-layout đã được benchmark: có thể nhận nhầm bố cục nhiều cột là bảng, hoặc bỏ sót diagram/bảng không viền. Raster nhúng được giữ như ảnh, không tự gửi VLM; nếu là bảng/diagram cần khai báo vùng để xử lý.

Với scan/PNG/JPEG, bản nâng cấp **chưa tự động phân loại layout**. Cần manifest `--regions` xác nhận vùng cấu trúc. Nếu không có manifest, dừng với lỗi rõ ràng; không ngầm gửi cả trang VLM và không coi cả trang là prose. `[]` là xác nhận rõ trang chỉ có text cần OCR. Tesseract hoặc ngôn ngữ OCR thiếu thì dừng, không dùng VLM thay thế.

Các ROI trên cùng trang hiện hợp thành **một crop bao ngoài** để giữ quan hệ giữa cột, node và connector. Vì vậy một phần text nằm giữa các bảng cũng có thể đi cùng crop. Chưa tối ưu nhiều crop tách rời và nối relation giữa crop. Vùng tự động được mở rộng tới hết các text line chạm mép để giảm cắt chữ.

Ảnh crop dùng hệ tọa độ riêng 0–1000 khi gửi model; backend đổi bbox, edge points, label_position, column và row về hệ trang. Diagram và cell span giữ nguyên, ID của local text được chọn không trùng model IDs.

## Khai báo vùng

Ví dụ file `regions.json` cho tài liệu ba trang:

```json
{
  "1": [],
  "2": [{"x": 50, "y": 200, "w": 900, "h": 700}],
  "3": [{"x": 0, "y": 0, "w": 1000, "h": 1000}]
}
```

Số trang tính từ 1; bbox dùng x,y,width,height trên hệ trang 0–1000. Trang 1 xác nhận chỉ text; trang 2 có một vùng cấu trúc; trang 3 toàn trang là bảng/diagram. Trang PDF native không có key trong manifest dùng heuristic; trang scan thiếu key sẽ dừng.

`regions-full-structure.example.json` khai báo trang 1 toàn bộ là vùng cấu trúc, phù hợp để tiếp tục thử hai ảnh SOP bảng có lưu đồ đã cung cấp. **Không dùng file này mặc định cho mọi scan**, vì sẽ gửi cả trang text vào VLM. Khi ROI phủ toàn trang cấu trúc không cần OCR prose; các scan có prose ngoài ROI cần OCR.

```powershell
.\.venv-sop\Scripts\python.exe -m sop_demo.extract document/border.png --mode hybrid --regions sop_demo/regions-full-structure.example.json --out sop_demo/runs/hybrid-border-01
.\.venv-sop\Scripts\python.exe -m sop_demo.extract "document/YOUR-FILE.pdf" --mode hybrid --regions regions.json --out sop_demo/runs/hybrid-pdf-01
```

UI có lựa chọn mode và upload manifest riêng. File `page-N-routing.json` và `assets/page-N-structure.png` phục vụ kiểm tra vùng được route; routing.json lưu cả text evidence cục bộ, nên cần giữ cùng mức bảo mật với tài liệu nguồn.

## OCR trên máy công ty

```powershell
.\.venv-sop\Scripts\python.exe -m pip install -r sop_demo/requirements-ocr.txt
```

Cần cài thêm executable Tesseract cùng traineddata tiếng Việt/Anh qua quy trình của công ty; pip package không cài engine hoặc language data. Có thể đặt `SOP_TESSERACT` tới executable và `SOP_OCR_LANG=vie+eng` trong `.env`. Chất lượng OCR tiếng Việt phải được kiểm tra trên scan thật.

## Kiểm chứng và bàn giao tiếp

```powershell
.\.venv-sop\Scripts\python.exe -m unittest sop_demo.test_schema sop_demo.test_app sop_demo.test_routing -v
```

Các test routing kiểm tra prose không gọi VLM, crop/merge trang hỗn hợp, biến đổi tọa độ, giữ graph/span, scan cần manifest và đường OCR bằng mock. Chưa kiểm chứng live Tesseract trên máy hiện tại vì chưa có engine; chưa gọi VLM mới cho nâng cấp này. Không xem test mock là bằng chứng chất lượng OCR/VLM.

Trên máy công ty cần thêm phép thử: PDF chỉ text phải có `vlm_calls=0`; PDF hỗn hợp phải giữ text ngoài ROI; scan chỉ text với manifest `[]` phải dùng OCR và không có API call; hai ảnh mẫu chỉ gửi vùng cấu trúc, vẫn đáp ứng cell share và diagram nguyên khối. Hướng cải thiện sau là layout detector cục bộ cho scan/borderless, thay heuristic/manual ROI, không dùng VLM làm classifier trang text.
