"""Phase 1, bước 2: chuẩn hóa quy trình.

MỤC ĐÍCH CỦA FILE
-----------------
Script này là bước tiền xử lý dữ liệu của Phase 1. Nó đọc từng file BPMN thô (xuất từ các
công cụ vẽ quy trình như Bizagi, Camunda...), rồi:
  1. Làm sạch BPMN: bỏ phần đồ họa (tọa độ, kích thước, màu...), bỏ phần tử ngoài luồng
     điều khiển (dataObject, textAnnotation...), bỏ thuộc tính riêng của công cụ xuất,
     chuẩn hóa khoảng trắng trong tên. Bài báo đưa vào LLM BPMN *không có đồ họa*.
  2. Phân tích BPMN thành đồ thị quy trình (node + sequence flow) và kiểm tra tính hợp lệ
     (mọi flow trỏ tới node có thật, có start/end event, mọi node đi được từ start và tới
     được end, không trùng tên...).
  3. Nếu có cả bản gốc (data/raw/original) và bản đối chiếu (data/raw), so sánh để đảm bảo
     việc làm sạch không làm thay đổi cấu trúc quy trình.
  4. Ghi ra các file kết quả dùng cho các phase sau (chunking, Pure LLM, sinh ground truth,
     đánh giá) và một báo cáo tổng hợp phase1_report.json.

Đầu vào / đầu ra:
data/raw/original/<pid>.bpmn (nếu chưa có thì dùng data/raw/<pid>.bpmn)  ->  data/processed/<pid>/
    <pid>.bpmn             BPMN đã bỏ đồ họa (input cho chunking và Pure LLM)
    graph.json             node + sequence flow, nguồn sự thật cho các phase sau
    dfg_activities.txt     danh sách activity, đúng format của bài báo
    dfg_flows_paper.txt    giống file của bài: bỏ flow chạm gateway không tên
    dfg_flows_full.txt     gộp gateway không tên, không mất chuyển tiếp giữa các activity
    dfg_flows_gateway.txt  đủ mọi flow; gateway có tên gọi bằng tên, không tên gọi bằng id
data/processed/phase1_report.json

Khi có cả hai file, graph của bản gốc phải trùng với data/raw/<pid>.bpmn.

Chạy:  python scripts/prepare_processes.py   (exit code 1 nếu có quy trình không hợp lệ)
"""
import json                          # ghi báo cáo phase1_report.json
import sys                           # cấu hình stdout và trả exit code cho shell/CI
import xml.etree.ElementTree as ET   # chỉ dùng để bắt lỗi ET.ParseError khi XML hỏng

# PROJECT_ROOT: thư mục gốc của dự án, để đường dẫn không phụ thuộc nơi chạy script
from bpllm.config import PROJECT_ROOT
# Các hàm xử lý BPMN của package bpllm.parsing:
#   BpmnFormatError  - lỗi khi file không phải BPMN 2.0 hợp lệ
#   activities_text  - sinh nội dung dfg_activities.txt từ graph
#   clean_bpmn       - làm sạch XML BPMN (bỏ đồ họa, phần tử ngoài luồng, chuẩn hóa tên)
#   flows_text       - sinh nội dung dfg_flows_<mode>.txt từ graph
#   parse_bpmn       - đọc file BPMN từ đường dẫn thành ProcessGraph
#   parse_bpmn_text  - đọc chuỗi XML BPMN thành ProcessGraph
from bpllm.parsing import (BpmnFormatError, activities_text, clean_bpmn, flows_text, parse_bpmn,
                           parse_bpmn_text)

# Thư mục chứa BPMN thô (bản đối chiếu / bản dự phòng khi chưa có bản gốc)
RAW_DIR = PROJECT_ROOT / "data" / "raw"
# Thư mục chứa BPMN gốc xuất từ công cụ vẽ (được ưu tiên dùng làm nguồn)
ORIGINAL_DIR = RAW_DIR / "original"
# Thư mục ghi kết quả đã xử lý, mỗi quy trình một thư mục con data/processed/<pid>/
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"


