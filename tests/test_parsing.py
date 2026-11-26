"""Tiêu chí nghiệm thu Phase 1 ở mức thư viện: làm sạch BPMN, graph, gateway, DFG text."""
import csv
import re
import xml.etree.ElementTree as ET
from collections import Counter

import pytest

from bpllm.config import PROJECT_ROOT
from bpllm.parsing import (BpmnFormatError, activities_text, dfg_edges, flows_text,
                           normalize_name, parse_bpmn, parse_bpmn_text, parse_flows_text,
                           strip_graphics, strip_graphics_report)

RAW = PROJECT_ROOT / "data" / "raw"
ORIGINAL = RAW / "original"
QUESTIONS = PROJECT_ROOT / "data" / "questions" / "3_questions_answers_refined.csv"
PIDS = ["ecommerce", "food_delivery", "reimbursement"]

# Đếm từ file BPMN gốc
EXPECTED = {
    "food_delivery": dict(activities=17, exclusive_gateways=4, parallel_gateways=2,
                          start_events=1, end_events=1, sequence_flows=27),
    "ecommerce": dict(activities=15, exclusive_gateways=4, parallel_gateways=0,
                      start_events=1, end_events=1, sequence_flows=22),
    "reimbursement": dict(activities=11, exclusive_gateways=5, parallel_gateways=0,
                          start_events=1, end_events=2, sequence_flows=20),
}
UNNAMED_GATEWAYS = {"food_delivery": 4, "ecommerce": 2, "reimbursement": 2}
PROCESS_NAMES = {"food_delivery": "Food Delivery", "ecommerce": "E-commerce",
                 "reimbursement": "Reimbursement"}


def _cleaned(pid):
  return strip_graphics((ORIGINAL / f"{pid}.bpmn").read_text(encoding="utf-8"))


@pytest.fixture(scope="module", params=PIDS)
def graph(request):
  return parse_bpmn_text(_cleaned(request.param), request.param, f"{request.param}.bpmn")


@pytest.fixture(scope="module")
def food():
  return parse_bpmn(RAW / "food_delivery.bpmn", "food_delivery")


def _bpmn(tmp_path, body):
  path = tmp_path / "x.bpmn"
  path.write_text('<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL">'
                  f'<process id="P">{body}</process></definitions>', encoding="utf-8")
  return path


def _split(tmp_path, gateway):
  return parse_bpmn(_bpmn(tmp_path, (
      f'<startEvent id="s"/><task id="a" name="A"/><{gateway} id="x"/>'
      '<task id="b" name="B"/><task id="c" name="C"/><endEvent id="e"/>'
      '<sequenceFlow id="1" sourceRef="s" targetRef="a"/>'
      '<sequenceFlow id="2" sourceRef="a" targetRef="x"/>'
      '<sequenceFlow id="3" sourceRef="x" targetRef="b"/>'
      '<sequenceFlow id="4" sourceRef="x" targetRef="c"/>'
      '<sequenceFlow id="5" sourceRef="b" targetRef="e"/>'
      '<sequenceFlow id="6" sourceRef="c" targetRef="e"/>')), "x")


# ---------- Bỏ đồ họa ----------
@pytest.mark.parametrize("pid", PIDS)
def test_cleaned_file_has_only_the_bpmn_namespace(pid):
  cleaned = _cleaned(pid)
  assert set(re.findall(r'xmlns(?::\w+)?="([^"]+)"', cleaned)) == {
      "http://www.omg.org/spec/BPMN/20100524/MODEL"}
  assert not re.search(r"<ns\d+:", cleaned)
  for leftover in ("BPMNShape", "BPMNEdge", "BPMNDiagram", "Bizagi", "extensionElements"):
    assert leftover not in cleaned


