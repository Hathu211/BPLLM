"""Parse a BPMN 2.0 XML file into a normalised ProcessGraph (nodes + sequence flows).

The graph is the single source of truth for every later phase:
ground truth, chunking, question generation and evaluation.
Standard library only.
"""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from collections import deque
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Dict, List, Optional, Union

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

# Tên chuẩn dùng chung cho mọi phase (bộ lọc Streamlit, metadata chunk, câu hỏi).
# Tên participant trong BPMN không dùng được: 'Administration Office' là Reimbursement.
PROCESS_NAMES = {
  "food_delivery": "Food Delivery",
  "ecommerce": "E-commerce",
  "reimbursement": "Reimbursement",
}


class BpmnFormatError(ValueError):
  """The file cannot be turned into a graph without silently losing elements."""


def local(tag: str) -> str:
  """'{http://...}task' -> 'task'."""
  return tag.split("}")[-1]


def normalize_name(raw: Optional[str]) -> str:
  """Collapse whitespace/newlines: 'check credit  card' -> 'check credit card'."""
  return " ".join((raw or "").split())


def kind_of(element_type: str) -> str:
  if element_type in TASK_TAGS:
    return "activity"
  if element_type in GATEWAY_TAGS:
    return "gateway"
  return "event"


@dataclass
class Node:
  id: str
  type: str            # BPMN tag: task, sendTask, exclusiveGateway, startEvent...
  kind: str            # activity | gateway | event
  name: str            # normalised name ('' if unnamed)
  # R10: bỏ raw_name. Cleaner đã chuẩn hóa tên trước khi parse nên raw_name luôn bằng name;
  # tên gốc giờ được ghi trong phase1_report.json (mục "renamed").
  lane: str = ""
  # R1: boundaryEvent gắn vào activity nào (attachedToRef); rỗng với mọi node khác
  attached_to: str = ""

  @property
  def display_name(self) -> str:
    """Name used in questions/chunks; unnamed elements fall back to their id
    (the paper's questions refer to unnamed gateways as e.g. 'Gateway_0z24z44')."""
    return self.name or self.id

  @property
  def lookup(self) -> str:
    """How to refer to this element: 'name' if it has a name, otherwise 'id'."""
    return "name" if self.name else "id"


@dataclass
class Flow:
  id: str
  source: str
  target: str
  name: str = ""       # branch condition, e.g. 'yes' / 'no'


