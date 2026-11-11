# Thử nghiệm extraction SOP: Docling và PP-StructureV3

Ngày: 11/11/2026. Phạm vi: PDF giả lập, inference local trên Windows CPU.

## Nhận định

**Cả hai baseline hiện tại đều chưa đáp ứng yêu cầu trích xuất đầy đủ thành phần.** Docling hữu ích cho native text và một số cấu trúc bảng, nhưng bỏ sót bảng có hình/sơ đồ bên trong. PP-StructureV3 khoanh được các vùng bảng chính rộng hơn trong bộ mẫu, nhưng cấu trúc ô và OCR tiếng Việt của cấu hình đang thử còn lỗi đáng kể. Cả hai đều không tách được các diagram trong bảng thành vùng riêng.

Do đó chưa nên chọn một parser làm toàn bộ pipeline hoặc xây UI sản phẩm dựa trên giả định parser đã giải quyết phần extraction. Hướng phù hợp tiếp theo là giữ các baseline này, thử riêng bước phát hiện thành phần bên trong bảng và kiểm tra cấu trúc/nội dung từng ô.

## Thiết lập và cách chấm

- 4 thiết kế trang: nội dung thông thường, lịch sử có ô gộp/chữ xoay, bảng bố cục có flowchart vector, bảng chứa text + ảnh + diagram.
- Mỗi thiết kế có digital, scan sạch, scan suy giảm và hybrid: 16 trang mỗi engine, 32 lượt inference trong kết quả cuối. Đây không phải 16 mẫu độc lập.
- Nhãn được ghi lúc tạo PDF, tách khỏi inference. Code chạy parser không đọc ground truth.
- Docling 2.150.0, docling-core 2.106.0, TableFormer accurate, EasyOCR 1.7.2 `vi/en`, native-aware, không force OCR toàn trang.
- PaddleOCR 3.7.0, PaddleX 3.7.2, PaddlePaddle 3.3.1; PP-StructureV3 image-first với OCR `vi`, PP-OCRv3 mobile detector và `latin_PP-OCRv3_mobile_rec`.
- CPU 4 threads cho mỗi engine; render phục vụ Paddle/overlay/crop 200 DPI. Cấu hình hiệu lực của Paddle và cấu hình đầy đủ của Docling được lưu riêng.
- Region matching 1:1, IoU >= 0.5. Kiểm tra grid bằng `(row, col, rowspan, colspan)`; chỉ đúng số hàng/cột chưa được coi là đúng grid.
- Text được đối chiếu bằng localized normalized token recall để tìm vùng cần xem lại; **không phải CER/WER hoặc số đo accuracy OCR**. Đánh giá này chịu ảnh hưởng của segmentation, bbox và gán text vào ô.

Mở [báo cáo trực quan](index.html) để xem source/ground truth cạnh overlay parser, geometry ô, bảng HTML, crop và raw JSON. [Evaluation JSON](evaluation.json) lưu chi tiết từng target và quy tắc chấm.

Hai bản scan đã được [audit lại ở mức content stream, nhiều extractor và source hash](../pdf/SCAN_AUDIT.md): đều image-only, không có text layer; thao tác chọn/copy chữ trong Edge không phải tiêu chí đủ để phân loại file. File PDF không thay đổi sau lần audit nên các source hashes của benchmark vẫn khớp.

## Kết quả chính trên bộ giả lập

| Kiểm tra | Docling | PP-StructureV3 |
|---|---:|---:|
| Trang xử lý thành công | 16/16 | 16/16 |
| Vùng bảng nhiều ô khớp nhãn | 8/12 | 12/12 |
| Lưới bảng chuẩn nhiều ô khớp toàn bộ index/span | 1/8 | 0/8 |
| Diagram được tách thành figure region khớp nhãn | 0/8 | 0/8 |
| Body image/diagram regions khớp nhãn, không tính logo | 4/16 | 3/16 |
| Nested image/diagram có liên kết rõ tới đúng table ancestor | 0/12 | 0/12 |

Các con số là đếm target trong bộ kiểm tra, không phải ước lượng chất lượng trên SOP thực. Việc khớp figure region cũng chưa đủ chứng minh đúng semantic type, đủ nội dung crop hay đúng cell ownership.

Bộ nhãn có thêm 4 khung một ô ở cuối trang lịch sử; cả hai engine xem chúng như text thay vì table. Bảng trên tách các khung này khỏi 12 bảng nhiều ô vì cách phân loại khung một ô có tính quy ước. Evaluation JSON vẫn giữ tất cả target, nên tổng table ở đó là 16.