def _elements(xml_text):
  result = Counter()
  for el in ET.fromstring(xml_text).iter():
    tag = el.tag.split("}")[-1]
    attrs = dict(el.attrib)
    if tag == "definitions":
      # R7: cleaner giữ targetNamespace (XSD bắt buộc), còn file đối chiếu trong data/raw/
      # đã bị xóa thuộc tính này khi làm sạch tay. Bỏ qua đúng một thuộc tính này khi so.
      attrs.pop("targetNamespace", None)
    result[(tag, tuple(sorted(attrs.items())), (el.text or "").strip())] += 1
  return result


@pytest.mark.parametrize("pid", PIDS)
def test_cleaned_original_has_exactly_the_same_elements_as_raw(pid):
  # Bằng chứng mạnh nhất: file sinh tự động trùng từng phần tử với file đã làm sạch sẵn
  raw = (RAW / f"{pid}.bpmn").read_text(encoding="utf-8")
  assert _elements(_cleaned(pid)) == _elements(raw)


@pytest.mark.parametrize("pid", PIDS)
def test_cleaning_twice_changes_nothing(pid):
  assert strip_graphics(_cleaned(pid)) == _cleaned(pid)


def test_cleaning_reports_what_was_removed():
  text = (ORIGINAL / "reimbursement.bpmn").read_text(encoding="utf-8")
  removed = strip_graphics_report(text)[1]
  assert removed["BPMNShape"] == 21
  assert removed["BizagiExtensions"] == 23
  assert removed["boundaryEvent"] == 1


def test_cleaning_keeps_a_boundary_event_that_has_flows(tmp_path):
  cleaned = strip_graphics(_bpmn(tmp_path, (
      '<task id="t"/><boundaryEvent id="used" attachedToRef="t"/><boundaryEvent id="idle" attachedToRef="t"/>'
      '<task id="h"/><sequenceFlow id="f" sourceRef="used" targetRef="h"/>')).read_text(encoding="utf-8"))
  assert 'id="used"' in cleaned
  assert 'id="idle"' not in cleaned


def test_cleaning_keeps_data_store_and_moves_annotation_to_its_name():
  # Tên CSDL của Food Delivery chỉ nằm trong textAnnotation của file gốc
  cleaned = _cleaned("food_delivery")
  assert 'name="customer database"' in cleaned
  assert 'name="payment database"' in cleaned
  assert "textAnnotation" not in cleaned


# ---------- Graph ----------
def test_counts(graph):
  assert graph.counts() == EXPECTED[graph.process_id]


def test_graph_is_valid(graph):
  # Toàn vẹn tham chiếu, đi tới được từ start, tới được end, không trùng tên
  assert graph.validate() == []


@pytest.mark.parametrize("pid", PIDS)
def test_original_and_raw_give_the_same_graph(pid):
  cleaned = parse_bpmn_text(_cleaned(pid), pid, f"{pid}.bpmn")
  assert cleaned.diff(parse_bpmn(RAW / f"{pid}.bpmn", pid)) == []


def test_uncleaned_reimbursement_is_invalid_so_it_must_be_cleaned_first():
  # Sự kiện biên không có flow trong file Bizagi
  g = parse_bpmn(ORIGINAL / "reimbursement.bpmn", "reimbursement")
  assert any("unreachable" in e for e in g.validate())


def test_graph_diff_finds_a_changed_flow(tmp_path):
  a = parse_bpmn(_bpmn(tmp_path, '<task id="a"/><task id="b"/><sequenceFlow id="1" sourceRef="a" targetRef="b"/>'), "x")
  b = parse_bpmn(_bpmn(tmp_path, '<task id="a"/><task id="b"/><sequenceFlow id="1" sourceRef="b" targetRef="a"/>'), "x")
  assert len(a.diff(b)) == 2


def test_names_are_normalised(graph):
  # R10: Node không còn raw_name; tên gốc nằm trong CleanResult.renamed (xem test_phase1_fixes.py)
  for node in graph.nodes.values():
    assert node.name == normalize_name(node.name)
    assert "  " not in node.name


