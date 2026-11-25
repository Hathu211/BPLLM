"""BPMN-specific chunking theo bài báo BPLLM (Fig. 3).

Mỗi chunk là nguyên văn XML của một phần tử BPMN (task, gateway, event), giữ cả
các tag con như <incoming>/<outgoing>. Phần đồ họa đã được bỏ ở Phase 1
(data/processed/<process>/<process>.bpmn).

<sequenceFlow> KHÔNG thành chunk riêng: flow A -> B đọc được nhờ id Flow_x nằm
trong <outgoing> của A và <incoming> của B. Chunk sequenceFlow chỉ chứa id nên
chiếm chỗ trong top-10 mà không giúp gì.

Chế độ enrich (cải tiến, không có trong bài báo): vẫn là XML của node, nhưng mỗi
<incoming>/<outgoing> được gắn tên node ở đầu bên kia và nhãn điều kiện lấy từ
<sequenceFlow>, ví dụ <outgoing target="register the order" condition="yes">Flow_1</outgoing>.

Chạy: python -m bpllm.chunking.chunking_processor            (bài báo)
      python -m bpllm.chunking.chunking_processor --enrich   (cải tiến)
"""
from __future__ import annotations

import copy
import json
import re
import textwrap
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from bpllm.config import PROJECT_ROOT
from bpllm.parsing import PROCESS_NAMES

BPMN_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"

TASK_TAGS = {
    "task", "userTask", "serviceTask", "sendTask", "receiveTask",
    "scriptTask", "businessRuleTask", "manualTask", "callActivity", "subProcess",
}
GATEWAY_TAGS = {
    "exclusiveGateway", "inclusiveGateway", "parallelGateway",
    "eventBasedGateway", "complexGateway",
}
EVENT_TAGS = {
    "startEvent", "endEvent", "intermediateCatchEvent",
    "intermediateThrowEvent", "boundaryEvent",
}
NODE_TAGS = TASK_TAGS | GATEWAY_TAGS | EVENT_TAGS

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
CHUNKS_FILE = PROCESSED_DIR / "bpmn_chunks.jsonl"
ENRICHED_CHUNKS_FILE = PROCESSED_DIR / "bpmn_chunks_enriched.jsonl"

# Xuất XML với namespace mặc định để không sinh tiền tố "ns0:"
ET.register_namespace("", BPMN_NS)
_XMLNS_ATTR = re.compile(r'\s+xmlns(:\w+)?="[^"]*"')


def _local(tag: str) -> str:
  return tag.split("}")[-1]


def _node_kind(tag: str) -> str:
  if tag in TASK_TAGS:
    return "activity"
  if tag in GATEWAY_TAGS:
    return "gateway"
  return "event"


def element_xml(el: ET.Element) -> str:
  """Nguyên văn XML của một phần tử: bỏ khai báo xmlns, chuẩn hóa thụt lề."""
  tail, el.tail = el.tail, None
  try:
    text = ET.tostring(el, encoding="unicode")
  finally:
    el.tail = tail
  text = _XMLNS_ATTR.sub("", text, count=1)
  first, _, rest = text.partition("\n")
  if not rest:
    return first.strip()
  # Các dòng con giữ thụt lề tương đối, thẻ đóng về sát lề
  return first.strip() + "\n" + textwrap.dedent(rest).strip("\n")


def _enrich(el: ET.Element, nodes: Dict[str, ET.Element],
            flows: Dict[str, ET.Element]) -> ET.Element:
  """Bản sao của node, mỗi <incoming>/<outgoing> được gắn thông tin của <sequenceFlow>.

  <outgoing target="tên node đích">   (id nếu node đích không có tên)
  <incoming source="tên node nguồn">  (id nếu node nguồn không có tên)
  condition="..." nếu flow có nhãn nhánh (yes/no...).
  Cố ý chỉ thêm 1-2 thuộc tính: bản đầy đủ (thêm *Ref, *Type) làm chunk dài quá
  256 token của MiniLM và làm id gateway xuất hiện ở chunk hàng xóm.
  """
  el = copy.deepcopy(el)
  for child in el:
    kind = _local(child.tag)
    flow = flows.get((child.text or "").strip())
    if kind not in ("incoming", "outgoing") or flow is None:
      continue
    side = "target" if kind == "outgoing" else "source"
    other_id = flow.get(f"{side}Ref") or ""
    other = nodes.get(other_id)
    name = (other.get("name") or "").strip() if other is not None else ""
    child.set(side, name or other_id)
    if (flow.get("name") or "").strip():
      child.set("condition", flow.get("name").strip())
  return el


