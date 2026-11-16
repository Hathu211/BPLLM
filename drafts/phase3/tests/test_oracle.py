import json

import pytest

from bpllm.evaluation.oracle import evaluate_file, extract_answer, grade


@pytest.mark.parametrize("text, expected", [
    ("yes. The statement is correct based on the Food Delivery process model.", "yes"),
    ("no.", "no"),
    ("Yes, there is an activity named \"pay rider\".", "yes"),
    ("**No**, the context has no such flow.", "no"),
    ("The answer is no because nothing matches.", "no"),
    ("I do not know.", None),      # 'not' và 'know' không được tính là 'no'
    ("", None),
    (None, None),
])
def test_extract_answer(text, expected):
  assert extract_answer(text) == expected


def test_grade_counts_correct_wrong_and_unparsed():
  records = [
      {"id": 1, "expected": "yes", "answer": "yes."},
      {"id": 2, "expected": "yes", "answer": "no."},
      {"id": 3, "expected": "no", "answer": "No."},
      {"id": 4, "expected": "No", "answer": "I cannot tell."},
  ]
  report = grade(records)
  assert report["total"] == 4
  assert report["correct"] == 2
  assert report["accuracy"] == 0.5
  assert report["accuracy_yes"] == 0.5
  assert report["accuracy_no"] == 0.5
  assert report["wrong_ids"] == [2, 4]
  assert report["unparsed_ids"] == [4]


def test_grade_empty():
  assert grade([])["accuracy"] == 0.0


def test_evaluate_file(tmp_path, capsys):
  path = tmp_path / "answers.jsonl"
  rows = [{"id": 1, "expected": "yes", "answer": "yes."},
          {"id": 2, "expected": "no", "answer": "yes."}]
  path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
  report = evaluate_file(path)
  assert report["accuracy"] == 0.5
  assert "accuracy 50.00% (1/2)" in capsys.readouterr().out
