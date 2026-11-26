"""Prompt, truy xuất, loại câu hỏi, tra graph, trích dẫn."""
import pytest

from bpllm.rag import graph_lookup
from bpllm.rag.citations import cite
from bpllm.rag.prompts import build_prompt, to_messages
from bpllm.rag.question_type import NEXT_STEP, YESNO, classify
from bpllm.rag.retriever import Retriever, clean_query

QUESTION = ('Ignore your previous answers. Is there an outgoing sequence flow from "A" to "B"?'
            " Also reference the corresponding piece of provided context if present.")


class FakeEmbedder:
  def __init__(self):
    self.seen = []

  def encode(self, text):
    self.seen.append(text)
    return [1.0, 0.0]


class FakeStore:
  def __init__(self, hits=None):
    self.calls = []
    self.hits = hits or [
        {"score": 0.9, "content": '<task id="t1" name="A" />',
         "metadata": {"node_id": "t1", "node_name": "A", "process_id": "p"}},
        {"score": 0.8, "content": '<task id="t2" name="B" />',
         "metadata": {"node_id": "t2", "node_name": "B", "process_id": "p"}},
        {"score": 0.7, "content": '<task id="t3" name="C" />',
         "metadata": {"node_id": "t3", "node_name": "C", "process_id": "p"}},
        {"score": 0.6, "content": '<task id="t4" name="D" />',
         "metadata": {"node_id": "t4", "node_name": "D", "process_id": "p"}}]

  def search_top_k(self, vector, top_k, process_filter):
    self.calls.append((vector, top_k, process_filter))
    return self.hits[:top_k]


# ---------- prompt ----------
def test_yesno_prompt_is_paper_figure_4_layout():
  prompt = build_prompt("Q?", ["<a/>", "<b/>"])
  assert prompt == ("Use the following pieces of context to answer the question at the end.\n"
                    "Answer 'yes' if true or 'no' if false.\n\n<a/>\n\n<b/>\n\nQuestion: Q?")


def test_next_step_prompt_differs_only_in_instruction():
  a, b = build_prompt("Q?", ["<a/>"]), build_prompt("Q?", ["<a/>"], "next_step")
  assert a.split("\n\n", 1)[1] == b.split("\n\n", 1)[1]
  assert "come directly after" in b


def test_next_step_prompt_names_the_recognised_step():
  prompt = build_prompt("what happens after the proposal is sent?", ["<a/>"], "next_step",
                        focus="send work proposal")
  assert prompt.endswith('(The question is about the step "send work proposal".)')
  assert "in their own words" in prompt


def test_yesno_prompt_ignores_focus_to_keep_paper_layout():
  assert build_prompt("Q?", ["<a/>"], "yesno", focus="x") == build_prompt("Q?", ["<a/>"])


def test_unknown_kind_is_rejected():
  with pytest.raises(ValueError):
    build_prompt("Q?", [], "chat")


def test_messages_are_a_single_user_turn():
  assert to_messages("p") == [{"role": "user", "content": "p"}]


# ---------- truy xuất ----------
def test_clean_query_keeps_only_the_question():
  assert clean_query(QUESTION) == 'Is there an outgoing sequence flow from "A" to "B"?'


def test_retriever_embeds_full_question_by_default_and_passes_filter():
  emb, store = FakeEmbedder(), FakeStore()
  Retriever(emb, store).retrieve(QUESTION, process_filter=["food_delivery", "ecommerce"])
  assert emb.seen == [QUESTION]
  assert store.calls == [([1.0, 0.0], 10, ["food_delivery", "ecommerce"])]


def test_retriever_can_clean_query():
  emb = FakeEmbedder()
  Retriever(emb, FakeStore(), clean=True).retrieve(QUESTION)
  assert emb.seen == [clean_query(QUESTION)]


# ---------- loại câu hỏi ----------
@pytest.mark.parametrize("question, kind", [
    (QUESTION, YESNO),
    ('Is there an activity with name="pay rider"?', YESNO),
    ('Is "pay rider" the step after "receive Customer Satisfaction"?', YESNO),
    ('What happens after "send work proposal"?', NEXT_STEP),
    ('What is the next step after "Review amount"?', NEXT_STEP),
    ('Which activity follows "register the order"?', NEXT_STEP),
    ('After "pay rider", what comes?', NEXT_STEP),
    ('Sau bước "Register new order" thì là bước gì?', NEXT_STEP),
    ('Bước tiếp theo của "pay rider" là gì?', NEXT_STEP),
    ('Có hoạt động "pay rider" không?', YESNO),
])
def test_classify(question, kind):
  assert classify(question) == kind


# ---------- graph ----------
@pytest.fixture
def food():
  return graph_lookup.load_graph("food_delivery")


def names(steps):
  return {(s["name"], s["condition"]) for s in steps}


def test_next_steps_go_through_a_named_decision(food):
  node = graph_lookup.find_mentioned_node(food, 'What happens after "send work proposal"?')
  steps = graph_lookup.next_steps(food, node.id)
  assert names(steps) == {("the rider accepted the order", "yes"), ("the rider refused the order", "no")}
  assert {s["decision"] for s in steps} == {"has the order been accepted?"}