def process_one(pid, src, baseline):
  """Xử lý một quy trình: làm sạch, parse, kiểm tra và (nếu có) đối chiếu với baseline.

  pid:      mã quy trình (tên file viết thường, không đuôi .bpmn)
  src:      file BPMN dùng làm nguồn (ưu tiên bản trong original/)
  baseline: file data/raw/<pid>.bpmn để đối chiếu, hoặc None nếu không có

  Trả về (report, kết quả cần ghi). Chưa ghi gì để file lỗi không để lại kết quả dở.
  Kết quả cần ghi là (graph, cleaned) nếu hợp lệ, None nếu có lỗi.
  """
  # Khởi tạo báo cáo cho quy trình này với các trường mặc định rỗng
  report = {"source": src.name,                           # tên file nguồn đã dùng
            "from_original": src.parent == ORIGINAL_DIR,  # nguồn có phải bản gốc không
            "counts": {},       # số lượng activity, gateway, event, flow
            "errors": [],       # lỗi làm quy trình không hợp lệ
            "warnings": [],     # cảnh báo không chặn nhưng làm yếu dữ liệu
            "removed": {},      # số phần tử bị cleaner bỏ, theo từng loại tag
            "renamed": []}      # các tên bị đổi khi chuẩn hóa khoảng trắng
  try:
    # Đọc XML nguồn và làm sạch (bỏ đồ họa, phần tử ngoài luồng, thuộc tính công cụ...)
    result = clean_bpmn(src.read_text(encoding="utf-8"))
    # cleaned: XML đã sạch; removed: Counter đếm phần tử đã bỏ theo loại
    cleaned, removed = result.text, result.removed
    # Parse XML đã sạch thành đồ thị quy trình (ProcessGraph); source_file ghi theo tên đầu ra
    graph = parse_bpmn_text(cleaned, pid, f"{pid}.bpmn")
    # Kiểm tra cấu trúc đồ thị; danh sách rỗng nghĩa là hợp lệ
    errors = graph.validate()
    # Nếu nguồn là bản gốc và có bản đối chiếu khác file, so sánh node/flow giữa hai bản
    # để chắc chắn việc làm sạch không làm thay đổi quy trình
    if baseline is not None and baseline != src:
      errors += graph.diff(parse_bpmn(baseline, pid))
  except (ET.ParseError, BpmnFormatError) as ex:
    # XML hỏng hoặc không phải BPMN 2.0: ghi lỗi và dừng, không có gì để ghi ra đĩa
    report["errors"] = [str(ex)]
    return report, None

  # Lấy tất cả gateway để thống kê gateway có tên / không tên
  gateways = graph.by_kind("gateway")
  # Điền đầy đủ thông tin vào báo cáo
  report.update(
      counts=graph.counts(),                   # số lượng từng loại phần tử
      errors=errors,                           # lỗi validate + khác biệt với bản đối chiếu
      warnings=graph.warnings(),               # ví dụ: nhánh gateway thiếu nhãn điều kiện
      removed=dict(sorted(removed.items())),   # sắp xếp theo tên tag để báo cáo ổn định
      renamed=result.renamed,   # R10: tên gốc trước khi chuẩn hóa khoảng trắng
      # Gateway có tên được tham chiếu bằng tên, không tên được tham chiếu bằng id
      gateways={"named": sum(n.lookup == "name" for n in gateways),
                "unnamed": sum(n.lookup == "id" for n in gateways)},
  )
  # Chỉ trả kết quả để ghi khi không có lỗi; có lỗi thì trả None để không ghi file dở
  return report, None if errors else (graph, cleaned)


def _write(path, text):
  """Ghi chuỗi ra file UTF-8 với ký tự xuống dòng thống nhất."""
  # R9: newline="\n" để output giống hệt nhau trên Windows và Colab/Kaggle
  path.write_text(text, encoding="utf-8", newline="\n")