def test_normalize_name():
  assert normalize_name("check credit\xa0 card and the payment") == "check credit card and the payment"
  assert normalize_name("  a\nb ") == "a b"
  assert normalize_name(None) == ""


def test_graph_json_round_trip(graph, tmp_path):
  path = tmp_path / "graph.json"
  graph.save(path)
  loaded = type(graph).load(path)
  assert loaded.counts() == graph.counts()
  assert loaded.nodes == graph.nodes
  assert loaded.flows == graph.flows
  assert loaded.participant == graph.participant


def test_process_name_is_canonical_and_participant_is_kept(graph):
  assert graph.process_name == PROCESS_NAMES[graph.process_id]
  assert graph.participant
  assert activities_text(graph).startswith(f"The {graph.process_name} process")
  assert flows_text(graph).startswith(f"The {graph.process_name} process")


def test_duplicate_node_id_is_rejected(tmp_path):
  path = _bpmn(tmp_path, '<task id="t" name="A"/><task id="t" name="B"/>')
  with pytest.raises(BpmnFormatError, match="'t'"):
    parse_bpmn(path, "x")


def test_decision_gateways_without_branch_labels_are_reported(graph):
  expected = {"ecommerce": 2, "food_delivery": 0, "reimbursement": 0}
  assert len(graph.warnings()) == expected[graph.process_id]


# ---------- Gateway: có tên thì gọi tên, không tên thì gọi id ----------
def test_gateway_reference_follows_the_naming_rule(graph):
  gateways = graph.by_kind("gateway")
  unnamed = [n for n in gateways if not n.name]
  assert len(unnamed) == UNNAMED_GATEWAYS[graph.process_id]
  for node in gateways:
    assert node.lookup == ("name" if node.name else "id")
    assert node.display_name == (node.name or node.id)


def test_every_gateway_can_be_found_by_id(graph):
  for node in graph.by_kind("gateway"):
    assert node.id
    assert graph.find_gateway(node.id) is node
    assert graph.find_gateway(node.id.upper()) is node


def test_named_gateway_can_be_found_by_name(graph):
  for node in graph.by_kind("gateway"):
    if node.name:
      assert graph.find_gateway(f"  {node.name.upper()} ") is node


def test_find_gateway_ignores_other_elements(graph):
  activity = graph.by_kind("activity")[0]
  assert graph.find(activity.id) is activity
  assert graph.find_gateway(activity.id) is None
  assert graph.find_gateway(activity.name) is None
  assert graph.find_gateway("") is None


def test_empty_name_attribute_counts_as_unnamed(tmp_path):
  g = parse_bpmn(_bpmn(tmp_path, '<exclusiveGateway id="x" name="  "/>'), "x")
  assert g.nodes["x"].lookup == "id"
  assert g.find_gateway("") is None


def test_gateway_without_id_is_rejected_and_named_in_the_error(tmp_path):
  # sequenceFlow nối bằng id, nên gateway không có id không thể nằm trong luồng
  path = _bpmn(tmp_path, '<exclusiveGateway name="Is it ok?"/>')
  with pytest.raises(BpmnFormatError, match="Is it ok"):
    parse_bpmn(path, "x")


# ---------- DFG natural text cho cả 3 quy trình ----------
LINE_FORMATS = (
    r'The .+ process defines the following transitions:',
    r'The process (starts from|ends with) ".+"\.',
    # R5: đuôi "(parallel branch)" / "(after all parallel branches complete)" ở chế độ full
    r'From ".+", the process continues with ".+"( \(parallel branch\))?( \(after all parallel branches complete\))?\.',
    r'From ".+", the process can continue with ".+"( \(parallel branch\))?( \(after all parallel branches complete\))? if the branch is ".+"\.',
    # nhánh không nhãn của gateway có nhánh khác mang nhãn
    r'From ".+", the process can continue with ".+"( \(parallel branch\))?( \(after all parallel branches complete\))? otherwise\.',
    r'Gateway ".+" is (an unnamed|an?) \w+ gateway.*\.',
)