class BPMNSpecificChunker:
  """Cắt một file BPMN thành các chunk XML, mỗi chunk một node.

  enrich=False: đúng Fig. 3 bài báo (baseline).
  enrich=True : gộp thông tin <sequenceFlow> vào <incoming>/<outgoing> của node (cải tiến).
  """

  def __init__(self, enrich: bool = False):
    self.enrich = enrich

  def chunk(self, xml_content: str, process_id: str,
            process_name: Optional[str] = None) -> List[Dict]:
    """Trả về list {'text', 'metadata'}; 'text' là đoạn XML đem đi embed."""
    root = ET.fromstring(xml_content)
    process_name = process_name or PROCESS_NAMES.get(
        process_id, process_id.replace("_", " ").title())
    nodes = {el.get("id"): el for el in root.iter() if _local(el.tag) in NODE_TAGS}
    flows = {el.get("id"): el for el in root.iter() if _local(el.tag) == "sequenceFlow"}

    chunks: List[Dict] = []
    for el in root.iter():
      tag = _local(el.tag)
      if tag not in NODE_TAGS:
        continue
      source = _enrich(el, nodes, flows) if self.enrich else el
      chunks.append({
          "text": element_xml(source),
          "metadata": {
              "process_id": process_id,
              "process_name": process_name,
              "node_id": el.get("id"),
              "node_type": tag,
              "node_kind": _node_kind(tag),
              "node_name": (el.get("name") or "").strip(),
              "chunk_index": len(chunks),
              "chunking": "bpmn_enriched" if self.enrich else "bpmn_specific",
          },
      })
    return chunks


def process_dirs(processed_dir: Path = PROCESSED_DIR) -> List[Path]:
  """Các thư mục data/processed/<process>/ có file <process>.bpmn."""
  if not processed_dir.is_dir():
    return []
  return sorted(d for d in processed_dir.iterdir()
                if d.is_dir() and (d / f"{d.name}.bpmn").is_file())


def chunk_process_dir(process_dir: Path,
                      chunker: Optional[BPMNSpecificChunker] = None) -> List[Dict]:
  """Chunk file BPMN đã làm sạch của một quy trình."""
  chunker = chunker or BPMNSpecificChunker()
  process_id = process_dir.name
  process_name = None
  graph_file = process_dir / "graph.json"
  if graph_file.is_file():
    process_name = json.loads(graph_file.read_text(encoding="utf-8")).get("process_name")
  xml = (process_dir / f"{process_id}.bpmn").read_text(encoding="utf-8")
  return chunker.chunk(xml, process_id, process_name)


def chunk_all(processed_dir: Path = PROCESSED_DIR,
              process_ids: Optional[Iterable[str]] = None,
              enrich: bool = False) -> List[Dict]:
  """Chunk mọi quy trình, hoặc chỉ các process_ids được chọn."""
  wanted = set(process_ids) if process_ids else None
  chunker = BPMNSpecificChunker(enrich=enrich)
  chunks: List[Dict] = []
  for d in process_dirs(processed_dir):
    if wanted is None or d.name in wanted:
      chunks.extend(chunk_process_dir(d, chunker))
  return chunks


def write_jsonl(chunks: List[Dict], path: Path = CHUNKS_FILE) -> Path:
  path.parent.mkdir(parents=True, exist_ok=True)
  with path.open("w", encoding="utf-8") as f:
    for c in chunks:
      f.write(json.dumps(c, ensure_ascii=False) + "\n")
  return path


def main() -> None:
  import argparse
  parser = argparse.ArgumentParser(description="BPMN-specific chunking")
  parser.add_argument("--enrich", action="store_true",
                      help="gộp thông tin sequenceFlow vào <incoming>/<outgoing>")
  args = parser.parse_args()
  chunks = chunk_all(enrich=args.enrich)
  if not chunks:
    print(f"Không tìm thấy quy trình nào trong {PROCESSED_DIR}. Chạy scripts/prepare_processes.py trước.")
    return
  counts: Dict[str, int] = {}
  for c in chunks:
    pid = c["metadata"]["process_id"]
    counts[pid] = counts.get(pid, 0) + 1
  for pid, n in counts.items():
    print(f"{pid}: {n} chunk")
  out = write_jsonl(chunks, ENRICHED_CHUNKS_FILE if args.enrich else CHUNKS_FILE)
  print(f"Đã ghi {len(chunks)} chunk vào {out}")
  print("\nVí dụ chunk đầu tiên:\n" + chunks[0]["text"])


if __name__ == "__main__":
  main()