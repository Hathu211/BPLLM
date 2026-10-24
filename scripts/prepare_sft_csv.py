import csv
import json
from pathlib import Path

def convert_csv_to_huggingface_sft():
    # 1. Đường dẫn tệp
    csv_path = Path("data/questions/3_questions_answers_refined.csv")
    output_json_path = Path("data/dataset/supervised_finetune_data.json")

    if not csv_path.exists():
        print(f"LỖI: Không tìm thấy tệp CSV tại {csv_path}")
        return

    # 2. Đọc tệp CSV gốc bằng thư viện chuẩn
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    # 3. Instruction Template chuẩn Refined Prompt theo bài báo (Hình 4 / Hình 6)
    INSTRUCTION_TEMPLATE = (
        "Use the following pieces of context to answer the question at the end. "
        "Answer 'yes' if true or 'no' if false. "
        "Also reference the corresponding piece of provided context if present."
    )

    hf_dataset = []

    # 4. Duyệt qua từng dòng và đóng gói chuẩn cấu trúc
    for row in rows:
        process_name = row.get("process", "Process Model")
        question = row.get("question", "")
        context = row.get("context", row.get("retrieved_chunks", ""))
        answer = str(row.get("expected_answer", row.get("answer", ""))).strip().lower()
        context_ref = row.get("context_reference", "")

        # Format trường input
        if context is None or str(context).strip() == "":
            input_text = f"Process: {process_name}\nQuestion: {question}"
        else:
            input_text = f"Process: {process_name}\nContext:\n{context}\n\nQuestion: {question}"

        # Format trường output nhị phân
        if answer == "yes":
            if context_ref is not None and str(context_ref).strip() != "":
                output_text = f"yes. Context reference: {context_ref}"
            else:
                output_text = f"yes. The statement is correct based on the {process_name} process model."
        else:
            output_text = "no."

        hf_dataset.append({
            "instruction": INSTRUCTION_TEMPLATE,
            "input": input_text,
            "output": output_text
        })

    # 5. Ghi tệp JSON chuẩn HuggingFace
    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(hf_dataset, f, indent=2, ensure_ascii=False)

    print(f"Đã tinh chỉnh thành công {len(hf_dataset)} mẫu dữ liệu!")
    print(f"Tệp đầu ra lưu tại: {output_json_path}")

if __name__ == "__main__":
    convert_csv_to_huggingface_sft()