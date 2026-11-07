from bpllm.chunking.chunking_processor import EnrichedBPMNChunker
from bpllm.config import PROJECT_ROOT

BPMN = """<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL">
  <collaboration id="c1"><participant id="p1" name="Demo" processRef="pr1"/></collaboration>
  <process id="pr1">
    <startEvent id="s1" name="Start"/>
    <task id="t1" name="Check order"/>
    <exclusiveGateway id="g1" name="Valid?"/>
    <task id="t2" name="Ship"/>
    <endEvent id="e1" name="Done"/>
    <sequenceFlow id="f1" sourceRef="s1" targetRef="t1"/>
    <sequenceFlow id="f2" sourceRef="t1" targetRef="g1"/>
    <sequenceFlow id="f3" name="yes" sourceRef="g1" targetRef="t2"/>
    <sequenceFlow id="f4" name="no" sourceRef="g1" targetRef="e1"/>
    <sequenceFlow id="f5" sourceRef="t2" targetRef="e1"/>
  </process>
</definitions>
"""


def by_node_id(chunks):
  return {c["metadata"]["node_id"]: c for c in chunks}


def test_overview_counts_tasks_and_gateways():
  overview = EnrichedBPMNChunker().chunk(BPMN, "demo.bpmn")[0]
  assert overview["metadata"]["node_type"] == "process_overview"
  assert "Process 'Demo'" in overview["text"]
  assert "Contains 2 tasks and 1 gateways" in overview["text"]


def test_one_chunk_per_node_plus_overview():
  chunks = EnrichedBPMNChunker().chunk(BPMN, "demo.bpmn")
  assert len(chunks) == 6


def test_task_chunk_uses_names_instead_of_ids():
  text = by_node_id(EnrichedBPMNChunker().chunk(BPMN))["t1"]["text"]
  assert "Preceded by: Start event 'Start'" in text
  assert "Followed by: Exclusive gateway (XOR decision) 'Valid?'" in text


def test_gateway_chunk_lists_branch_conditions():
  text = by_node_id(EnrichedBPMNChunker().chunk(BPMN))["g1"]["text"]
  assert "if 'yes' -> Task 'Ship'" in text
  assert "if 'no' -> End event 'Done'" in text


def test_real_bpmn_files_can_be_chunked():
  files = list((PROJECT_ROOT / "data" / "raw").glob("*.bpmn"))
  assert len(files) == 3
  for path in files:
    chunks = EnrichedBPMNChunker().chunk(
        path.read_text(encoding="utf-8"), path.name
    )
    assert len(chunks) > 1, path.name
