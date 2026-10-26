import os
import json
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(BASE_DIR, "data", "questions", "3_questions_answers_refined.csv")
GT_DIR = os.path.join(BASE_DIR, "data", "ground_truth")
OUTPUT_PATH = os.path.join(BASE_DIR, "data", "dataset", "supervised_finetune_data.json")

def load_ground_truths():
    contexts = {}
    mapping = {
        "E-commerce": "ecommerce.json",
        "Food Delivery": "food_delivery.json",
        "Reimbursement": "reimbursement.json"
    }
    for proc_name, file_name in mapping.items():
        file_path = os.path.join(GT_DIR, file_name)
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                contexts[proc_name] = json.load(f)
    return contexts

def build_dataset():
    contexts = load_ground_truths()
    
    if not os.path.exists(CSV_PATH):
        raise FileNotFoundError(f"Không tìm thấy CSV tại {CSV_PATH}")
        
    df = pd.read_csv(CSV_PATH)
    
    instruction = (
        "Use the following pieces of context to answer the question at the end. "
        "Answer 'yes' if true or 'no' if false. Also reference the corresponding piece of provided context if present."
    )
    
    samples = []
    
    question_col = "3_question" if "3_question" in df.columns else ("question" if "question" in df.columns else df.columns[0])
    answer_col = "expected_answer" if "expected_answer" in df.columns else ("answer" if "answer" in df.columns else df.columns[-1])
    process_col = "process_name" if "process_name" in df.columns else ("process" if "process" in df.columns else None)

    for _, row in df.iterrows():
        question = str(row[question_col]).strip()
        process_name = str(row[process_col]).strip() if process_col and pd.notna(row[process_col]) else "Food Delivery"
        answer = str(row.get(answer_col, "yes")).strip().lower()
        
        # Đảm bảo câu hỏi có đuôi yêu cầu reference ngữ cảnh
        if not question.endswith("Also reference the corresponding piece of provided context if present."):
            question = f"{question} Also reference the corresponding piece of provided context if present."
        
        # Lấy full context JSON của quy trình (không chunking)
        proc_data = contexts.get(process_name, {})
        context_str = json.dumps(proc_data, ensure_ascii=False, indent=2) if proc_data else ""
        
        input_text = f"Process: {process_name}\nContext BPMN:\n{context_str}\n\nQuestion: {question}"
        
        # Định dạng output chuẩn đúng như mẫu yêu cầu
        if answer.startswith("yes"):
            output_text = f"yes. The statement is correct based on the {process_name} process model."
        else:
            output_text = "no."
            
        samples.append({
            "instruction": instruction,
            "input": input_text,
            "output": output_text
        })
        
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(samples, f, indent=2, ensure_ascii=False)
        
    print(f" Đã tạo thành công {len(samples)} mẫu Fine-Tuning tại '{OUTPUT_PATH}'!")

if __name__ == "__main__":
    build_dataset()