"""Bỏ phần không thuộc luồng điều khiển của file BPMN, chỉ giữ mô hình cho LLM và chunking.

Bài báo đưa BPMN *không có thông tin đồ họa* vào LLM. File gốc (giữ để vẽ sơ đồ) còn chứa
nhiều thứ khác tùy công cụ xuất: Bizagi thêm extensionElements, dataObject, ioSpecification.
Những phần này không đổi quy trình mà làm nhiễu chunk, nên bị bỏ cùng phần đồ họa.

Cụ thể, cleaner bỏ 5 nhóm:
  1. Đồ họa chuẩn (bpmndi, dc, di): vị trí, kích thước, đường nối, font.
  2. Định dạng riêng của công cụ (ví dụ bizagi:BizagiProperty: màu sắc).
  3. Phần tử mô hình ngoài luồng điều khiển: dataObject, ioSpecification, association,
     textAnnotation, documentation rỗng, laneSet rỗng.
  4. boundaryEvent không nằm trong flow nào (Bizagi xuất ra kiểu này).
  5. Thuộc tính của công cụ xuất: exporter, gatewayDirection, isExecutable...
Tên phần tử được chuẩn hóa khoảng trắng; tên gốc được trả về trong CleanResult.renamed.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple, Union

from .bpmn_parser import BpmnFormatError

BPMN_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"

# Không thuộc luồng điều khiển. dataStoreReference được giữ vì task ghi vào CSDL là thông tin mô hình.
NON_FLOW_TAGS = {
  "extensionElements", "textAnnotation", "association", "group", "category",
  "dataObject", "dataObjectReference", "dataState", "property",
  "ioSpecification", "dataInput", "dataOutput", "inputSet", "outputSet",
}
DATA_ASSOCIATIONS = {"dataInputAssociation", "dataOutputAssociation"}
# Thuộc tính của công cụ xuất. gatewayDirection cũng bỏ vì suy ra được từ flow, và Bizagi
# ghi sai: 'Expense report is OK?' có 2 nhánh ra nhưng được ghi là Converging.
# R7: KHÔNG bỏ targetNamespace, vì XSD của BPMN 2.0 bắt buộc <definitions> phải có thuộc tính này.
TOOL_ATTRIBUTES = {
  "exporter", "exporterVersion", "expressionLanguage", "typeLanguage",
  "isExecutable", "gatewayDirection",
}


@dataclass
class CleanResult:
  text: str                                            # XML đã làm sạch
  removed: Counter = field(default_factory=Counter)    # số phần tử bị bỏ theo từng loại
  # R10: tên bị đổi khi chuẩn hóa khoảng trắng, để còn truy vết được tên gốc
  renamed: List[Dict[str, str]] = field(default_factory=list)


def _local(tag: str) -> str:
  return tag.split("}")[-1]


def _is_foreign(tag: str) -> bool:
  """Đồ họa (bpmndi, dc, di) và phần mở rộng của công cụ đều nằm ngoài namespace BPMN."""
  return not tag.startswith("{" + BPMN_NS + "}")


def _store_ids(root: ET.Element) -> set:
  return {e.get("id") for e in root.iter() if _local(e.tag) == "dataStoreReference"}


def _touches_store(el: ET.Element, stores: set) -> bool:
  return any(_local(c.tag) in ("sourceRef", "targetRef") and (c.text or "").strip() in stores
             for c in el)


def _flow_node_ids(root: ET.Element) -> set:
  ids = set()
  for el in root.iter():
    if _local(el.tag) == "sequenceFlow":
      ids.update((el.get("sourceRef"), el.get("targetRef")))
  return ids


def _should_remove(el: ET.Element, stores: set, connected: set) -> bool:
  tag = _local(el.tag)
  if _is_foreign(el.tag) or tag in NON_FLOW_TAGS:
    return True
  if tag in DATA_ASSOCIATIONS:
    return not _touches_store(el, stores)
  if tag == "documentation":
    return not (el.text or "").strip()
  # Sự kiện biên không có flow (compensation của Bizagi) không tham gia luồng điều khiển.
  if tag == "boundaryEvent":
    return el.get("id") not in connected
  return False


def _name_stores_from_annotations(root: ET.Element, stores: set) -> None:
  """Food Delivery đặt tên CSDL trong textAnnotation; giữ tên đó trước khi bỏ annotation."""
  notes = {}
  for el in root.iter():
    if _local(el.tag) == "textAnnotation":
      notes[el.get("id")] = " ".join(t.strip() for t in el.itertext() if t.strip())
  for el in root.iter():
    if _local(el.tag) != "association":
      continue
    ends = (el.get("sourceRef"), el.get("targetRef"))
    for store_id, note_id in (ends, ends[::-1]):
      if store_id in stores and note_id in notes:
        for store in root.iter():
          if store.get("id") == store_id and not store.get("name"):
            store.set("name", notes[note_id])


def clean_bpmn(xml_text: str) -> CleanResult:
  """Làm sạch BPMN, trả về XML sạch kèm những gì đã bỏ và đã đổi tên."""
  ET.register_namespace("", BPMN_NS)          # giữ <task>, không thành <ns0:task>
  root = ET.fromstring(xml_text)
  # R2: không có namespace BPMN thì mọi phần tử đều bị coi là ngoại lai và bị xóa sạch,
  # rồi validate() chỉ báo "no startEvent". Báo đúng lỗi ngay từ đầu.
  if root.tag != "{" + BPMN_NS + "}definitions":
    raise BpmnFormatError(
      f"không phải BPMN 2.0: phần tử gốc là <{root.tag}>, "
      f"cần <definitions xmlns=\"{BPMN_NS}\">")
  stores, connected = _store_ids(root), _flow_node_ids(root)
  _name_stores_from_annotations(root, stores)
  removed: Counter = Counter()
  renamed: List[Dict[str, str]] = []

  for parent in list(root.iter()):
    for child in list(parent):
      if _should_remove(child, stores, connected):
        removed[_local(child.tag)] += 1
        parent.remove(child)

  # laneSet trống chỉ còn là vỏ sau khi bỏ phần tử bên trong
  for parent in list(root.iter()):
    for child in list(parent):
      if _local(child.tag) == "laneSet" and len(child) == 0:
        removed["laneSet"] += 1
        parent.remove(child)

  for el in root.iter():
    for attr in list(el.attrib):
      if attr.startswith("{") or attr in TOOL_ATTRIBUTES:
        del el.attrib[attr]
    if "name" in el.attrib:
      # 'check credit\xa0 card' -> 'check credit card'; name="" nghĩa là không có tên
      original = el.get("name")
      name = " ".join(original.split())
      if name and name != original:
        renamed.append({"id": el.get("id", ""), "tag": _local(el.tag), "from": original, "to": name})
      if name:
        el.set("name", name)
      else:
        del el.attrib["name"]

  ET.indent(root, space="  ")                 # Python >= 3.9
  text = '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode") + "\n"
  return CleanResult(text, removed, renamed)


def strip_graphics_report(xml_text: str) -> Tuple[str, Counter]:
  """Giữ cho code cũ chạy được: (XML đã làm sạch, số phần tử bị bỏ theo từng loại)."""
  result = clean_bpmn(xml_text)
  return result.text, result.removed


def strip_graphics(xml_text: str) -> str:
  return strip_graphics_report(xml_text)[0]


def strip_graphics_file(src: Union[str, Path], dst: Union[str, Path]) -> Counter:
  """Làm sạch src và ghi ra dst. Không đọc được thì không tạo file đích."""
  text, removed = strip_graphics_report(Path(src).read_text(encoding="utf-8"))
  Path(dst).parent.mkdir(parents=True, exist_ok=True)
  Path(dst).write_text(text, encoding="utf-8", newline="\n")   # R9
  return removed
