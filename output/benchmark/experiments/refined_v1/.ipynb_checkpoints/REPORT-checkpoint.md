# Refinement v1: kết quả và thời gian chạy

Đã chạy đủ **16 trang/engine, 32 lượt trang thành công**, trên 4 PDF giả lập có cùng 4 thiết kế trang. Baseline được giữ nguyên; kết quả mới ở run `refined_v1`. Đây là thử nghiệm kỹ thuật trên dữ liệu dùng phát triển luật, chưa phải đánh giá SOP thực hoặc tập held-out.

## Thay đổi đã triển khai

- Khôi phục bảng, ảnh và từ có tọa độ từ PDF native. Text trong ô được dựng lại từ từ gốc và geometry, giúp tránh text tiêu đề ngoài bảng bị ghép vào ô.
- Dựng lại lưới bảng có đường kẻ, hàng/cột và merged cells; kiểm tra occupancy và tính chữ nhật trước khi nhận. Bảng của parser được giữ làm fallback có cờ review.
- Tách diagram bằng các hình khép kín và connector; tìm ảnh bên trong ô, gán `parent_ref` đến cell hoặc table phù hợp. Diagram trải nhiều row bands có parent ở table. Các ứng viên CV vẫn cần review.
- Chỉ loại đường kẻ bảng trên mask phân tích. Crop ảnh/diagram lấy từ trang nguồn để giữ nguyên nhánh, mũi tên, nhãn và chất lượng gốc.
- Giữ token OCR trước table assembly của Docling, kể cả điểm thấp; token confidence <0.5 và ô liên quan có cờ review. Native text được ưu tiên khi đủ bằng chứng; OCR xung đột và nguồn thô được giữ để kiểm tra.
- Lưu riêng parser evidence/HTML gốc, geometry candidates, token ownership, mask, nguồn code theo hash và thời gian từng giai đoạn.

Không đổi nội dung các PDF scan. Cả hai vẫn là image-only; xem [kết quả audit](../../../pdf/SCAN_AUDIT.md). Việc Edge cho chọn chữ không đủ chứng minh file có text layer.

## Đối chiếu chất lượng

Mỗi ô dưới đây là **baseline → refinement** trên cùng dữ liệu. Grid exact gồm row/col/rowspan/colspan. Detection vùng dùng matching 1:1, IoU ≥ 0.5; không chứng minh hiểu ngữ nghĩa diagram.

| Engine | Grid chuẩn đúng / 8 | Body figures / 16 | Diagram regions / 8 | Liên kết hình trong bảng / 12 | Text ô đúng tuyệt đối / 212 |
|---|---:|---:|---:|---:|---:|
| docling | 1 → 8 / 8 | 4 → 16 / 16 | 0 → 8 / 8 | 0 → 12 / 12 | 134 → 171 / 212 |
| paddle | 0 → 8 / 8 | 3 → 16 / 16 | 0 → 8 / 8 | 0 → 12 / 12 | 16 → 109 / 212 |

- 12 bảng nhiều ô (history, layout process, bảng hình) được kiểm tra vùng; 8 bảng history/bảng hình có nhãn topology đầy đủ để tính grid exact. Bảng layout process không bị ép thành lưới chuẩn vì diagram cắt qua nhiều dải hàng.
- 4 hộp phê duyệt một ô vẫn được evaluator liệt kê như table target, nhưng refinement giữ dạng vùng nội dung thay vì bảng. Vì vậy tổng table detection có thể là 12/16; đây không phải 4 bảng nhiều ô bị mất.
- Bảng trên chỉ tính body figures. Nếu tính cả logo/header furniture thì Docling khớp 32/32 vùng hình; Paddle khớp 16/32 và có 1 vùng dư. Paddle vẫn chưa xuất 16 logo thành figure riêng, dù một số được nhận thành header text; chưa thể coi là trích xuất đủ mọi loại thành phần.
- 12/12 nested links là liên kết đến đúng bảng; 8 trường hợp có ô sở hữu cụ thể đúng index/span. 4 diagram dài còn lại gắn ở cấp table, không khẳng định đã chia được các bước theo hàng.
- Text denominator 212 gồm 208 ô text của bảng nhiều ô và 4 hộp một ô. `compared` trong JSON cho biết bao nhiêu ô có đúng index/span để so text. Exact text chuẩn hóa NFC, chữ hoa/thường và khoảng trắng; vẫn tính lỗi dấu, ký tự, dấu câu. Không dùng con số này làm OCR CER/WER.
- Native text recovery sửa được cả 46 ô history ở trang digital, gồm các ô `03` từng bị ghép thêm tiêu đề. Scan vẫn có lỗi nhận dạng và ô thiếu chữ; không đạt yêu cầu “đúng tất cả thành phần” trên dữ liệu thực.
- Bật tùy chọn Paddle cells-to-HTML riêng lẻ **không giải quyết đủ lỗi topology**: trang digital 3 vẫn trả HTML 13×7 / 17 cells so với 27 cell boxes. Kết quả grid cải thiện trong bảng trên đến từ lớp geometry refinement độc lập; raw parser output vẫn được giữ nguyên để đối chiếu.