@dataclass
class ProcessGraph:
  process_id: str
  process_name: str
  source_file: str
  nodes: Dict[str, Node] = field(default_factory=dict)
  flows: List[Flow] = field(default_factory=list)
  participant: str = ""   # tên participant gốc trong BPMN

  # ---------- queries ----------
  def by_kind(self, kind: str) -> List[Node]:
    return [n for n in self.nodes.values() if n.kind == kind]

  def by_type(self, type_: str) -> List[Node]:
    return [n for n in self.nodes.values() if n.type == type_]

  def successors(self, node_id: str) -> List[str]:
    return [f.target for f in self.flows if f.source == node_id]

  def predecessors(self, node_id: str) -> List[str]:
    return [f.source for f in self.flows if f.target == node_id]

  def has_flow(self, src_id: str, tgt_id: str) -> bool:
    return any(f.source == src_id and f.target == tgt_id for f in self.flows)

  def find(self, reference: str) -> Optional[Node]:
    """Case/whitespace-insensitive lookup. An id always wins over a name."""
    key = normalize_name(reference).lower()
    if not key:
      return None
    for n in self.nodes.values():
      if n.id.lower() == key:
        return n
    for n in self.nodes.values():
      if n.name.lower() == key:
        return n
    return None

  def find_gateway(self, reference: str) -> Optional[Node]:
    """Find a gateway by id (works for every gateway) or by name (only named ones)."""
    node = self.find(reference)
    return node if node is not None and node.kind == "gateway" else None

  def counts(self) -> Dict[str, int]:
    return {
      "activities": len(self.by_kind("activity")),
      "exclusive_gateways": len(self.by_type("exclusiveGateway")),
      "parallel_gateways": len(self.by_type("parallelGateway")),
      "start_events": len(self.by_type("startEvent")),
      "end_events": len(self.by_type("endEvent")),
      "sequence_flows": len(self.flows),
    }

  # ---------- validation ----------
  def validate(self) -> List[str]:
    """Return a list of problems (empty list == valid graph)."""
    errors: List[str] = []
    for f in self.flows:
      if f.source not in self.nodes:
        errors.append(f"{f.id}: sourceRef '{f.source}' is not a node")
      if f.target not in self.nodes:
        errors.append(f"{f.id}: targetRef '{f.target}' is not a node")
    starts = [n.id for n in self.by_type("startEvent")]
    ends = {n.id for n in self.by_type("endEvent")}
    if not starts:
      errors.append("no startEvent")
    if not ends:
      errors.append("no endEvent")
    # R1: boundaryEvent không có flow đi vào; nó được kích hoạt từ activity mà nó gắn vào.
    # Vì vậy khi duyệt, coi như có cạnh ngầm activity -> boundaryEvent.
    def forward(nid: str) -> List[str]:
      return self.successors(nid) + [n.id for n in self.nodes.values() if n.attached_to == nid]

    def backward(nid: str) -> List[str]:
      host = self.nodes[nid].attached_to if nid in self.nodes else ""
      return self.predecessors(nid) + ([host] if host in self.nodes else [])

    for n in self.by_type("boundaryEvent"):
      if n.attached_to and n.attached_to not in self.nodes:
        errors.append(f"{n.id}: attachedToRef '{n.attached_to}' is not a node")

    # every node reachable from a start event
    seen = self._bfs(starts, forward)
    for nid in self.nodes:
      if nid not in seen:
        errors.append(f"{nid} ({self.nodes[nid].display_name}) unreachable from start")
    # every node can reach an end event
    can_end = self._bfs(list(ends), backward)
    for nid in self.nodes:
      if nid not in can_end:
        errors.append(f"{nid} ({self.nodes[nid].display_name}) cannot reach an end event")
    # duplicate names (would make name-based questions ambiguous)
    names: Dict[str, str] = {}
    for n in self.nodes.values():
      if n.name:
        k = n.name.lower()
        if k in names:
          errors.append(f"duplicate name '{n.name}' ({names[k]}, {n.id})")
        names[k] = n.id
    return errors

  def warnings(self) -> List[str]:
    """Data problems that do not break the graph but weaken what can be derived from it."""
    result: List[str] = []
    for n in self.by_type("exclusiveGateway"):
      out = [f for f in self.flows if f.source == n.id]
      if len(out) > 1 and not all(f.name for f in out):
        missing = [self.nodes[f.target].display_name for f in out if not f.name]
        result.append(f"gateway '{n.display_name}': nhánh không có nhãn điều kiện tới {missing}")
    return result

  def diff(self, other: "ProcessGraph") -> List[str]:
    """Differences in nodes and flows, ignoring file order and flow ids."""
    def nodes(g):
      return {(n.id, n.type, n.name) for n in g.nodes.values()}

    def flows(g):
      return {(f.source, f.target, f.name) for f in g.flows}

    result: List[str] = []
    for label, mine, theirs in (("node", nodes(self), nodes(other)),
                                ("flow", flows(self), flows(other))):
      result += [f"{label} chỉ có ở bản gốc: {x}" for x in sorted(mine - theirs)]
      result += [f"{label} chỉ có ở bản đối chiếu: {x}" for x in sorted(theirs - mine)]
    return result

  @staticmethod
  def _bfs(roots: List[str], step) -> set:
    seen, q = set(roots), deque(roots)
    while q:
      for nxt in step(q.popleft()):
        if nxt not in seen:
          seen.add(nxt)
          q.append(nxt)
    return seen

  # ---------- (de)serialisation ----------
  def to_dict(self) -> dict:
    return {
      "process_id": self.process_id,
      "process_name": self.process_name,
      "source_file": self.source_file,
      "participant": self.participant,
      "counts": self.counts(),
      "nodes": [asdict(n) for n in self.nodes.values()],
      "flows": [asdict(f) for f in self.flows],
    }

  def save(self, path: Union[str, Path]) -> None:
    # R9: newline="\n" để file giống hệt nhau trên Windows và Colab/Kaggle
    Path(path).write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n",
                          encoding="utf-8", newline="\n")

  @classmethod
  def load(cls, path: Union[str, Path]) -> "ProcessGraph":
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    g = cls(d["process_id"], d["process_name"], d["source_file"],
            participant=d.get("participant", ""))
    # R10: bỏ qua khóa không còn dùng (raw_name trong graph.json cũ) để file cũ vẫn đọc được
    known = {f.name for f in fields(Node)}
    g.nodes = {n["id"]: Node(**{k: v for k, v in n.items() if k in known}) for n in d["nodes"]}
    g.flows = [Flow(**f) for f in d["flows"]]
    return g


