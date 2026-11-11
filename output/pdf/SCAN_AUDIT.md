# Kiểm tra lại hai PDF scan giả lập

Kết quả: **cả hai file trong repo là image-only PDF**, không chứa text layer/OCR layer. Không cần thay nội dung PDF để sửa hiện tượng copy chữ trong trình xem.

| Kiểm tra | Scan sạch | Scan suy giảm |
|---|---:|---:|
| Số trang | 4 | 4 |
| Ảnh raster trên mỗi trang | 1 | 1 |
| Kích thước ảnh trang | 1323 x 1871 px | 1323 x 1871 px |
| Lệnh vẽ chữ `Tj`, `TJ`, `'`, `"` | 0 | 0 |
| Native text qua pypdf | 0 ký tự | 0 ký tự |
| Native text qua PyMuPDF | 0 ký tự | 0 ký tự |
| Ký tự nhận được qua pdfplumber | 0 | 0 |
| Nội dung text qua Poppler `pdftotext` | 0 ký tự | 0 ký tự |
| Annotation | 0 | 0 |
| Hash khớp manifest và nguồn benchmark | Có | Có |

Poppler chỉ trả 4 ký tự form-feed ngăn trang, không có text nội dung. Mỗi trang chỉ có một image XObject phủ trang; không có vector drawing paint hoặc text-show operators. Catalog không có structure tree hoặc AcroForm.

ReportLab có thêm một resource font Helvetica và chuỗi khởi tạo text rỗng `BT /F1 ... ET`. Đây là thiết lập mặc định, không có lệnh vẽ chữ hoặc ký tự trong đó; việc xuất hiện font resource không đồng nghĩa có text layer.

Hai SHA256:

- `sop_scan_clean.pdf`: `8949ba7d87671613df7e2cc072fad1026d66ca872da9c464e114b214501b839b`
- `sop_scan_degraded.pdf`: `76f623b06e718646e61e9699fb74d9b661c3706e684ff6278f8e15f40eba03b2`

Các hash trùng file đã dùng cho các lượt Docling/Paddle; không có thay đổi PDF và không cần chạy lại benchmark vì lần kiểm tra này.

## Vì sao vẫn có thể chọn/copy chữ trong Edge?

Người dùng xác nhận mở trực tiếp file trong repo bằng Edge. Với cấu trúc PDF ở trên, việc chọn/copy chữ nhiều khả năng là do nhận dạng chữ trong trình xem hoặc một tính năng hỗ trợ của trình xem, không phải text layer được nhúng sẵn. Đây là suy luận từ kiểm tra file và hiện tượng người dùng báo; chưa trực tiếp kiểm tra setting/build Edge trên máy người dùng.

Một [thảo luận Microsoft Q&A](https://learn.microsoft.com/zh-cn/answers/questions/5983548/edge-pdf) cũng ghi nhận hiện tượng Edge tự nhận dạng chữ khi đọc PDF. Đây là nguồn thảo luận cộng đồng, không phải đặc tả bảo đảm hành vi trên mọi phiên bản Edge.

PDF image-only vẫn có thể được trình xem OCR để chọn/copy. Không dùng thao tác bôi đen/copy làm tiêu chí duy nhất phân biệt digital và scan. Tạo lại image-only PDF cũng không ngăn trình xem nhận dạng lại chữ từ ảnh.

Đây là scan **giả lập từ ảnh raster của trang**, chưa phải dữ liệu quét từ giấy bằng máy scan. Các hạn chế về skew, perspective và đa dạng thiết bị scan đã được ghi trong README của bộ mẫu.

## Kiểm tra tái lập

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/audit_scan_pdfs.py
```

Script kiểm tra content streams và Form XObjects, ba thư viện độc lập, Poppler nếu có, source hashes và hai negative controls: digital phải phát hiện text, hybrid chỉ có trang 2 là image-only. Kết quả máy đọc được nằm trong `scan_audit.json`.

Phần `verify()` của generator cũng đã bổ sung kiểm tra không có text-show operators và chỉ có image XObject cho hai scan fixtures. Những kiểm tra này chỉ đọc PDF; không thêm OCR hoặc sửa nội dung file.
