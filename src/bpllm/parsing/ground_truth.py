"""Sinh ground truth của một quy trình từ ProcessGraph, không viết tay.

Giữ nguyên các khóa mà scripts/build_vector_store.py và scripts/prepare_dataset.py đang đọc:
`gateways` vẫn là danh sách chuỗi, `sequence_flows` vẫn có `from` và `to`.
Chi tiết của gateway nằm trong khóa mới `gateway_details`.

Hai khóa về activity, dùng cho hai mục đích khác nhau:
  activities      chỉ task theo BPMN (task, sendTask, receiveTask...).
  dfg_activities  task + startEvent + endEvent, đúng danh sách trong dfg_activities.txt và đúng
                  cách bộ 104 câu hỏi của bài báo hiểu chữ "activity" ('customer order',
                  'order completed' có đáp án Yes). Câu hỏi cấu trúc phải đối chiếu với khóa này.
"""
from __future__ import annotations

from typing import List

from .bpmn_parser import Node, ProcessGraph
from .dfg import dfg_nodes


def _names(nodes: List[Node]) -> List[str]:
  return [n.display_name for n in nodes]


def _gateway_detail(g: ProcessGraph, node: Node) -> dict:
  return {
    "id": node.id,
    "name": node.name,
    "reference": node.display_name,
    "lookup": node.lookup,
    "type": node.type,
    "incoming": len(g.predecessors(node.id)),
    "outgoing": len(g.successors(node.id)),
  }


def build_ground_truth(g: ProcessGraph) -> dict:
  """Không có thời gian sinh trong kết quả, nên cùng BPMN luôn cho cùng một file."""
  gateways = g.by_kind("gateway")
  return {
    "process_id": g.process_id,
    "process_name": g.process_name,
    "source_files": [g.source_file],
    "start_events": _names(g.by_type("startEvent")),
    "end_events": _names(g.by_type("endEvent")),
    "activities": _names(g.by_kind("activity")),
    "dfg_activities": [g.nodes[i].display_name for i in dfg_nodes(g)],
    "gateways": _names(gateways),
    "gateway_details": [_gateway_detail(g, n) for n in gateways],
    "sequence_flows": [
      {"from": g.nodes[f.source].display_name,
       "to": g.nodes[f.target].display_name,
       "condition": f.name}
      for f in g.flows
    ],
  }