def parse_bpmn_text(xml_text: str, process_id: str, source_file: str) -> ProcessGraph:
  """Parse BPMN XML text (with or without bpmndi graphics) into a ProcessGraph."""
  root = ET.fromstring(xml_text)

  participant = next((e for e in root.iter() if local(e.tag) == "participant"), None)
  process_el = next((e for e in root.iter() if local(e.tag) == "process"), None)
  participant_name = normalize_name(
    (participant.get("name") if participant is not None else None)
    or (process_el.get("name") if process_el is not None else None)
  )
  process_name = PROCESS_NAMES.get(process_id) or process_id.replace("_", " ").title()

  lane_of: Dict[str, str] = {}
  for lane in (e for e in root.iter() if local(e.tag) == "lane"):
    lane_name = normalize_name(lane.get("name")) or lane.get("id")
    for ref in lane.iter():
      if local(ref.tag) == "flowNodeRef" and ref.text:
        lane_of[ref.text.strip()] = lane_name

  g = ProcessGraph(process_id, process_name, source_file, participant=participant_name)
  for el in root.iter():
    tag = local(el.tag)
    if tag in NODE_TAGS:
      nid = el.get("id")
      if not nid:
        # sequenceFlow nối bằng id, nên phần tử không có id không thể nằm trong luồng
        raise BpmnFormatError(
          f"{source_file}: <{tag}> tên '{normalize_name(el.get('name'))}' không có id")
      if nid in g.nodes:
        raise BpmnFormatError(f"{source_file}: id '{nid}' bị trùng")
      g.nodes[nid] = Node(
        id=nid, type=tag, kind=kind_of(tag),
        name=normalize_name(el.get("name")),
        lane=lane_of.get(nid, ""), attached_to=el.get("attachedToRef") or "",
      )
    elif tag == "sequenceFlow":
      g.flows.append(Flow(
        id=el.get("id"), source=el.get("sourceRef"), target=el.get("targetRef"),
        name=normalize_name(el.get("name")),
      ))
  return g


def parse_bpmn(path: Union[str, Path], process_id: Optional[str] = None) -> ProcessGraph:
  """Parse one .bpmn file into a ProcessGraph.

  Chỉ dùng cho file ĐÃ làm sạch (data/raw/, data/processed/). Với file gốc từ công cụ
  (data/raw/original/, file người dùng upload) hãy dùng load_process(), vì file gốc có thể
  chứa phần tử không thuộc luồng (ví dụ boundaryEvent mồ côi của Bizagi).
  """
  path = Path(path)
  return parse_bpmn_text(path.read_text(encoding="utf-8"), process_id or path.stem.lower(), path.name)


def load_process(path: Union[str, Path], process_id: Optional[str] = None):
  """Đọc MỌI file BPMN (gốc hoặc đã sạch): làm sạch rồi parse. Dùng hàm này ở Phase 2 và 10.

  Trả về (graph, xml_sạch, kết_quả_làm_sạch). Import ở đây để tránh vòng import.
  """
  from .bpmn_cleaner import clean_bpmn
  path = Path(path)
  pid = process_id or path.stem.lower()
  result = clean_bpmn(path.read_text(encoding="utf-8"))
  return parse_bpmn_text(result.text, pid, f"{pid}.bpmn"), result.text, result