Bốn bảng bố cục có flowchart được chấm region nhưng không ép vào phép chấm canonical grid: vùng lưu đồ không được tự gán rowspan hoặc quan hệ 1:1 với hàng mô tả. Tám bảng chuẩn nhiều ô là 4 bảng lịch sử và 4 bảng minh họa/nested.

## Những lỗi đã kiểm tra trực tiếp

### 1. Docling có thể đúng grid nhưng vẫn sai text ô

Ở trang lịch sử digital, Docling trả lưới 8x6 với 46 cell, đúng các ô gộp của nhãn. Tuy nhiên, ba ô vốn chỉ có `03` lại chứa:

- `03 DOCUMENT HISTORY`
- `03 LIỆU -`
- `03 LỊCH`

Đây là chữ xoay ở dải bên ngoài bị trộn vào bảng. Vì vậy bảng này chỉ đạt kiểm tra topology; không được coi là đã trích xuất đúng hoàn toàn.

Bằng chứng: [HTML bảng](runs/docling/baseline/sop_digital/page_002/table_00.view.html), [cell text checks](runs/docling/baseline/sop_digital/page_002/evaluation.json), [raw document](runs/docling/baseline/sop_digital/page_002/raw_document.json).

### 2. Flowchart vector vẫn bị xử lý thành text của bảng

Docling khoanh đúng vùng bảng ở trang lưu đồ, nhưng không xuất một picture cho flowchart. Nhiều node/connector không có thành phần diagram tương ứng. Log ghi `13 of 101 pdf cells ... were dropped from the table`. Đây là **PDF text cells**, không phải 13 ô bảng hoặc 13 paragraph chuẩn; cảnh báo cho thấy conversion thành công vẫn có thể đi kèm nội dung không được giữ trong table output.

PP-StructureV3 cũng chỉ xuất vùng table. Trên bản digital, HTML được diễn giải thành 10x5, có 32 logical cells trong HTML nhưng chỉ 27 cell boxes. Adapter đánh dấu association là `unresolved`, không tự nối 32 ô vào 27 bbox. Overlay geometry hiển thị các raw boxes với chỉ số `raw`.

Bằng chứng: [Docling parser log](runs/docling/baseline/sop_digital/page_003/parser.log), [Docling table](runs/docling/baseline/sop_digital/page_003/table_00.view.html), [Paddle raw JSON](runs/paddle/baseline/sop_digital/page_003/raw_paddle.json), [Paddle table](runs/paddle/baseline/sop_digital/page_003/table_00.view.html).

### 3. Bảng chứa hình và diagram không được bảo toàn thành cấu trúc chỉnh sửa được

Ở trang 4, Docling gán cả vùng biểu mẫu là `picture`; không tạo table/cells, trong khi text bên trong vẫn xuất hiện thành nhiều text items. Hình thiết bị và diagram bên trong không được tách riêng.

PP-StructureV3 nhận vùng table nhưng cũng không xuất hai asset bên trong thành components riêng. Trên bản digital, HTML của bảng 3x2 được nhãn lại thành 6x3; có 13 HTML cells và 9 cell boxes. Việc có một crop của toàn bộ bảng chỉ giúp xem lại, chưa đáp ứng thao tác thay/xóa từng hình hoặc diagram.

Bằng chứng: [Docling overlay](runs/docling/baseline/sop_digital/page_004/overlay.png), [Docling raw document](runs/docling/baseline/sop_digital/page_004/raw_document.json), [Paddle table](runs/paddle/baseline/sop_digital/page_004/table_00.view.html), [Paddle evidence](runs/paddle/baseline/sop_digital/page_004/evidence.json).

### 4. Chọn `vi` không đồng nghĩa OCR đã đủ tốt

Trong ví dụ digital chạy image-first, Paddle nhận heading `QUY TRÌNH THỰC HIỆN / WORKFLOW` thành `QUY TRINH THU'C HIEN/WORKELOW`. Nhiều dấu tiếng Việt bị mất hoặc chuyển sang ký tự khác. Docling giữ native text của ví dụ này đúng hơn, nhưng EasyOCR trên scan/ảnh cũng có lỗi, ví dụ chữ trong ảnh thiết bị.

Đây là nhận xét về đúng model/config đang thử, không phải kết luận cho mọi model trong PaddleOCR hoặc mọi OCR engine mà Docling hỗ trợ.

### 5. Biên của image cần có quy tắc annotation