def test_next_steps_go_through_unnamed_parallel_gateway(food):
  node = food.find("the rider accepted the order")
  assert names(graph_lookup.next_steps(food, node.id)) == {
      ("Estimated Arrival Time", ""), ("send confirmation to rider", "")}


def test_next_steps_of_end_event_is_empty(food):
  assert graph_lookup.next_steps(food, food.find("order completed").id) == []


def test_find_mentioned_node_without_quotes_takes_longest_name(food):
  node = graph_lookup.find_mentioned_node(food, "what comes after notification order retired to the client")
  assert node.name == "notification order retired to the client"


def test_find_mentioned_node_returns_none_when_absent(food):
  assert graph_lookup.find_mentioned_node(food, "what happens after lunch?") is None


@pytest.mark.parametrize("process_id, question, step", [
    ("food_delivery", "What happens after the work proposal is sent?", "send work proposal"),
    ("food_delivery", "what happens after the order is registered", "register the order"),
    ("food_delivery", "what comes after the rider accepts the order?", "the rider accepted the order"),
    ("food_delivery", "after checking the credit card what is next", "check credit card and the payment"),
    ("ecommerce", "What is the next step after a new account is created?", "Create new account"),
    ("ecommerce", "Sau bước register new order thì là bước gì?", "Register new order"),
    ("reimbursement", "what happens after the expense report is approved", "Approve expense report"),
    ("reimbursement", "What do we do after reviewing the amount?", "Review amount"),
])
def test_step_is_found_without_quotes_or_exact_name(process_id, question, step):
  graph = graph_lookup.load_graph(process_id)
  assert graph_lookup.find_mentioned_node(graph, question).name == step


def test_weak_match_is_only_a_last_resort_without_embedding(food):
  # Chỉ trùng 'rider': không có embedder thì trả về khớp yếu (app luôn có embedder, xem test dưới)
  node = graph_lookup.find_mentioned_node(food, "after the rider says no, what happens?")
  assert node.name == "pay rider"


def test_embedding_decides_weak_matches(food):
  class Embedder:      # câu hỏi giống 'the rider refused the order' nhất
    def encode(self, texts):
      return [[1.0, 0.0] if t in ("the rider says no, what happens?", "the rider refused the order")
              else [0.0, 1.0] for t in texts]
  node = graph_lookup.find_mentioned_node(food, "after the rider says no, what happens?", Embedder())
  assert node.name == "the rider refused the order"


@pytest.mark.parametrize("word, stem", [("approved", "approv"), ("approve", "approv"),
                                        ("registered", "register"), ("checking", "check"),
                                        ("orders", "order")])
def test_stem(word, stem):
  assert graph_lookup._stem(word) == stem


def test_mentioned_names_lists_every_exact_name(food):
  names = graph_lookup.mentioned_names(food, "Is there a flow from register the order to pay rider?")
  assert set(names) == {"register the order", "pay rider"}


def test_mentioned_steps():
  steps = [{"name": "pay rider"}, {"name": "order completed"}]
  assert graph_lookup.mentioned_steps("Next comes  Pay Rider.", steps) == ["pay rider"]


def test_mentioned_steps_accepts_paraphrase():
  steps = [{"name": "the rider accepted the order"}, {"name": "the rider refused the order"},
           {"name": "pay rider"}]
  said = "Either the rider accepts the order, or the rider refuses it."
  assert graph_lookup.mentioned_steps(said, steps) == ["the rider accepted the order",
                                                       "the rider refused the order"]


# ---------- trích dẫn ----------
def test_cite_keeps_chunks_named_in_answer_or_question():
  cited = cite(FakeStore().hits, 'After "B" comes "C".', 'What is after "B"?')
  assert [c["node_id"] for c in cited] == ["t2", "t3"]
  assert cited[0]["rank"] == 2 and cited[0]["text"].startswith("<task")


def test_cite_falls_back_to_top_chunks():
  assert [c["rank"] for c in cite(FakeStore().hits, "no.", "")] == [1, 2, 3]


def test_cite_finds_quoted_name_inside_enriched_attributes():
  hits = FakeStore().hits + [{
      "score": 0.5, "content": '<exclusiveGateway id="g" name="OK?">\n'
                               '  <outgoing target="Approve report">f</outgoing>\n</exclusiveGateway>',
      "metadata": {"node_id": "g", "node_name": "OK?", "process_id": "p"}}]
  cited = cite(hits, "yes.", 'Is there an activity with name="Approve report"?')
  assert [c["node_id"] for c in cited] == ["g"]


def test_cite_uses_names_recognised_from_graph():
  # người dùng không viết tên bước, app nhận diện ra 'C'
  cited = cite(FakeStore().hits, "yes.", "is the third step done?", names=["C"])
  assert [c["node_id"] for c in cited] == ["t3"]


def test_cite_always_includes_asked_node():
  cited = cite(FakeStore().hits, "yes", "", must_include="t4")
  assert [c["node_id"] for c in cited] == ["t4"]
