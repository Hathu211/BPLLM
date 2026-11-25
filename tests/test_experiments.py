"""Cấu hình thực nghiệm khớp dữ liệu, notebook Kaggle khớp code trong src/."""
import csv
import json
import re

import pytest

from bpllm.config import PROJECT_ROOT
from bpllm.evaluation import oracle
from bpllm.experiments import (APP_MODEL_GROUP, EXPERIMENTS, MODEL_GROUPS, answers_name, app_model,
                               rag_input_path)
from bpllm.parsing import PROCESS_NAMES

NOTEBOOKS = PROJECT_ROOT / "notebooks"


def rows(experiment):
  with open(experiment.questions_path, encoding="utf-8-sig", newline="") as f:
    return list(csv.DictReader(f))


@pytest.mark.parametrize("name", list(EXPERIMENTS))
def test_question_file_has_expected_size_and_balanced_labels(name):
  data = rows(EXPERIMENTS[name])
  assert len(data) == EXPERIMENTS[name].expected_count
  labels = [r["answer"].strip().lower() for r in data]
  assert set(labels) == {"yes", "no"}
  assert labels.count("yes") == labels.count("no")


def test_six_models_three_groups_two_quants():
  ids = [m for g in MODEL_GROUPS.values() for m in g.models.values()]
  assert len(set(ids)) == 6 and all(i.startswith("angeloc1/llama3dot1") for i in ids)


def test_every_process_has_an_app_model_trained_on_it():
  assert set(APP_MODEL_GROUP) == set(PROCESS_NAMES)
  for pid, group in APP_MODEL_GROUP.items():
    assert pid in MODEL_GROUPS[group].processes
  assert app_model("ecommerce", "int4") == "angeloc1/llama3dot1SimilarProcesses4"


def test_multi_process_experiments_search_two_processes():
  assert EXPERIMENTS["similar"].processes == ("food_delivery", "ecommerce")
  assert EXPERIMENTS["different"].processes == ("food_delivery", "reimbursement")


def test_file_names():
  assert rag_input_path("fd_ft", "enriched").name == "fd_ft_enriched_top10.jsonl"
  assert answers_name("similar", "specific", "int8") == "answers_similar_specific_int8.jsonl"


# ---------- notebook ----------
def code_cells(name):
  nb = json.loads((NOTEBOOKS / name).read_text(encoding="utf-8"))
  assert nb["nbformat"] == 4
  assert all(c.get("id") for c in nb["cells"])
  return ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"]


def run_cell(source, namespace=None):
  namespace = {} if namespace is None else namespace
  exec(compile(source, "<cell>", "exec"), namespace)
  return namespace


@pytest.mark.parametrize("name", ["bpllm_experiment_kaggle.ipynb", "bpllm_server_kaggle.ipynb"])
def test_notebook_models_match_src(name):
  config = next(c for c in code_cells(name) if c.lstrip().startswith(("EXPERIMENT =", "QUANT =")))
  block = re.search(r"^MODELS = \{.*?^\}", config, re.MULTILINE | re.DOTALL).group(0)
  models = run_cell(block)["MODELS"]
  assert models == {g: dict(m.models) for g, m in MODEL_GROUPS.items()}


def test_experiment_notebook_config_matches_src():
  config = code_cells("bpllm_experiment_kaggle.ipynb")[0]
  block = re.search(r"^EXPERIMENTS = \{.*?^\}", config, re.MULTILINE | re.DOTALL).group(0)
  assert run_cell(block)["EXPERIMENTS"] == {
      e.name: {"model_group": e.model_group, "count": e.expected_count} for e in EXPERIMENTS.values()}


def test_experiment_notebook_sends_the_stored_prompt_and_names_files_like_src():
  source = "\n".join(code_cells("bpllm_experiment_kaggle.ipynb"))
  assert 'ask(record["prompt"])' in source
  assert 'f"{EXPERIMENT}_{c}_top{TOP_K}.jsonl"' in source
  assert 'answers_{EXPERIMENT}_{chunking}_{QUANT}.jsonl' in source


@pytest.mark.parametrize("text", ["yes.", "No, never", "I do not know", None, "Answer: YES"])
def test_notebook_oracle_behaves_like_src(text):
  cell = next(c for c in code_cells("bpllm_experiment_kaggle.ipynb") if "def grade(" in c)
  ns = run_cell(cell)
  assert ns["extract_answer"](text) == oracle.extract_answer(text)
  records = [{"id": 1, "expected": "yes", "answer": text}, {"id": 2, "expected": "no", "answer": text}]
  assert ns["grade"](records) == oracle.grade(records)


@pytest.mark.parametrize("name", ["bpllm_experiment_kaggle.ipynb", "bpllm_server_kaggle.ipynb"])
def test_notebooks_do_not_downgrade_kaggle_libraries(name):
  # Ghim transformers<5 từng kéo huggingface-hub của Kaggle từ 1.x xuống 0.36
  source = "\n".join(code_cells(name))
  assert "<5" not in source and "!pip" not in source
  assert 'snapshot_download(model_id, local_dir=target' in source
  assert 'allow_patterns=["*.json", "*.safetensors"]' in source


def test_server_notebook_speaks_openai_protocol():
  source = "\n".join(code_cells("bpllm_server_kaggle.ipynb"))
  for needle in ('@app.get("/v1/models")', '@app.post("/v1/chat/completions")', "Bearer {API_KEY}",
                 "load_in_4bit=True", "trycloudflare"):
    assert needle in source


def test_server_notebook_tunnel_is_verified_before_printing_url():
  # Bản cũ in "LLM_BASE_URL=None/v1" khi cloudflared thoát mà không có link
  source = "\n".join(code_cells("bpllm_server_kaggle.ipynb"))
  assert '"--protocol", "http2"' in source          # Kaggle hay chặn QUIC/UDP
  assert "if PUBLIC_URL is None:" in source and "raise RuntimeError" in source
  assert source.index("public_ok(url)") < source.index('print(f"LLM_BASE_URL={PUBLIC_URL}/v1")')
  assert "NGROK_AUTHTOKEN" in source
