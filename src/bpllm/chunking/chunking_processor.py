import xml.etree.ElementTree as ET
from typing import List, Dict, Any
import re
import os
import pandas as pd

class BPMNSpecificChunker:
    """
    Chunker dành riêng cho tệp BPMN (XML format).
    Phân tách theo ngữ nghĩa của từng thẻ (Flow Objects & Connecting Objects)
    và loại bỏ các thông tin đồ họa (BPMN Diagram elements).
    """
    def __init__(self):
        # Các thẻ BPMN ngữ nghĩa phổ biến cần tách chunk
        self.semantic_tags = {
            'task', 'userTask', 'serviceTask', 'sendTask', 'receiveTask', 
            'scriptTask', 'businessRuleTask', 'manualTask',
            'exclusiveGateway', 'inclusiveGateway', 'parallelGateway', 
            'eventBasedGateway', 'complexGateway',
            'startEvent', 'endEvent', 'intermediateCatchEvent', 'intermediateThrowEvent',
            'sequenceFlow'
        }

    def chunk(self, xml_content: str) -> List[str]:
        chunks = []
        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError as e:
            raise ValueError(f"Lỗi định dạng XML/BPMN: {e}")

        # Lấy namespace nếu có
        namespace = ""
        if root.tag.startswith("{"):
            namespace = root.tag.split("}")[0] + "}"

        # Duyệt qua các phần tử trong XML
        for elem in root.iter():
            # Lấy tên thẻ không kèm namespace
            tag_name = elem.tag.replace(namespace, "")
            
            # Chỉ bóc tách các thẻ nằm trong danh sách ngữ nghĩa
            if tag_name in self.semantic_tags:
                chunk_str = self._element_to_clean_string(elem, namespace)
                if chunk_str:
                    chunks.append(chunk_str)

        return chunks

    def _element_to_clean_string(self, elem: ET.Element, namespace: str) -> str:
        """
        Chuyển đổi ElementTree node thành chuỗi XML sạch (loại bỏ thông tin thừa).
        """
        clean_elem = ET.Element(elem.tag.replace(namespace, ""))
        
        # Sao chép các thuộc tính quan trọng (id, name, sourceRef, targetRef, ...)
        for k, v in elem.attrib.items():
            attr_name = k.replace(namespace, "")
            clean_elem.attrib[attr_name] = v

        # Sao chép các thẻ con ngữ nghĩa (incoming, outgoing)
        for child in elem:
            child_tag = child.tag.replace(namespace, "")
            if child_tag in ['incoming', 'outgoing']:
                sub_elem = ET.SubElement(clean_elem, child_tag)
                sub_elem.text = child.text

        # Format lại dạng chuỗi XML
        raw_xml = ET.tostring(clean_elem, encoding='unicode')
        # Loại bỏ các khoảng trắng thừa
        clean_xml = re.sub(r'>\s+<', '><', raw_xml).strip()
        return clean_xml


class FixedSizeChunker:
    """
    Chunker kích thước cố định (dùng làm phương pháp đối chứng).
    """
    def __init__(self, chunk_size: int = 128, chunk_overlap: int = 10):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(self, text: str) -> List[str]:
        words = text.split()
        if not words:
            return []
        
        chunks = []
        i = 0
        step = max(1, self.chunk_size - self.chunk_overlap)
        
        while i < len(words):
            chunk_words = words[i:i + self.chunk_size]
            chunks.append(" ".join(chunk_words))
            i += step
            
        return chunks


class RecursiveChunker:
    """
    Chunker phân cấp đệ quy dựa trên ký tự phân tách (dùng làm phương pháp đối chứng).
    """
    def __init__(self, chunk_size: int = 128, separators: List[str] = None):
        self.chunk_size = chunk_size
        self.separators = separators or ["\n\n", "\n", " ", ""]

    def chunk(self, text: str) -> List[str]:
        return self._split_text(text, self.separators)

    def _split_text(self, text: str, separators: List[str]) -> List[str]:
        final_chunks = []
        if not text:
            return final_chunks

        # Lấy separator hiện tại
        separator = separators[-1]
        new_separators = []
        for i, _s in enumerate(separators):
            if _s == "":
                separator = ""
                break
            if re.search(re.escape(_s), text):
                separator = _s
                new_separators = separators[i + 1:]
                break

        # Tách text theo separator
        splits = text.split(separator) if separator != "" else list(text)

        # Gom nhóm các phần tách nhỏ sao cho không vượt quá chunk_size (tính theo từ/ký tự)
        good_splits = []
        for s in splits:
            if len(s.split()) <= self.chunk_size:
                good_splits.append(s)
            else:
                if good_splits:
                    final_chunks.append(separator.join(good_splits))
                    good_splits = []
                if new_separators:
                    final_chunks.extend(self._split_text(s, new_separators))
                else:
                    final_chunks.append(s)
        
        if good_splits:
            final_chunks.append(separator.join(good_splits))

        return [c.strip() for c in final_chunks if c.strip()]
    