Trên trang nội dung thông thường, ảnh nguồn chứa cả thiết bị và các nhãn bên phải. Bản scan suy giảm của Paddle chỉ khoanh phần thiết bị, khiến IoU với vùng ảnh nguồn thấp hơn ngưỡng. Target đó được tính là không khớp biên, không có nghĩa toàn bộ ảnh đã biến mất. Với digital PDF, native image placement/bytes là bằng chứng bổ sung hữu ích để bảo toàn asset gốc.

## Đề xuất vòng tiếp theo

1. **Ưu tiên diagram và nested figure detection.** Chạy phân tích riêng trong vùng bảng/container và kiểm tra khả năng gom toàn bộ sơ đồ, gồm mũi tên/nhãn. So sánh layout trên crop với vector grouping cho digital và CV/raster refinement cho scan. Không dùng bbox nhãn hoặc tọa độ hardcode của bộ mẫu làm bộ phát hiện.
2. **Tách table region, logical grid và content assignment.** Khi layout nhận nhầm bảng thành picture, thử native line/grid hoặc detector đối chứng để tạo candidate table. Khi HTML và geometry không khớp, giữ trạng thái chưa xác định; chưa đưa vào editor như một bảng chắc chắn đúng.
3. **Kiểm tra text placement bằng geometry và orientation.** Ca chữ xoay bị trộn vào ba ô cho thấy cần kiểm soát việc gán native/OCR tokens vào cell. Giữ các token chưa gán được cùng cảnh báo để có thể đối chiếu, thay vì chỉ tin document JSON sau cùng.
4. **Đánh giá OCR tiếng Việt riêng trên vùng đã xác định.** Native text đáng tin là nguồn ưu tiên trên digital. Chọn OCR thay thế sau khi đo trên cùng vùng scan; chưa cần phối hợp toàn bộ output của nhiều parser.
5. **Mở rộng dữ liệu sau khi sửa được các lỗi này.** Thêm nhiều họ template, skew/watermark, bảng xuyên trang và PDF thực tế. Bộ mẫu hiện tại chỉ hỗ trợ quyết định kỹ thuật ban đầu.

Nếu cần chọn nền tảng cho bước thử tiếp: dùng Docling làm nguồn native text/structured document tham khảo và PP-StructureV3 làm đối chứng layout/table. Chưa khóa toàn bộ hệ thống vào schema hoặc cấu trúc nội bộ của một engine.

## Runtime, kiểm tra và giới hạn

- Máy chạy thực tế: Windows CPU, Python 3.11.7, 22 logical CPUs, RAM OS báo khoảng 33.68 GB; cấu hình parser dùng 4 threads. Chưa chạy trên Mac M4 hoặc T4.
- Peak RSS sampled quan sát khoảng 3.65 GiB cho Docling và 1.70 GiB cho Paddle; là process tree được lấy mẫu mỗi 200 ms, không phải giới hạn bộ nhớ tuyệt đối hoặc VRAM.
- Một phần lượt chạy cuối diễn ra đồng thời trên cùng máy. Thời gian từng trang vẫn được lưu nhưng **không dùng để xếp hạng tốc độ**; startup/tải model được ghi riêng và cache đã có ở lượt cuối.
- Hai môi trường qua `pip check`. Tám kiểm tra evaluator qua, bao gồm coordinate conversion, merged cells, partial grids, 1:1 region matching, crop thiếu và table ancestor qua group.
- Raw document JSON của Docling là output document công khai; chưa xuất toàn bộ intermediate OCR/native token traces nội bộ. Raw Paddle JSON giữ overall OCR và table results. Kết luận về hierarchy đã đối chiếu với raw output của các ca nêu trên, không chỉ adapter.
- Adapter Paddle chỉ gán bbox theo thứ tự khi số HTML cells bằng số boxes (`ordered_1_to_1`); đây chưa phải chứng minh association đúng. Khi số lượng lệch, bbox logical cell để trống và raw geometry vẫn được giữ.
- Không thực hiện fine-tuning, custom vector grouping, native-text recovery fusion hoặc sửa output parser bằng ground truth trong vòng baseline này.

Các khóa phiên bản và lệnh tái lập nằm trong [hướng dẫn playground](../../playground/README.md). [Model inventory](model_inventory.json) ghi hash của model/config đã tải; [package manifest](package_manifest.json) và manifest từng trang xác định đúng các artifacts của lượt thành công hiện tại. Trọng số và virtualenv không đi kèm gói chia sẻ.
