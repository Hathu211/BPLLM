"""Natural-text (DFG) representation of a ProcessGraph, in the paper's format (Fig. 5).

Sinh được cho mọi quy trình, không chỉ Food Delivery (quy trình duy nhất bài báo kèm file text).

Three variants of the flows text:
 mode="paper"  : reproduces the paper's files. Unnamed gateways are dropped together with
         every flow touching them (this is why the original food_delivery flow file
         has only 15 transitions for 27 sequence flows).
 mode="full"   : unnamed gateways are collapsed (predecessors linked to successors),
         so no transition between activities is lost and parallel splits are stated.
 mode="gateway": every sequence flow exactly as in the graph. A named gateway is called by
         its name, an unnamed one by its id, and each gateway's type is listed.
         This is the only variant that can answer the paper's gateway questions.
"full" and "gateway" are own extensions, not in the paper.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple

from .bpmn_parser import ProcessGraph

Edge = Tuple[str, str, str]   # (source_id, target_id, condition)
MODES = ("paper", "full", "gateway")

# R6: bảng tên thay cho type.replace("Gateway", " gateway") (từng ra "eventBased gateway")
GATEWAY_LABELS = {
  "exclusiveGateway": "exclusive gateway",
  "parallelGateway": "parallel gateway",
  "inclusiveGateway": "inclusive gateway",
  "eventBasedGateway": "event-based gateway",
  "complexGateway": "complex gateway",
}
# R5: phần đuôi câu ở chế độ full
PARALLEL_SPLIT = "(parallel branch)"
PARALLEL_JOIN = "(after all parallel branches complete)"


@dataclass(frozen=True)
class EdgeInfo:
  split: bool = False   # cạnh đi qua parallelGateway không tên có >= 2 nhánh ra
  join: bool = False    # cạnh đi qua parallelGateway không tên có >= 2 nhánh vào (phải chờ đủ nhánh)


def dfg_nodes(g: ProcessGraph) -> List[str]:
  """Activities + start/end events (the paper's 'activities' file lists both)."""
  return [n.id for n in g.nodes.values()
      if n.kind == "activity" or n.type in ("startEvent", "endEvent")]


def _collapsed_edges(g: ProcessGraph) -> Dict[Edge, EdgeInfo]:
  """Edges with unnamed gateways collapsed -> whether they pass a parallel split / join."""
  unnamed = {n.id for n in g.nodes.values() if n.kind == "gateway" and not n.name}
  edges: Dict[Edge, EdgeInfo] = {}
  for f in g.flows:
    if f.source in unnamed:
      continue                          # reached through expansion below
    # expand through chains of unnamed gateways
    stack, seen = [(f.target, f.name, False, False)], set()
    while stack:
      tgt, cond, split, join = stack.pop()
      if tgt in unnamed:
        if tgt in seen:
          continue
        seen.add(tgt)
        outgoing = [f2 for f2 in g.flows if f2.source == tgt]
        is_and = g.nodes[tgt].type == "parallelGateway"
        splits = is_and and len(outgoing) > 1
        joins = is_and and len(g.predecessors(tgt)) > 1
        stack.extend((f2.target, cond or f2.name, split or splits, join or joins) for f2 in outgoing)
      else:
        edge = (f.source, tgt, cond)
        old = edges.get(edge, EdgeInfo())
        edges[edge] = EdgeInfo(old.split or split, old.join or join)
  return edges


def dfg_edges(g: ProcessGraph, mode: str = "paper") -> List[Edge]:
  if mode not in MODES:
    raise ValueError(f"mode must be one of {MODES}")
  if mode == "gateway":
    return [(f.source, f.target, f.name) for f in g.flows]
  unnamed = {n.id for n in g.nodes.values() if n.kind == "gateway" and not n.name}
  if mode == "paper":
    return [(f.source, f.target, f.name) for f in g.flows
        if f.source not in unnamed and f.target not in unnamed]
  order = {n: i for i, n in enumerate(g.nodes)}
  return sorted(_collapsed_edges(g), key=lambda e: (order[e[0]], order[e[1]], e[2]))


def activities_text(g: ProcessGraph) -> str:
  lines = sorted(g.nodes[i].display_name for i in dfg_nodes(g))
  return f"The {g.process_name} process defines the following activities, one per line:\n" + "\n".join(lines) + "\n"


def _gateway_line(node) -> str:
  label = GATEWAY_LABELS.get(node.type, node.type)
  article = "an" if label[0] in "aeiou" else "a"
  if node.lookup == "id":
    return f'Gateway "{node.id}" is an unnamed {label}, referred to by its id.'
  return f'Gateway "{node.name}" is {article} {label} with id "{node.id}".'


def _is_default_branch(g: ProcessGraph, src: str, cond: str) -> bool:
  """Nhánh không nhãn của gateway XOR/OR mà các nhánh khác có nhãn (ví dụ E-commerce
  'Is this a new customer?': nhánh 'Yes' có nhãn, nhánh tới 'Recover client history' không).
  Viết nó như nhánh còn lại để LLM không hiểu là luôn chạy. Không tự đặt nhãn 'No'."""
  node = g.nodes[src]
  if cond or node.type not in ("exclusiveGateway", "inclusiveGateway"):
    return False
  return any(f.name for f in g.flows if f.source == src)


def flows_text(g: ProcessGraph, mode: str = "paper") -> str:
  out = [f"The {g.process_name} process defines the following transitions:"]
  info = _collapsed_edges(g) if mode == "full" else {}
  if mode == "gateway":
    out.extend(_gateway_line(n) for n in g.by_kind("gateway"))
  for s in g.by_type("startEvent"):
    out.append(f'The process starts from "{s.display_name}".')
  for e in g.by_type("endEvent"):
    out.append(f'The process ends with "{e.display_name}".')
  for src, tgt, cond in dfg_edges(g, mode):
    a, b = g.nodes[src].display_name, g.nodes[tgt].display_name
    # R5: nói rõ X là nhánh song song, và X phải chờ đủ các nhánh (AND-join)
    e = info.get((src, tgt, cond), EdgeInfo())
    tail = "".join(f" {t}" for t, on in ((PARALLEL_SPLIT, e.split), (PARALLEL_JOIN, e.join)) if on)
    if cond:
      out.append(f'From "{a}", the process can continue with "{b}"{tail} if the branch is "{cond}".')
    elif _is_default_branch(g, src, cond):
      out.append(f'From "{a}", the process can continue with "{b}"{tail} otherwise.')
    else:
      out.append(f'From "{a}", the process continues with "{b}"{tail}.')
  return "\n".join(out) + "\n"


def parse_flows_text(text: str) -> Set[Tuple[str, str]]:
  """Read a DFG flows file back into {(source_name, target_name)} (lower-case)."""
  pairs = set()
  for line in text.splitlines():
    # "(?:in parallel )?" vẫn giữ để đọc được file sinh bởi phiên bản cũ
    m = re.match(r'From "(.+?)", the process (?:can )?continue[s]? (?:in parallel )?with "(.+?)"', line.strip())
    if m:
      pairs.add((m.group(1).lower(), m.group(2).lower()))
  return pairs
