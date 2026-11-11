"""Write the refinement findings from measured artifacts, without running inference."""
import argparse
from collections import defaultdict
from common import BENCHMARK, read_json


def build(run_name="refined_v1"):
    directory = BENCHMARK / "experiments" / run_name
    timing = read_json(directory / "timing.json")
    comparison = read_json(directory / "comparison.json")
    evaluation = read_json(directory / "evaluation.json")
    assert len(timing["engines"]) == 2
    assert all(e["returncode"] == 0 and e["execution"]["processed_pages"] == 16
               and e["execution"]["failed_pages"] == 0 for e in timing["engines"])
    quality = []
    times = []
    phases = []
    fixtures = []
    for engine in ("docling", "paddle"):
        before = next(s for s in comparison["baseline"] if s["engine"] == engine)
        after = next(s for s in comparison["refined"] if s["engine"] == engine)
        quality.append(
            f"| {engine} | {before['complete_grids_exact']} → {after['complete_grids_exact']} / 8 "
            f"| {before['figure_detection']['body_matched']} → {after['figure_detection']['body_matched']} / 16 "
            f"| {before['figure_detection']['diagram_matched']} → {after['figure_detection']['diagram_matched']} / 8 "
            f"| {before['nested_table_links']} → {after['nested_table_links']} / 12 "
            f"| {before['cell_text_evaluation']['exact']} → {after['cell_text_evaluation']['exact']} / 212 |")
        record = next(e for e in timing["engines"] if e["engine"] == engine)
        execution = record["execution"]
        rows = [r for r in evaluation["pages"] if r["engine"] == engine]
        assert len(rows) == 16 and all(r["state"] == "success" for r in rows)
        seconds = sorted(r["seconds"] for r in rows)
        peak = max(r["peak_rss_bytes"] for r in rows) / 1024**3
        times.append(f"| {engine} | {record['initialization']['seconds']:.2f} "
                     f"| {execution['page_seconds']:.2f} | {execution['page_seconds']/16:.2f} "
                     f"| {seconds[0]:.2f}–{seconds[-1]:.2f} | {record['process_wall_seconds']:.2f} | {peak:.2f} |")
        p = execution["phase_seconds"]
        phases.append(f"| {engine} | {p['input_preparation']:.2f} | {p['parser_and_raw_export']:.2f} "
                      f"| {p['refinement_and_debug_export']:.2f} "
                      f"| {p['refinement_and_debug_export']/16:.2f} | {p['evidence_and_crop_export']:.2f} |")
        by_pdf = defaultdict(list)
        for row in rows:
            by_pdf[row["pdf"]].append(row["seconds"])
        fixtures.extend(f"| {engine} | {pdf} | {sum(values):.2f} | {sum(values)/len(values):.2f} |"
                        for pdf, values in sorted(by_pdf.items()))
    elapsed = timing["total_wall_seconds"]
    report = f"""# Refinement v1: kết quả và thời gian chạy

Đã chạy đủ **16 trang/engine, 32 lượt trang thành công**, trên 4 PDF giả lập có cùng 4 thiết kế trang. Baseline được giữ nguyên; kết quả mới ở run `{run_name}`. Đây là thử nghiệm kỹ thuật trên dữ liệu dùng phát triển luật, chưa phải đánh giá SOP thực hoặc tập held-out.

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
{chr(10).join(quality)}

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
{chr(10).join(times)}

Tổng wall time chạy cả hai engine: **{elapsed:.2f} giây ({int(elapsed//60)} phút {elapsed%60:.1f} giây)**. RSS lấy mẫu process tree mỗi 200 ms, không phải peak tuyệt đối hoặc VRAM.

Phân rã phần xử lý 16 trang; refinement bao gồm cả ghi diagnostics, export cuối gồm evidence/overlay/crops:

| Engine | Chuẩn bị input | Parser + raw export | Refinement + debug export | Refinement TB/trang | Evidence + crop export |
|---|---:|---:|---:|---:|---:|
{chr(10).join(phases)}

| Engine | PDF (4 trang) | Tổng xử lý | TB/trang |
|---|---|---:|---:|
{chr(10).join(fixtures)}

Đây là một lượt đo trên máy hiện tại. Không suy ra tốc độ GPU/M4 hay throughput production. Baseline cũ chạy xen kẽ và có phạm vi timing khác nên không dùng để tính speedup. Số đầy đủ, command và thời điểm UTC ở [timing.json](timing.json); từng trang có `status.json`, từng run có `initialization.json`/`execution.json`.

## Giới hạn còn lại và hướng tiếp theo

Ưu tiên hiện tại vẫn là trích xuất đủ và đúng thành phần. Refinement là lớp thu hồi bằng chứng phù hợp để tiếp tục thử nghiệm; chưa đủ cơ sở chọn engine cuối cùng hoặc cam kết accuracy. Luật hiện giả định trang thẳng, bảng có đường kẻ, diagram có các hình khép kín nối nhau. Chưa kiểm tra bảng không đường kẻ, trang nghiêng mạnh, sơ đồ tự do hay SOP thực. Các ngưỡng đã được phát triển trên chính 4 thiết kế này; cần một tập mới, không dùng để chỉnh luật, trước khi kết luận tổng quát hóa.

OCR tiếng Việt trên scan vẫn là hạn chế rõ rệt. Cần benchmark OCR/crop OCR riêng trên lỗi còn lại và đưa vùng chưa chắc chắn vào review; việc giữ token điểm thấp giúp truy vết nhưng không tự sửa ký tự sai. Text xoay còn có thể chỉ nằm trong token evidence thay vì paragraph block. `parent_ref` là ownership dùng ở vòng thử này; chưa triển khai schema xuất sản phẩm.

Kiểm tra tự động: 14 unit tests cho matching/evaluation, ownership, grid/merged cells và connected-shape grouping; package builder kiểm tra đủ 32 trang thành công, fingerprint đồng nhất, source snapshot/hash, local HTML links và ZIP CRC. Crop diagram/ảnh được kiểm tra trực quan. Các kiểm tra kỹ thuật này không thay thế đánh giá trên tài liệu thực.

Lệnh tái chạy và mô tả code: [playground README](../../../../playground/README.md). Gói ZIP giữ kết quả refined và số đối chiếu baseline; toàn bộ raw artifacts baseline vẫn nằm riêng trong repo/gói baseline cũ.
"""
    (directory / "REPORT.md").write_text(report, encoding="utf-8")
    print(directory / "REPORT.md")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-name", default="refined_v1")
    build(ap.parse_args().run_name)
