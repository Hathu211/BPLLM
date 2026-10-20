import xml.etree.ElementTree as ET
from typing import List, Dict, Any
import re

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