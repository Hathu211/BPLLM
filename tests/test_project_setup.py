"""Giữ cho các lỗi của Phase 0 không quay lại."""
import tomllib

import yaml

from bpllm.config import PROJECT_ROOT

SUBPACKAGES = ["chunking", "embeddings", "evaluation", "llm", "parsing", "rag", "vectorstore"]


def test_every_package_has_init():
  package_root = PROJECT_ROOT / "src" / "bpllm"
  assert (package_root / "__init__.py").is_file()
  for name in SUBPACKAGES:
    assert (package_root / name / "__init__.py").is_file(), name


def test_entry_points_do_not_hack_imports():
  files = list((PROJECT_ROOT / "scripts").glob("*.py"))
  files += list((PROJECT_ROOT / "app").glob("*.py"))
  assert files
  for path in files:
    text = path.read_text(encoding="utf-8")
    assert "sys.path" not in text, path.name
    assert "src.bpllm" not in text, path.name


def test_compose_is_pinned_and_has_no_version_key():
  compose = yaml.safe_load(
      (PROJECT_ROOT / "docker_compose.yml").read_text(encoding="utf-8")
  )
  assert "version" not in compose
  assert compose["services"]["qdrant"]["image"] == "qdrant/qdrant:v1.10.1"


def test_gitignore_covers_qdrant_data():
  lines = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
  assert "data/qdrant_storage/" in lines
  assert "data/qdrant_local/" in lines


def test_pytest_testpaths_exist():
  config = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
  for path in config["tool"]["pytest"]["ini_options"]["testpaths"]:
    assert (PROJECT_ROOT / path).is_dir(), path


def test_raw_data_file_names():
  raw = PROJECT_ROOT / "data" / "raw"
  assert (raw / "food_delivery_dfg_activities.txt").is_file()
  assert (raw / "food_delivery_dfg_flows.txt").is_file()
  assert not [p.name for p in raw.iterdir() if "(1)" in p.name]