if __name__ == "__main__":
    inputs = "./data/raw"  
    output_dir = "./data/processed"
    os.makedirs(output_dir, exist_ok=True)
    
    # 2. Lấy danh sách các file .bpmn và .xml trong thư mục
    valid_extensions = ('.bpmn', '.xml')
    bpmn_files = [
        f for f in os.listdir(inputs) 
        if f.endswith(valid_extensions) and os.path.isfile(os.path.join(inputs, f))
    ]
    
    if not bpmn_files:
        print(f"Không tìm thấy file BPMN/XML nào trong thư mục: {inputs}")
    else:
        # 3. Khởi tạo các bộ chunker
        bpmn_chunker = BPMNSpecificChunker()
        fixed_chunker = FixedSizeChunker(chunk_size=32, chunk_overlap=10)     # Thông số đề xuất cho BPMN
        recursive_chunker = RecursiveChunker(chunk_size=32)                    # Thông số đề xuất cho BPMN[cite: 39]

        all_results = []

        # 4. Duyệt qua từng file và thực hiện chunking
        for name in bpmn_files:
            full_path = os.path.join(inputs, name) 
            print(f"\n==========================================")
            print(f"Đang xử lý file: {full_path}")
            print(f"==========================================")
            
            # Đọc nội dung file BPMN
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    xml_content = f.read()
            except Exception as e:
                print(f"Lỗi khi đọc file {name}: {e}")
                continue

            # --- A. Áp dụng BPMN-Specific Chunking ---
            try:
                bpmn_chunks = bpmn_chunker.chunk(xml_content)
                print(f"[1] BPMN-Specific Chunker: Tạo ra {len(bpmn_chunks)} chunks.")
                for idx, chunk in enumerate(bpmn_chunks, 1):
                    all_results.append({
                        "file_name": name,
                        "strategy": "BPMN-specific",
                        "chunk_id": idx,
                        "content": chunk
                    })
            except Exception as e:
                print(f"Lỗi BPMN-Specific Chunking trên file {name}: {e}")

            # --- B. Áp dụng Fixed-Size Chunking (Đối chứng) ---
            fixed_chunks = fixed_chunker.chunk(xml_content)
            print(f"[2] Fixed-Size Chunker:     Tạo ra {len(fixed_chunks)} chunks.")
            for idx, chunk in enumerate(fixed_chunks, 1):
                all_results.append({
                    "file_name": name,
                    "strategy": "Fixed-size",
                    "chunk_id": idx,
                    "content": chunk
                })

            # --- C. Áp dụng Recursive Chunking (Đối chứng) ---
            recursive_chunks = recursive_chunker.chunk(xml_content)
            print(f"[3] Recursive Chunker:      Tạo ra {len(recursive_chunks)} chunks.")
            for idx, chunk in enumerate(recursive_chunks, 1):
                all_results.append({
                    "file_name": name,
                    "strategy": "Recursive",
                    "chunk_id": idx,
                    "content": chunk
                })

        # 5. Lưu kết quả ra file CSV để kiểm tra hoặc nạp vào Vector DB
        if all_results:
            df = pd.DataFrame(all_results)
            output_csv = os.path.join(output_dir, "bpmn_chunks_summary.csv")
            df.to_csv(output_csv, index=False, encoding='utf-8-sig')
            print(f"\n---> Đã xuất toàn bộ kết quả chunking ra file: {output_csv}")
            
            # In thử 3 chunk mẫu của phương pháp BPMN-Specific
            print("\n--- MẪU KẾT QUẢ (BPMN-Specific) ---")
            sample_df = df[df["strategy"] == "BPMN-specific"].head(3)
            for _, row in sample_df.iterrows():
                print(f"\n[File: {row['file_name']} | Chunk {row['chunk_id']}]:\n{row['content']}")