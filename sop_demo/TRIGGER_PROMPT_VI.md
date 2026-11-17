# Prompt chạy tiếp pipeline SOP trên máy công ty

Sao chép nội dung trong khối dưới đây vào agent đang mở tại root repo. Không cần dán API key vào hội thoại; cấu hình `.env` cục bộ trước.

```text
Hãy tiếp tục thực thi và kiểm chứng dự án SOP VLM trong repo này trên máy công ty. Tôi muốn bạn chạy pipeline thật và sửa các lỗi cần thiết để có JSON đầu ra có thể kiểm tra trên UI, không chỉ đưa kế hoạch hay giải thích cách chạy.

Đọc trước:
- AGENTS.md áp dụng cho workspace nếu có.
- sop_demo/HANDOFF_VI.md
- sop_demo/HYBRID_VI.md (nâng cấp mới nhất, ưu tiên hơn mô tả baseline cũ)
- sop_demo/README.md
- sop_demo/research.md
- sop_demo/schema.py và sop_demo/extract.py
Sau đó đọc các module liên quan khi cần. Hướng mới ở sop_demo/, độc lập với phương pháp cũ trong playground/. Giữ nguyên công việc có sẵn của người dùng.

Bài toán:
Đọc SOP từ PDF có text, PDF scan và DOCX; giữ text, bảng, cell, flowchart node, mũi tên/nhãn và relation giữa các component trong JSON trung gian. Bảng cần các hàng logic để biểu diễn relation theo cả gióng ngang và ngữ nghĩa. Lưu đồ phải giữ nguyên thành một diagram xuyên các hàng; không cắt hoặc nhân bản node để ép vào hàng. Text dùng chung phải là một component được tham chiếu, hiển thị bằng rowspan khi các hàng liên tiếp. UI demo chỉ cần sửa text, không cần editor relation hay API HTTP. Chưa triển khai chuyển đổi JSON SIPOC/RACI cuối hoặc Excel. Ưu tiên độ chính xác, chi phí hợp lý.

Yêu cầu bổ sung bắt buộc: chạy mode hybrid mặc định. Text thông thường lấy native từ PDF/DOCX render hoặc OCR cục bộ cho scan; chỉ bảng/diagram mới dùng VLM. Không tự fallback cả trang prose sang VLM. Kiểm tra routing.py, file routing.json và crop thực tế. Scan/ảnh cần manifest vùng trong bản hiện tại; hai ảnh mẫu toàn bảng có thể dùng sop_demo/regions-full-structure.example.json. Với scan hỗn hợp xác định ROI từ ảnh; [] xác nhận trang chỉ prose. Cài Tesseract + vie/eng và requirements-ocr.txt nếu cần. Text bên trong vùng bảng/node có thể để VLM xử lý với native/OCR evidence. Báo rõ detector đang heuristic/manual, chưa tự động nhận dạng scan layout.

Thêm test_routing vào lệnh test. Kiểm chứng prose có 0 VLM call, mixed page giữ text ngoài ROI và tọa độ crop được đổi đúng, scan prose có 0 call và OCR thật. Nếu cải thiện tự động nhận diện layout, dùng công cụ/model cục bộ, giữ nguyên quy tắc chỉ gọi VLM trên vùng cấu trúc. Không dùng full-vlm mặc định để vượt lỗi routing/OCR; chỉ dùng khi chủ động chạy baseline so sánh và ghi rõ.

Bạn được phép dùng credential đã cấu hình trong .env để gọi LiteLLM và gửi các tài liệu mẫu trong document/ phục vụ nhiệm vụ này. Không in key hoặc ghi key vào log/code. Tự tiến hành các lần chạy cần thiết với số call hữu hạn; dùng probe và trang mẫu trước để tránh chạy cả tập bằng một route chưa kiểm chứng. Không tự thay đổi cấu hình server proxy. Nếu có trở ngại quyền thực thi của môi trường, xử lý qua cơ chế cấp quyền của môi trường đó.

Thực hiện theo thứ tự:
1. Kiểm tra môi trường Python; tạo venv riêng nếu cần, cài sop_demo/requirements.txt và chạy test_schema + test_app. Kiểm tra renderer Word/LibreOffice cho DOCX. Dùng đường dẫn theo workspace hiện tại, không hard-code đường dẫn máy cũ.
2. Đọc tên biến cấu hình mà không tiết lộ giá trị bí mật. List deployment từ proxy; dùng model có vision, không mặc định dùng LITELLM_MODEL nếu đó là model text-only. Chạy probe đọc ảnh ngắn. Các alias trong research.md là lịch sử thử nghiệm, không bảo đảm còn hoạt động ở đây.
3. Xác minh streaming và token limit bằng route thật. Baseline hiện stream=True với include_usage; phiên trước chưa kiểm chứng live. Sửa tương thích provider nếu cần, ghi rõ thay đổi và kết quả. Kiểm tra các mục “Những điểm cần kiểm tra hoặc sửa tiếp” trong HANDOFF_VI.md, nhất là review sau repair và logging validation/API errors.
4. Chạy border.png rồi no_border.png, mỗi lần vào thư mục run mới. Không sử dụng manual-schema-example hoặc các output Qwen rỗng cũ như kết quả VLM. Giữ raw response, usage, image assets và JSON để đối chiếu.
5. Nếu full-page schema quá dài, timeout, rỗng hoặc chất lượng kém, chẩn đoán trước khi retry. Có thể tách inventory text/node, tracing edges và suy luận table/relations thành các pass nhỏ; crop vùng cần đọc rõ nhưng vẫn giữ toàn trang làm ngữ cảnh. Giữ ID ổn định, quy đổi tọa độ crop về trang và validate kết quả merge. Không hard-code nội dung/toạ độ mẫu để giả lập output model, không bỏ node/relations chỉ để vượt validator. Không retry vô hạn hoặc gọi mọi model một cách không kiểm soát.
6. Đối chiếu bằng mắt và cấu trúc với ảnh nguồn. Với border.png, kiểm tra riêng hai node HCN TTC/NM có mô tả riêng nhưng dùng chung “Hằng ngày” và nhóm trách nhiệm. Tính đủ các hàng khác cũng dùng chung component trong ảnh gốc. Giữ lưu đồ nguyên khối; kiểm tra hướng mũi tên, document inputs và nhãn các nhánh vòng lặp.
7. Chọn các trang thật có bảng/lưu đồ trong ít nhất một PDF và một DOCX ở document/ để chạy thử. Khi trang mẫu hoạt động và phạm vi/chi phí hợp lý, chạy toàn tài liệu mẫu để kiểm tra trang text, bảng và lưu đồ. Chưa nối bảng/lưu đồ xuyên trang thì báo rõ; không bịa relation xuyên trang.
8. Chạy UI Streamlit local, mở output VLM mới, kiểm tra bảng chia hàng/cell gộp/lưu đồ, thử sửa text và lưu document.edited.json. Xác minh ID, edges và relations không bị mất. Nếu không có khả năng kiểm tra trực quan trình duyệt, chạy AppTest và báo rõ giới hạn thay vì nhận đã kiểm tra visual.
9. Nếu có từ hai deployment hoạt động phù hợp, đối chiếu trên cùng một mẫu trước khi khuyến nghị model. Nếu chỉ một model chạy được, báo kết quả của model đó; chưa gọi là model tốt nhất. Không suy ra accuracy từ schema hợp lệ hay confidence tự báo. Chỉ tính tiền khi có rate proxy đáng tin, còn lại báo token usage và số call.
10. Ghi sop_demo/COMPANY_RUN_REPORT.md gồm: môi trường, model/route, file/trang đã chạy, lệnh tái chạy, đường dẫn output, token usage, kết quả kiểm tra relation/flow/cell, lỗi còn lại và code đã sửa. Cập nhật hướng dẫn khi behavior đổi; đồng bộ JSON Schema nếu sửa Pydantic models. Chạy lại các test có liên quan.

Tiêu chí kết thúc:
Có output VLM thực tế cho các mẫu đã chạy, validate đạt và được đối chiếu về nội dung/quan hệ; UI mở/sửa/xuất được JSON. Nếu còn lỗi ngoài khả năng xử lý như credential upstream, quyền truy cập hoặc timeout server, báo chính xác call nào thất bại, bằng chứng đã che bí mật, phần đã hoàn tất và việc cụ thể cần phía công ty xử lý. Không đánh dấu pipeline end-to-end thành công khi chỉ probe hoặc ví dụ viết tay chạy được.

Bắt đầu kiểm tra và chạy ngay. Chỉ hỏi khi thiếu thông tin thiết yếu mà repo/.env/tài liệu bàn giao không cung cấp; các lựa chọn triển khai thông thường hãy tự xử lý và ghi lại trong báo cáo.
```
