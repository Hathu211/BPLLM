import pytest

from bpllm.config import get_settings


@pytest.fixture(autouse=True)
def fresh_settings():
  """Mỗi test đọc lại cấu hình, không dùng lại kết quả đã cache."""
  get_settings.cache_clear()
  yield
  get_settings.cache_clear()
