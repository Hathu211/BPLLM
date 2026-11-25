import json

from bpllm.chunking.chunking_processor import (BPMNSpecificChunker, chunk_all,
                                               chunk_process_dir, process_dirs)
from bpllm.config import PROJECT_ROOT

BPMN = """<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL">
  <collaboration id="c1"><participant id="p1" name="Demo" processRef="pr1"/></collaboration>
  <process id="pr1">
    <startEvent id="s1" name="Start">
      <outgoing>f1</outgoing>
    </startEvent>
    <task id="t1" name="Check order">
      <incoming>f1</incoming>
      <outgoing>f2</outgoing>
    </task>
    <exclusiveGateway id="g1">
      <incoming>f2</incoming>
      <outgoing>f3</outgoing>
      <outgoing>f4</outgoing>
    </exclusiveGateway>
    <sendTask id="t2" name="Ship">
      <incoming>f3</incoming>
      <outgoing>f5</outgoing>
    </sendTask>
    <endEvent id="e1" name="Done">
      <incoming>f4</incoming>
      <incoming>f5</incoming>
    </endEvent>
    <sequenceFlow id="f1" sourceRef="s1" targetRef="t1"/>
    <sequenceFlow id="f2" sourceRef="t1" targetRef="g1"/>
    <sequenceFlow id="f3" name="yes" sourceRef="g1" targetRef="t2"/>
    <sequenceFlow id="f4" name="no" sourceRef="g1" targetRef="e1"/>
    <sequenceFlow id="f5" sourceRef="t2" targetRef="e1"/>
  </process>
</definitions>
"""
PROCESSED = PROJECT_ROOT / "data" / "processed"


def chunks_by_id():
  chunks = BPMNSpecificChunker().chunk(BPMN, "demo", "Demo")
  return {c["metadata"]["node_id"]: c for c in chunks}


def test_one_chunk_per_node_and_no_sequence_flow_chunk():
  chunks = chunks_by_id()
  assert set(chunks) == {"s1", "t1", "g1", "t2", "e1"}
  assert not any("<sequenceFlow" in c["text"] for c in chunks.values())


def test_chunk_is_the_raw_xml_of_the_node():
  text = chunks_by_id()["t1"]["text"]
  assert text == ('<task id="t1" name="Check order">\n'
                  '  <incoming>f1</incoming>\n'
                  '  <outgoing>f2</outgoing>\n'
                  '</task>')
  assert "xmlns" not in text and "ns0:" not in text


def test_unnamed_gateway_keeps_its_id():
  chunk = chunks_by_id()["g1"]
  assert chunk["text"].startswith('<exclusiveGateway id="g1">')
  assert chunk["metadata"]["node_name"] == ""
  assert chunk["metadata"]["node_kind"] == "gateway"


def test_metadata_carries_process_for_filtering():
  meta = chunks_by_id()["t2"]["metadata"]
  assert meta["process_id"] == "demo"
  assert meta["process_name"] == "Demo"
  assert meta["node_type"] == "sendTask"
  assert meta["node_kind"] == "activity"


def test_known_process_name_comes_from_process_names():
  chunk = BPMNSpecificChunker().chunk(BPMN, "food_delivery")[0]
  assert chunk["metadata"]["process_name"] == "Food Delivery"


def test_processed_files_give_one_chunk_per_graph_node():
  dirs = process_dirs(PROCESSED)
  assert [d.name for d in dirs] == ["ecommerce", "food_delivery", "reimbursement"]
  for d in dirs:
    graph = json.loads((d / "graph.json").read_text(encoding="utf-8"))
    chunks = chunk_process_dir(d)
    assert {c["metadata"]["node_id"] for c in chunks} == {n["id"] for n in graph["nodes"]}, d.name
    assert all(c["metadata"]["process_name"] == graph["process_name"] for c in chunks)


def test_every_benchmark_flow_is_visible_in_two_chunks():
  # Flow A -> B: id của flow nằm trong <outgoing> của A và <incoming> của B
  d = PROCESSED / "food_delivery"
  graph = json.loads((d / "graph.json").read_text(encoding="utf-8"))
  text = {c["metadata"]["node_id"]: c["text"] for c in chunk_process_dir(d)}
  for f in graph["flows"]:
    assert f"<outgoing>{f['id']}</outgoing>" in text[f["source"]], f["id"]
    assert f"<incoming>{f['id']}</incoming>" in text[f["target"]], f["id"]


def test_chunk_all_can_select_processes():
  chunks = chunk_all(PROCESSED, process_ids=["food_delivery"])
  assert {c["metadata"]["process_id"] for c in chunks} == {"food_delivery"}
  assert len(chunks) == 25


# ----- Chế độ enrich (cải tiến) -----

def enriched_by_id():
  chunks = BPMNSpecificChunker(enrich=True).chunk(BPMN, "demo", "Demo")
  return {c["metadata"]["node_id"]: c for c in chunks}


def test_enrich_adds_other_end_name_and_condition():
  assert enriched_by_id()["g1"]["text"] == (
      '<exclusiveGateway id="g1">\n'
      '  <incoming source="Check order">f2</incoming>\n'
      '  <outgoing target="Ship" condition="yes">f3</outgoing>\n'
      '  <outgoing target="Done" condition="no">f4</outgoing>\n'
      '</exclusiveGateway>')


def test_enrich_uses_id_when_other_end_has_no_name():
  assert '<outgoing target="g1">f2</outgoing>' in enriched_by_id()["t1"]["text"]


def test_enrich_keeps_one_chunk_per_node_and_marks_mode():
  plain, rich = chunks_by_id(), enriched_by_id()
  assert set(plain) == set(rich)
  assert {c["metadata"]["chunking"] for c in plain.values()} == {"bpmn_specific"}
  assert {c["metadata"]["chunking"] for c in rich.values()} == {"bpmn_enriched"}


def test_enrich_does_not_change_the_parsed_tree():
  # deepcopy: chunk thường sinh sau chunk enrich vẫn không có thuộc tính thêm
  BPMNSpecificChunker(enrich=True).chunk(BPMN, "demo")
  assert "target=" not in chunks_by_id()["t1"]["text"]


def test_enrich_on_processed_files_names_every_flow_end():
  d = PROCESSED / "food_delivery"
  graph = json.loads((d / "graph.json").read_text(encoding="utf-8"))
  name = {n["id"]: n["name"] or n["id"] for n in graph["nodes"]}
  text = {c["metadata"]["node_id"]: c["text"]
          for c in chunk_process_dir(d, BPMNSpecificChunker(enrich=True))}
  for f in graph["flows"]:
    assert f'target="{name[f["target"]]}"' in text[f["source"]], f["id"]
    assert f'source="{name[f["source"]]}"' in text[f["target"]], f["id"]
