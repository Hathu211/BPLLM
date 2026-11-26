import pytest

from bpllm.config import get_settings
from bpllm.rag import graph_lookup


@pytest.fixture(autouse=True)
def fresh_settings():
  """Mỗi test đọc lại cấu hình, không dùng lại kết quả đã cache."""
  get_settings.cache_clear()
  yield
  get_settings.cache_clear()
  graph_lookup.load_graph.cache_clear()