Xem [báo cáo trực quan](index.html), [comparison.json](comparison.json) và [evaluation.json](evaluation.json). Raw output, overlay, table HTML, crop và liên kết sở hữu có trong từng trang của báo cáo.

## Thời gian thực đo

Windows CPU, cấu hình 4 threads/engine, RAM máy khoảng 32 GB; renderer 200 DPI. Hai engine chạy **tuần tự**, model có sẵn trong cache và inference offline. Ảnh render đầu vào cũng đã cache: số dưới đây không bao gồm việc render lại toàn bộ một bộ PDF mới, tải model, viết code, smoke test, đánh giá hoặc nén ZIP. Mỗi engine khởi tạo process/model mới; không tái sử dụng process giữa hai engine.

Đơn vị giây. Tổng process gồm interpreter/import, model startup, 16 trang và kết thúc process; không cộng thêm startup vào cột này.

| Engine | Khởi tạo model | Xử lý 16 trang | TB/trang | Min–max/trang | Tổng process | Peak RSS trang (GiB) |
|---|---:|---:|---:|---:|---:|---:|
| docling | 28.30 | 312.67 | 19.54 | 6.87–36.63 | 343.96 | 3.88 |
| paddle | 15.09 | 661.76 | 41.36 | 24.69–68.96 | 678.63 | 1.88 |

Tổng wall time chạy cả hai engine: **1022.59 giây (17 phút 2.6 giây)**. RSS lấy mẫu process tree mỗi 200 ms, không phải peak tuyệt đối hoặc VRAM.

Phân rã phần xử lý 16 trang; refinement bao gồm cả ghi diagnostics, export cuối gồm evidence/overlay/crops:

| Engine | Chuẩn bị input | Parser + raw export | Refinement + debug export | Refinement TB/trang | Evidence + crop export |
|---|---:|---:|---:|---:|---:|
| docling | 0.47 | 288.33 | 17.45 | 1.09 | 6.13 |
| paddle | 0.16 | 637.85 | 17.66 | 1.10 | 5.77 |

| Engine | PDF (4 trang) | Tổng xử lý | TB/trang |
|---|---|---:|---:|
| docling | sop_digital.pdf | 98.64 | 24.66 |
| docling | sop_hybrid.pdf | 59.33 | 14.83 |
| docling | sop_scan_clean.pdf | 77.10 | 19.27 |
| docling | sop_scan_degraded.pdf | 77.61 | 19.40 |
| paddle | sop_digital.pdf | 235.69 | 58.92 |
| paddle | sop_hybrid.pdf | 117.01 | 29.25 |
| paddle | sop_scan_clean.pdf | 196.71 | 49.18 |
| paddle | sop_scan_degraded.pdf | 112.34 | 28.09 |

Đây là một lượt đo trên máy hiện tại. Không suy ra tốc độ GPU/M4 hay throughput production. Baseline cũ chạy xen kẽ và có phạm vi timing khác nên không dùng để tính speedup. Số đầy đủ, command và thời điểm UTC ở [timing.json](timing.json); từng trang có `status.json`, từng run có `initialization.json`/`execution.json`.

## Giới hạn còn lại và hướng tiếp theo

Ưu tiên hiện tại vẫn là trích xuất đủ và đúng thành phần. Refinement là lớp thu hồi bằng chứng phù hợp để tiếp tục thử nghiệm; chưa đủ cơ sở chọn engine cuối cùng hoặc cam kết accuracy. Luật hiện giả định trang thẳng, bảng có đường kẻ, diagram có các hình khép kín nối nhau. Chưa kiểm tra bảng không đường kẻ, trang nghiêng mạnh, sơ đồ tự do hay SOP thực. Các ngưỡng đã được phát triển trên chính 4 thiết kế này; cần một tập mới, không dùng để chỉnh luật, trước khi kết luận tổng quát hóa.

OCR tiếng Việt trên scan vẫn là hạn chế rõ rệt. Cần benchmark OCR/crop OCR riêng trên lỗi còn lại và đưa vùng chưa chắc chắn vào review; việc giữ token điểm thấp giúp truy vết nhưng không tự sửa ký tự sai. Text xoay còn có thể chỉ nằm trong token evidence thay vì paragraph block. `parent_ref` là ownership dùng ở vòng thử này; chưa triển khai schema xuất sản phẩm.

Kiểm tra tự động: 14 unit tests cho matching/evaluation, ownership, grid/merged cells và connected-shape grouping; package builder kiểm tra đủ 32 trang thành công, fingerprint đồng nhất, source snapshot/hash, local HTML links và ZIP CRC. Crop diagram/ảnh được kiểm tra trực quan. Các kiểm tra kỹ thuật này không thay thế đánh giá trên tài liệu thực.

Lệnh tái chạy và mô tả code: [playground README](../../../../playground/README.md). Gói ZIP giữ kết quả refined và số đối chiếu baseline; toàn bộ raw artifacts baseline vẫn nằm riêng trong repo/gói baseline cũ.
