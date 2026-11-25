from bpllm.rag.retriever import INSTRUCTION, Retriever, build_input, clean_query

QUESTION = ('Ignore your previous answers. Is there an outgoing sequence flow from "A" to "B"?'
            " Also reference the corresponding piece of provided context if present.")


class FakeEmbedder:
  def __init__(self):
    self.seen = []

  def encode(self, text):
    self.seen.append(text)
    return [1.0, 0.0]


class FakeStore:
  def __init__(self):
    self.calls = []

  def search_top_k(self, vector, top_k, process_filter):
    self.calls.append((vector, top_k, process_filter))
    return [{"score": 0.9, "content": "<task id=\"t1\" name=\"A\" />", "metadata": {}},
            {"score": 0.8, "content": "<task id=\"t2\" name=\"B\" />", "metadata": {}}]


def test_clean_query_keeps_only_the_question():
  assert clean_query(QUESTION) == 'Is there an outgoing sequence flow from "A" to "B"?'


def test_retriever_passes_top_k_and_process_filter():
  emb, store = FakeEmbedder(), FakeStore()
  Retriever(emb, store).retrieve(QUESTION, process_id="food_delivery")
  assert store.calls == [([1.0, 0.0], 10, "food_delivery")]
  assert emb.seen == [QUESTION]          # mặc định embed nguyên câu như bài báo


def test_retriever_can_clean_query():
  emb = FakeEmbedder()
  Retriever(emb, FakeStore(), clean=True).retrieve(QUESTION)
  assert emb.seen == [clean_query(QUESTION)]


def test_input_has_same_layout_as_fine_tune_data():
  text = build_input("Q?", FakeStore().search_top_k(None, 10, None), "food_delivery")
  assert text == ('Process: Food Delivery\nContext BPMN:\n'
                  '<task id="t1" name="A" />\n\n<task id="t2" name="B" />\n\n'
                  'Question: Q?')
  assert INSTRUCTION.startswith("Use the following pieces of context")
