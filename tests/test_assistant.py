"""Luồng trả lời của Streamlit với embedder, store và LLM giả."""
from bpllm.rag.assistant import Assistant, guess_process
from bpllm.rag.graph_lookup import load_graph
from bpllm.rag.retriever import Retriever

CHUNKS = {
    "food_delivery": [
        ('<sendTask id="Activity_send" name="send work proposal">\n'
         '  <outgoing target="has the order been accepted?">Flow_1</outgoing>\n</sendTask>',
         "Activity_send", "send work proposal"),
        ('<task id="Activity_acc" name="the rider accepted the order" />', "Activity_acc",
         "the rider accepted the order"),
        ('<task id="Activity_ref" name="the rider refused the order" />', "Activity_ref",
         "the rider refused the order"),
        ('<task id="Activity_pay" name="pay rider" />', "Activity_pay", "pay rider"),
    ],
    "ecommerce": [('<task id="E1" name="Pay courier" />', "E1", "Pay courier")],
}


class FakeEmbedder:
  def encode(self, text):
    if isinstance(text, list):
      return [self.encode(t) for t in text]
    return [1.0, 0.0] if "rider" in text else [0.0, 1.0]


class FakeStore:
  def __init__(self):
    self.filters = []

  def search_top_k(self, vector, top_k, process_filter):
    self.filters.append(process_filter)
    return [{"score": 0.9 - i / 10, "content": text,
             "metadata": {"process_id": process_filter, "node_id": nid, "node_name": name,
                          "node_type": "task"}}
            for i, (text, nid, name) in enumerate(CHUNKS.get(process_filter, [])[:top_k])]


class FakeLLM:
  def __init__(self, reply="yes. There is such an activity.", fail=False):
    self.reply, self.fail, self.calls = reply, fail, []

  def chat(self, model, messages, max_tokens=None):
    self.calls.append((model, messages))
    if self.fail:
      raise ConnectionError("tunnel closed")
    return self.reply


PROFILES = {"food_delivery": [1.0, 0.0], "ecommerce": [0.0, 1.0], "reimbursement": [0.6, 0.6]}


def make(llm, quant="int4"):
  store = FakeStore()
  return Assistant(FakeEmbedder(), Retriever(FakeEmbedder(), store), llm, PROFILES, quant=quant), store


def test_guess_process_picks_closest_profile():
  assert guess_process([0.1, 0.9], PROFILES) == "ecommerce"


def test_yesno_question_uses_food_delivery_model_and_extracts_verdict():
  llm = FakeLLM()
  assistant, store = make(llm)
  answer = assistant.ask('Is there an activity with name="pay rider"?', "food_delivery")
  assert answer.kind == "yesno" and answer.verdict == "yes"
  assert answer.model == "angeloc1/llama3dot1FoodDel4v05"
  assert store.filters == ["food_delivery"]
  assert llm.calls[0][1][0]["content"].startswith("Use the following pieces of context")
  assert [c["node_id"] for c in answer.citations] == ["Activity_pay"]


def test_process_is_detected_and_routed_to_its_model():
  assistant, _ = make(FakeLLM(), quant="int8")
  answer = assistant.ask("Is there a task named Pay courier?")
  assert answer.process_id == "ecommerce"
  assert answer.model == "angeloc1/llama3dot1SimilarProcesses8"


def test_reimbursement_routes_to_different_processes_model():
  assistant, _ = make(FakeLLM())
  assert assistant.prepare("x", "reimbursement", "yesno").model == "angeloc1/llama3dot1DifferentProcesses4"


def test_next_step_question_is_checked_against_graph():
  reply = 'After "send work proposal", "the rider accepted the order" or "the rider refused the order".'
  assistant, _ = make(FakeLLM(reply))
  answer = assistant.ask('What happens after "send work proposal"?', "food_delivery")
  assert answer.kind == "next_step" and answer.verdict is None
  assert answer.asked_node["name"] == "send work proposal"
  assert answer.graph_agrees is True
  assert "come directly after" in answer.prompt
  assert {c["node_id"] for c in answer.citations} == {"Activity_send", "Activity_acc", "Activity_ref"}


def test_next_step_question_without_quotes_or_exact_name():
  reply = "The rider either accepts the order or refuses it."
  assistant, _ = make(FakeLLM(reply))
  answer = assistant.ask("What happens after the work proposal is sent?", "food_delivery")
  assert answer.kind == "next_step"
  assert answer.asked_node["name"] == "send work proposal"
  assert answer.prompt.endswith('(The question is about the step "send work proposal".)')
  assert answer.graph_agrees is True
  assert "Activity_send" in {c["node_id"] for c in answer.citations}


def test_chunk_of_asked_step_is_added_when_retrieval_misses_it():
  pay_id = load_graph("food_delivery").find("pay rider").id

  class Store:          # câu hỏi diễn đạt khác: lần tìm đầu không thấy chunk 'pay rider'
    def __init__(self):
      self.queries = []

    def search_top_k(self, vector, top_k, process_filter):
      self.queries.append(vector)
      hits = [("pay rider", pay_id)] if len(self.queries) == 2 else [("a", "A1"), ("b", "B1")]
      return [{"score": 0.5, "content": f"<task id='{i}' name='{n}' />",
               "metadata": {"node_id": i, "node_name": n, "process_id": process_filter}}
              for n, i in hits][:top_k]

  store = Store()
  assistant = Assistant(FakeEmbedder(), Retriever(FakeEmbedder(), store, top_k=2), FakeLLM(),
                        PROFILES)
  answer = assistant.prepare("what happens after we pay the rider?", "food_delivery")
  assert answer.asked_node == {"id": pay_id, "name": "pay rider"}
  assert [r["metadata"]["node_id"] for r in answer.results] == [pay_id, "A1"]
  assert "name='pay rider'" in answer.prompt


def test_yesno_question_recognises_steps_without_quotes():
  assistant, _ = make(FakeLLM("yes."))
  answer = assistant.ask("Is the rider paid at the end?", "food_delivery")
  assert answer.kind == "yesno"
  assert answer.names     # nhận ra ít nhất một bước liên quan


def test_incomplete_next_step_answer_is_flagged():
  assistant, _ = make(FakeLLM('Then "the rider accepted the order".'))
  answer = assistant.ask('What happens after "send work proposal"?', "food_delivery")
  assert answer.graph_agrees is False
  assert answer.matched_steps == ["the rider accepted the order"]


def test_llm_failure_is_reported_not_raised():
  assistant, _ = make(FakeLLM(fail=True))
  answer = assistant.ask('Is there an activity with name="pay rider"?', "food_delivery")
  assert answer.error.startswith("ConnectionError") and answer.text == ""


def test_prepare_does_not_call_llm():
  llm = FakeLLM()
  assistant, _ = make(llm)
  assistant.prepare('Is there an activity with name="pay rider"?', "food_delivery")
  assert llm.calls == []
