"""Giữ cho các lỗi cấu hình của repo cũ không quay lại."""
import tomllib

import yaml

from bpllm.config import PROJECT_ROOT

SUBPACKAGES = ["chunking", "embeddings", "evaluation", "llm", "parsing", "rag", "vectorstore"]


def test_every_package_has_init():
  root = PROJECT_ROOT / "src" / "bpllm"
  assert (root / "__init__.py").is_file()
  for name in SUBPACKAGES:
    assert (root / name / "__init__.py").is_file(), name


def test_entry_points_do_not_hack_imports():
  files = list((PROJECT_ROOT / "scripts").glob("*.py")) + list((PROJECT_ROOT / "app").glob("*.py"))
  assert files
  for path in files:
    text = path.read_text(encoding="utf-8")
    assert "sys.path" not in text and "src.bpllm" not in text, path.name


def test_compose_uses_own_names_and_ports():
  compose = yaml.safe_load((PROJECT_ROOT / "docker_compose.yml").read_text(encoding="utf-8"))
  qdrant = compose["services"]["qdrant"]
  assert compose["name"] == "bpllm2"
  assert qdrant["image"] == "qdrant/qdrant:v1.10.1"
  assert qdrant["container_name"] == "bpllm2-qdrant"
  assert qdrant["ports"] == ["${QDRANT_HTTP_PORT:-6343}:6333", "${QDRANT_GRPC_PORT:-6344}:6334"]


def test_gitignore_covers_secrets_venv_and_qdrant_data():
  lines = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
  for entry in (".env", "venv_bpllm2/", "data/qdrant_storage/"):
    assert entry in lines


def test_openai_client_is_a_core_dependency():
  # app/streamlit_app.py import thư viện openai, nên phải cài cùng `pip install -e .`
  deps = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["dependencies"]
  assert any(d.startswith("openai") for d in deps)


def test_pyarrow_works_with_installed_numpy():
  # st.dataframe cần pyarrow; bản pyarrow quá mới đòi NumPy 2 và làm hỏng màn Admin
  import pandas as pd
  import pyarrow as pa
  assert pa.Table.from_pandas(pd.DataFrame({"score": [0.5]})).num_rows == 1


def test_raw_data_present():
  raw = PROJECT_ROOT / "data" / "raw"
  for pid in ("food_delivery", "ecommerce", "reimbursement"):
    assert (raw / f"{pid}.bpmn").is_file() and (raw / "original" / f"{pid}.bpmn").is_file()
  assert (raw / "food_delivery_dfg_activities.txt").is_file()
  assert (raw / "food_delivery_dfg_flows.txt").is_file()