def write_outputs(pid, graph, cleaned):
  """Ghi toàn bộ file kết quả của một quy trình hợp lệ vào data/processed/<pid>/."""
  out = PROCESSED_DIR / pid
  # Tạo thư mục đầu ra (kể cả thư mục cha) nếu chưa có
  out.mkdir(parents=True, exist_ok=True)
  # BPMN đã làm sạch: input cho chunking và cho cách tiếp cận Pure LLM
  _write(out / f"{pid}.bpmn", cleaned)
  # Đồ thị dạng JSON: nguồn sự thật cho các phase sau (ground truth, đánh giá)
  graph.save(out / "graph.json")
  # Danh sách activity theo đúng format của bài báo
  _write(out / "dfg_activities.txt", activities_text(graph))
  # Ba biến thể danh sách flow (DFG):
  #   paper   - giống bài báo: bỏ flow chạm gateway không tên
  #   full    - gộp gateway không tên để không mất chuyển tiếp giữa các activity
  #   gateway - giữ đủ mọi flow, gateway gọi bằng tên hoặc id
  for mode in ("paper", "full", "gateway"):
    _write(out / f"dfg_flows_{mode}.txt", flows_text(graph, mode))


def main() -> int:
  """Xử lý mọi quy trình, in kết quả ra màn hình, ghi báo cáo. Trả 0 nếu tất cả hợp lệ, 1 nếu không."""
  # Liệt kê file .bpmn ở data/raw, ánh xạ pid (tên file viết thường) -> đường dẫn
  raws = {p.stem.lower(): p for p in RAW_DIR.glob("*.bpmn")}
  # Liệt kê file .bpmn ở data/raw/original theo cùng cách
  originals = {p.stem.lower(): p for p in ORIGINAL_DIR.glob("*.bpmn")}
  # Hợp hai tập pid và sắp xếp để thứ tự xử lý/báo cáo luôn cố định
  pids = sorted(set(raws) | set(originals))
  # Không có file nào thì báo và thoát với mã lỗi
  if not pids:
    print(f"Không tìm thấy file .bpmn trong {RAW_DIR}")
    return 1

  # report: pid -> báo cáo; all_ok: còn True khi chưa gặp quy trình lỗi nào
  report, all_ok = {}, True
  for pid in pids:
    # Ưu tiên bản gốc trong original/, nếu không có thì dùng bản trong data/raw
    src = originals.get(pid) or raws[pid]
    # Xử lý quy trình; bản trong data/raw (nếu có) được truyền vào làm baseline đối chiếu
    report[pid], result = process_one(pid, src, raws.get(pid))
    # Chỉ ghi file đầu ra khi quy trình hợp lệ
    if result is not None:
      write_outputs(pid, *result)   # *result tách thành (graph, cleaned)
    errors, warnings = report[pid]["errors"], report[pid]["warnings"]
    # Chỉ cần một quy trình lỗi là toàn bộ lần chạy bị coi là thất bại
    all_ok = all_ok and not errors
    # In trạng thái OK/LỖI kèm số lượng phần tử của quy trình
    print(f"[{'OK ' if not errors else 'LỖI'}] {pid}: {report[pid]['counts']}")
    # In chi tiết từng lỗi (dấu -) và từng cảnh báo (dấu !)
    for err in errors:
      print(f"      - {err}")
    for warning in warnings:
      print(f"      ! {warning}")

  # Đảm bảo thư mục processed tồn tại (trường hợp mọi quy trình đều lỗi nên chưa được tạo)
  PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
  # Ghi báo cáo tổng hợp; ensure_ascii=False để giữ nguyên tiếng Việt/ký tự Unicode
  _write(PROCESSED_DIR / "phase1_report.json", json.dumps(report, indent=2, ensure_ascii=False) + "\n")
  print(f"Đã ghi kết quả vào {PROCESSED_DIR}")
  # Exit code 0 = tất cả hợp lệ, 1 = có quy trình lỗi (để CI/script khác phát hiện được)
  return 0 if all_ok else 1


if __name__ == "__main__":
  # Ép stdout dùng UTF-8 để in tiếng Việt không lỗi trên console Windows (cp1252/cp1258)
  sys.stdout.reconfigure(encoding="utf-8", errors="replace")
  # Chạy main() và trả exit code của nó cho hệ điều hành
  sys.exit(main())