@pytest.mark.parametrize("mode", ["paper", "full", "gateway"])
def test_every_process_uses_the_same_text_format(graph, mode):
  for line in flows_text(graph, mode).splitlines():
    assert any(re.fullmatch(p, line) for p in LINE_FORMATS), line


def test_activities_text_lists_activities_and_events(graph):
  lines = activities_text(graph).splitlines()[1:]
  c = graph.counts()
  assert len(lines) == c["activities"] + c["start_events"] + c["end_events"]


def test_paper_mode_drops_exactly_the_flows_touching_unnamed_gateways(graph):
  unnamed = {n.id for n in graph.by_kind("gateway") if not n.name}
  kept = [f for f in graph.flows if f.source not in unnamed and f.target not in unnamed]
  assert len(dfg_edges(graph, "paper")) == len(kept)
  assert len(kept) < len(graph.flows)


def test_gateway_mode_keeps_every_flow(graph):
  assert len(dfg_edges(graph, "gateway")) == len(graph.flows)
  text = flows_text(graph, "gateway")
  for node in graph.by_kind("gateway"):
    assert f'Gateway "{node.display_name}"' in text
    assert node.type.replace("Gateway", " gateway") in text


def test_full_mode_never_mentions_unnamed_gateways(graph):
  unnamed = {n.id for n in graph.by_kind("gateway") if not n.name}
  for src, tgt, _ in dfg_edges(graph, "full"):
    assert src not in unnamed and tgt not in unnamed


def test_unknown_mode_is_rejected(food):
  with pytest.raises(ValueError):
    dfg_edges(food, "other")


def test_paper_activities_file_matches_graph(food):
  # 19 dòng = 17 activity + start + end
  lines = (RAW / "food_delivery_dfg_activities.txt").read_text(encoding="utf-8").splitlines()[1:]
  paper = {normalize_name(l).lower() for l in lines if l.strip()}
  ours = {normalize_name(l).lower() for l in activities_text(food).splitlines()[1:]}
  assert paper == ours
  assert len(paper) == 19


def test_paper_flows_file_matches_paper_mode_line_by_line(food):
  # File của bài = mọi flow không chạm gateway không tên (27 - 12 = 15)
  paper = (RAW / "food_delivery_dfg_flows.txt").read_text(encoding="utf-8").splitlines()
  assert set(flows_text(food, "paper").splitlines()) == set(paper)
  assert len(parse_flows_text("\n".join(paper))) == 15


def test_full_mode_keeps_transitions_hidden_behind_unnamed_gateways(food):
  full = {(food.nodes[s].name.lower(), food.nodes[t].name.lower()) for s, t, _ in dfg_edges(food, "full")}
  for pair in [("check payment", "register the order"),
               ("register the order", "select rider and create work proposal"),
               ("the rider refused the order", "select rider and create work proposal"),
               ("the rider accepted the order", "send confirmation to rider"),
               ("send to customer the waiting time", "notification order retired")]:
    assert pair in full


def test_full_mode_distinguishes_parallel_from_exclusive_split(tmp_path):
  assert 'continues with "B" (parallel branch)' in flows_text(_split(tmp_path, "parallelGateway"), "full")
  assert "parallel" not in flows_text(_split(tmp_path, "exclusiveGateway"), "full")


def test_food_delivery_parallel_branches_are_stated_and_still_parsable(food):
  text = flows_text(food, "full")
  assert text.count("(parallel branch)") == 2
  # R5: "notification order retired" phải chờ cả 2 nhánh (AND-join Gateway_0iw6ax3)
  assert text.count("(after all parallel branches complete)") == 2
  assert ("the rider accepted the order", "estimated arrival time") in parse_flows_text(text)
  assert len(parse_flows_text(text)) == len(dfg_edges(food, "full"))


