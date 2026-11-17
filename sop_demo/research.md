# Model selection and experiment log

Ngày kiểm tra: 2026-11-17. Kết quả dưới đây là thử nghiệm route trên proxy hiện tại, không phải benchmark độc lập của model gốc.

## Kết luận hiện tại

Chưa đủ bằng chứng để chọn model tốt nhất cho toàn pipeline. Kiểm tra đọc ảnh ngắn đã thành công, nhưng chưa có bản JSON đầy đủ đạt yêu cầu từ VLM. Không dùng output rỗng làm demo thành công.

| Deployment trong proxy | Kiểm tra thực tế | Vai trò đề xuất |
|---|---|---|
| `qwen.qwen3-vl-235b-a22b` | Đọc đúng tiêu đề và 3 node chính; prompt schema đầy đủ trả rỗng, lần repair vẫn rỗng | Ứng viên inventory/crop; cần thử pass nhỏ trước khi chọn |
| `global.anthropic.claude-sonnet-5` | Đọc đúng tiêu đề và 3 node; request JSON đầy đủ gặp nginx 504 | Ứng viên reasoning/review; mặc định thử nghiệm, chưa phải winner |
| `global.anthropic.claude-sonnet-4-6` | Request đầy đủ gặp nginx 504 | Chưa đánh giá được chất lượng |
| `azure/gpt-4o` | Đọc đúng tiêu đề và 3 node; route báo giới hạn 4096 output tokens | Cần chia pass/crop; không phù hợp full-page schema dài với cấu hình hiện tại |
| `gpt-4o` | Proxy báo thiếu upstream OpenAI key | Không dùng cho tới khi proxy được cấu hình |
| `claude-sonnet` | Proxy báo thiếu upstream Anthropic key | Không dùng cho tới khi proxy được cấu hình |

Danh sách `/models` chỉ chứng minh alias được liệt kê. Không chứng minh upstream key, capability hoặc token limits hoạt động. Key LiteLLM không phải key hãng. Không đổi `.env` của người dùng.

Streaming đã được thêm để tránh thời gian chờ không có dữ liệu ở reverse proxy, nhưng lần chạy xác minh streaming bị người dùng từ chối nên **chưa kiểm chứng live**. Không bảo đảm streaming sửa được 504 nếu thời gian tới token đầu tiên quá dài. Không tiếp tục gọi model sau lần từ chối đó.

## Nghiên cứu từ nguồn chính thức

- [LiteLLM Vision](https://docs.litellm.ai/docs/completion/vision): proxy dùng message image_url, hỗ trợ ảnh base64. OpenAI SDK ở client không có nghĩa backend là OpenAI; alias proxy quyết định routing.
- [LiteLLM Structured Outputs](https://docs.litellm.ai/docs/completion/json_mode): json_object/json_schema phụ thuộc model/provider. Cần kiểm tra capability thay vì coi mọi model hỗ trợ strict schema. Local validation vẫn cần thiết cho reference/span.
- [Qwen3-VL model card](https://huggingface.co/Qwen/Qwen3-VL-235B-A22B-Instruct): model image-text-to-text, có triển khai qua endpoint OpenAI-compatible. Là ứng viên cho document perception; card không chứng minh accuracy trên SOP này.
- [Claude vision](https://platform.claude.com/docs/en/build-with-claude/vision): nhận ảnh và có hướng dẫn workflow tọa độ. Chọn Sonnet làm ứng viên review dựa trên khả năng vision/reasoning; phải đo trên tập SOP có gán nhãn.
- [Gemini document processing](https://ai.google.dev/gemini-api/docs/document-processing): hỗ trợ hiểu PDF gồm text, hình, bảng và diagram. Có thể bổ sung Flash/Pro vào benchmark, nhưng `/models` của proxy hiện tại không có Gemini nên chưa thử và không coi là sẵn dùng.

Không sử dụng giá niêm yết để khẳng định chi phí proxy. Giá phụ thuộc deployment, provider, cache và quy tắc của tổ chức. Demo ghi usage từng call; công thức ước lượng là input_tokens × input_rate / 1e6 + output_tokens × output_rate / 1e6, cộng image/cache rate nếu provider tách riêng. Cần rate của proxy mới có tổng tiền đáng tin.

## Thiết kế thí nghiệm tiếp theo

1. Dùng 2 ảnh mẫu và các trang PDF/Word có flowchart làm golden set; gán nhãn node, directed edges, description alignment và shared spans. Tách các mẫu dùng tune prompt khỏi tập test.
2. Chạy inventory trước, tracing lưu đồ thứ hai, logical table/relation thứ ba. Mỗi pass chỉ nhận schema con, giảm output token và tránh model trả schema rỗng. Giữ ID ổn định và kiểm tra toàn vẹn khi ghép.
3. So sánh Qwen3-VL với Sonnet trên cùng ảnh, cùng crop và cùng budget. Đo cả baseline một pass lẫn pipeline nhiều pass để phân biệt cải thiện do model và do hệ thống.
4. Đo CER; precision/recall node, cạnh có hướng và nhãn; accuracy rowspan/colspan; relation F1, đặc biệt many-to-one; tỷ lệ phải sửa, latency và chi phí/trang.
5. Bổ sung crop review theo ambiguity và verifier độc lập. Không coi việc model tự review cùng câu trả lời là bằng chứng khách quan.

Pipeline hiện thực hiện nay là baseline full-page extraction + review, **chưa phải** pipeline nhiều pass nêu ở trên. Đây là hướng thử tiếp theo sau khi có route trả output dài ổn định hoặc có ngân sách chia nhỏ call.
