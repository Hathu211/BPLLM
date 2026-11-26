"""Cấu hình thực nghiệm: 6 model fine-tune của bài báo và các bộ câu hỏi tương ứng (Bảng 4).

Ba nhóm model, mỗi nhóm có bản int4 và int8. "int4/int8" là cách tác giả fine-tune (PEFT có
lượng tử hóa); trọng số trên Hugging Face đều là F16, khoảng 16 GB mỗi model.

| Nhóm        | Quy trình trong kho              | Bộ câu hỏi                                  |
| food_delivery | Food Delivery                  | 3 (refined, 104 câu), 6 (refined_ft, 104 câu) |
| similar     | Food Delivery + E-commerce       | 5 (similar processes, 190 câu)               |
| different   | Food Delivery + Reimbursement    | 4 (different processes, 182 câu)             |
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple

from bpllm.config import QUANTS, QUESTIONS_DIR, RAG_INPUTS_DIR, RESULTS_DIR


@dataclass(frozen=True)
class ModelGroup:
  name: str
  label: str
  processes: Tuple[str, ...]      # các quy trình model đã được fine-tune
  models: Dict[str, str]          # quant -> id Hugging Face

  def model(self, quant: str) -> str:
    if quant not in QUANTS:
      raise ValueError(f"quant phải là một trong {QUANTS}, nhận được '{quant}'")
    return self.models[quant]


MODEL_GROUPS: Dict[str, ModelGroup] = {
    "food_delivery": ModelGroup(
        "food_delivery", "Food Delivery", ("food_delivery",),
        {"int4": "angeloc1/llama3dot1FoodDel4v05", "int8": "angeloc1/llama3dot1FoodDel8v02"}),
    "similar": ModelGroup(
        "similar", "Food Delivery + E-commerce (similar processes)", ("food_delivery", "ecommerce"),
        {"int4": "angeloc1/llama3dot1SimilarProcesses4", "int8": "angeloc1/llama3dot1SimilarProcesses8"}),
    "different": ModelGroup(
        "different", "Food Delivery + Reimbursement (different processes)",
        ("food_delivery", "reimbursement"),
        {"int4": "angeloc1/llama3dot1DifferentProcesses4",
         "int8": "angeloc1/llama3dot1DifferentProcesses8"}),
}

# Streamlit: hỏi về quy trình nào thì gọi nhóm model nào.
# Food Delivery có model riêng; E-commerce và Reimbursement chỉ có trong model 2 quy trình.
APP_MODEL_GROUP: Dict[str, str] = {
    "food_delivery": "food_delivery",
    "ecommerce": "similar",
    "reimbursement": "different",
}


def app_model(process_id: str, quant: str) -> str:
  """Id model Streamlit gọi cho một quy trình."""
  return MODEL_GROUPS[APP_MODEL_GROUP[process_id]].model(quant)


@dataclass(frozen=True)
class Experiment:
  name: str
  questions_file: str
  model_group: str
  expected_count: int
  description: str

  @property
  def questions_path(self) -> Path:
    return QUESTIONS_DIR / self.questions_file

  @property
  def processes(self) -> Tuple[str, ...]:
    """Kho truy xuất gồm đúng các quy trình của nhóm model (như Bảng 4 bài báo)."""
    return MODEL_GROUPS[self.model_group].processes


EXPERIMENTS: Dict[str, Experiment] = {
    "fd_refined": Experiment("fd_refined", "3_questions_answers_refined.csv", "food_delivery", 104,
                             "Food Delivery, bộ câu hỏi 3 (refined)"),
    "fd_ft": Experiment("fd_ft", "6_questions_answers_refined_ft.csv", "food_delivery", 104,
                        "Food Delivery, bộ câu hỏi 6 (refined_ft)"),
    "similar": Experiment("similar", "5_questions_answers_similar_processes.csv", "similar", 190,
                          "Food Delivery + E-commerce, bộ câu hỏi 5"),
    "different": Experiment("different", "4_questions_answers_different_processes.csv", "different",
                            182, "Food Delivery + Reimbursement, bộ câu hỏi 4"),
}


def rag_input_path(experiment: str, chunking: str, top_k: int = 10) -> Path:
  """File top-k do scripts/retrieve_top_k.py sinh, là input của notebook thực nghiệm."""
  return RAG_INPUTS_DIR / f"{experiment}_{chunking}_top{top_k}.jsonl"


def answers_name(experiment: str, chunking: str, quant: str) -> str:
  """Tên file câu trả lời notebook thực nghiệm ghi ra (đặt vào data/results/)."""
  return f"answers_{experiment}_{chunking}_{quant}.jsonl"


def answers_path(experiment: str, chunking: str, quant: str) -> Path:
  return RESULTS_DIR / answers_name(experiment, chunking, quant)