def test_full_mode_order_does_not_depend_on_insertion(tmp_path):
  g = parse_bpmn(_bpmn(tmp_path, (
      '<startEvent id="s"/><exclusiveGateway id="d" name="D?"/><exclusiveGateway id="m"/>'
      '<task id="t" name="T"/><endEvent id="e"/>'
      '<sequenceFlow id="1" sourceRef="s" targetRef="d"/>'
      '<sequenceFlow id="2" name="zeta" sourceRef="d" targetRef="m"/>'
      '<sequenceFlow id="3" name="alpha" sourceRef="d" targetRef="m"/>'
      '<sequenceFlow id="4" sourceRef="m" targetRef="t"/>'
      '<sequenceFlow id="5" sourceRef="t" targetRef="e"/>')), "x")
  assert [c for _, _, c in dfg_edges(g, "full") if c] == ["alpha", "zeta"]


# ---------- Graph và text phải trả lời đúng bộ câu hỏi của bài báo ----------
def _questions():
  rows = list(csv.DictReader(QUESTIONS.read_text(encoding="utf-8-sig").splitlines()))
  assert len(rows) == 104
  return rows


def test_graph_agrees_with_every_benchmark_label(food):
  for row in _questions():
    question = row["question"]
    names = re.findall(r'"([^"]+)"', question)
    if "sequence flow" in question:
      src, tgt = food.find(names[0]), food.find(names[1])
      actual = bool(src and tgt and food.has_flow(src.id, tgt.id))
    elif "gateway" in question:
      wanted = "parallelGateway" if "parallel gateway" in question else "exclusiveGateway"
      node = food.find_gateway(names[0])
      actual = bool(node and node.type == wanted)
    else:
      actual = food.find(names[0]) is not None
    assert actual == (row["answer"] == "Yes"), question


def test_gateway_text_answers_every_flow_and_gateway_question(food):
  # Bản paper và full không trả lời được 12 câu flow "Yes" chạm gateway không tên
  text = flows_text(food, "gateway")
  pairs = parse_flows_text(text)
  checked = 0
  for row in _questions():
    question = row["question"]
    names = re.findall(r'"([^"]+)"', question)
    if "sequence flow" in question:
      actual = (normalize_name(names[0]).lower(), normalize_name(names[1]).lower()) in pairs
    elif "gateway" in question:
      kind = "parallel gateway" if "parallel gateway" in question else "exclusive gateway"
      actual = bool(re.search(rf'Gateway "{re.escape(names[0])}" is [^\n]*{kind}', text, re.I))
    else:
      continue
    checked += 1
    assert actual == (row["answer"] == "Yes"), question
  assert checked == 60


def test_paper_text_cannot_answer_flows_through_unnamed_gateways(food):
  pairs = parse_flows_text(flows_text(food, "paper"))
  assert ("check payment", "gateway_0z24z44") not in pairs
  assert ("check payment", "gateway_0z24z44") in parse_flows_text(flows_text(food, "gateway"))


def test_unlabelled_xor_branch_is_written_as_otherwise():
  ecommerce = parse_bpmn(RAW / "ecommerce.bpmn", "ecommerce")
  text = flows_text(ecommerce, "paper")
  assert 'From "Is this a new customer?", the process can continue with "Recover client history" otherwise.' in text
  assert 'From "Is the courier available?", the process can continue with "Assign package to courier" otherwise.' in text
  # vẫn đọc lại được thành cặp (nguồn, đích)
  assert ("is this a new customer?", "recover client history") in parse_flows_text(text)


def test_food_delivery_text_has_no_otherwise_branch(food):
  # mọi nhánh XOR của Food Delivery đều có nhãn, nên file "paper" vẫn trùng file của bài báo
  assert "otherwise" not in flows_text(food, "paper")
