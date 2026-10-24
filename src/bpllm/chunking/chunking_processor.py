import xml.etree.ElementTree as ET
from typing import List, Dict, Any
import os
import pandas as pd

TASK_TAGS = {'task', 'userTask', 'serviceTask', 'sendTask', 'receiveTask',
             'scriptTask', 'businessRuleTask', 'manualTask'}
GATEWAY_TAGS = {'exclusiveGateway', 'inclusiveGateway', 'parallelGateway',
                'eventBasedGateway', 'complexGateway'}
EVENT_TAGS = {'startEvent', 'endEvent', 'intermediateCatchEvent', 'intermediateThrowEvent'}
NODE_TAGS = TASK_TAGS | GATEWAY_TAGS | EVENT_TAGS

LABELS = {
    'task': 'Task', 'userTask': 'User task', 'serviceTask': 'Service task',
    'sendTask': 'Send task', 'receiveTask': 'Receive task', 'scriptTask': 'Script task',
    'businessRuleTask': 'Business rule task', 'manualTask': 'Manual task',
    'exclusiveGateway': 'Exclusive gateway (XOR decision)',
    'inclusiveGateway': 'Inclusive gateway (OR)',
    'parallelGateway': 'Parallel gateway (AND)',
    'eventBasedGateway': 'Event-based gateway',
    'complexGateway': 'Complex gateway',
    'startEvent': 'Start event', 'endEvent': 'End event',
    'intermediateCatchEvent': 'Intermediate catch event',
    'intermediateThrowEvent': 'Intermediate throw event',
}


def _strip(tag: str) -> str:
    return tag.split('}')[-1]


class EnrichedBPMNChunker:
    """
    Mỗi chunk = 1 node (task/gateway/event), viết bằng ngôn ngữ tự nhiên:
    - ID được thay bằng tên node (tra từ sequenceFlow)
    - Gắn ngữ cảnh: tên quy trình, lane, bước trước/sau, nhãn nhánh (Yes/No)
    - Thêm 1 chunk tổng quan cho cả quy trình
    Trả về List[Dict] gồm 'text' (đem đi embed) và 'metadata'.
    """

    def chunk(self, xml_content: str, file_name: str = "") -> List[Dict[str, Any]]:
        root = ET.fromstring(xml_content)

        # 1. Gom tất cả node và flow
        nodes: Dict[str, ET.Element] = {}
        flows: List[Dict[str, str]] = []
        lane_of: Dict[str, str] = {}
        process_name = ""

        for el in root.iter():
            tag = _strip(el.tag)
            if tag in NODE_TAGS:
                nodes[el.get('id')] = el
            elif tag == 'sequenceFlow':
                flows.append({'id': el.get('id'), 'name': el.get('name', ''),
                              'src': el.get('sourceRef'), 'tgt': el.get('targetRef')})
            elif tag == 'participant':
                process_name = el.get('name') or process_name
            elif tag == 'lane':
                lane_name = el.get('name') or el.get('id')
                for ref in el.iter():
                    if _strip(ref.tag) == 'flowNodeRef' and ref.text:
                        lane_of[ref.text.strip()] = lane_name

        def label(node_id: str) -> str:
            el = nodes.get(node_id)
            if el is None:
                return node_id
            name = el.get('name')
            kind = LABELS.get(_strip(el.tag), _strip(el.tag))
            return f"{kind} '{name}'" if name else f"{kind} (unnamed)"

        incoming: Dict[str, List[Dict]] = {k: [] for k in nodes}
        outgoing: Dict[str, List[Dict]] = {k: [] for k in nodes}
        for f in flows:
            if f['src'] in outgoing:
                outgoing[f['src']].append(f)
            if f['tgt'] in incoming:
                incoming[f['tgt']].append(f)

        # 2. Chunk tổng quan quy trình
        results: List[Dict[str, Any]] = []
        starts = [label(i) for i, e in nodes.items() if _strip(e.tag) == 'startEvent']
        ends = [label(i) for i, e in nodes.items() if _strip(e.tag) == 'endEvent']
        n_tasks = sum(1 for e in nodes.values() if _strip(e.tag) in TASK_TAGS)
        n_gw = sum(1 for e in nodes.values() if _strip(e.tag) in GATEWAY_TAGS)
        overview = (f"Process '{process_name or file_name}'. "
                    f"Starts with: {', '.join(starts) or 'n/a'}. "
                    f"Ends with: {', '.join(ends) or 'n/a'}. "
                    f"Contains {n_tasks} tasks and {n_gw} gateways.")
        results.append({'text': overview,
                        'metadata': {'file_name': file_name, 'node_type': 'process_overview',
                                     'node_id': None}})

        # 3. Chunk cho từng node
        for node_id, el in nodes.items():
            kind = _strip(el.tag)
            parts = [f"In process '{process_name or file_name}'"]
            if node_id in lane_of:
                parts[0] += f", lane '{lane_of[node_id]}'"
            parts[0] += f": {label(node_id)}."

            if incoming[node_id]:
                prev = '; '.join(label(f['src']) + (f" [condition: {f['name']}]" if f['name'] else '')
                                 for f in incoming[node_id])
                parts.append(f"Preceded by: {prev}.")
            if outgoing[node_id]:
                if kind in GATEWAY_TAGS and len(outgoing[node_id]) > 1:
                    nxt = '; '.join((f"if '{f['name']}' -> " if f['name'] else "-> ") + label(f['tgt'])
                                    for f in outgoing[node_id])
                    parts.append(f"Branches: {nxt}.")
                else:
                    nxt = '; '.join(label(f['tgt']) for f in outgoing[node_id])
                    parts.append(f"Followed by: {nxt}.")

            results.append({
                'text': ' '.join(parts),
                'metadata': {'file_name': file_name, 'node_type': kind, 'node_id': node_id,
                             'node_name': el.get('name', ''), 'lane': lane_of.get(node_id, '')},
            })
        return results
    
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
        bpmn_chunker = EnrichedBPMNChunker()

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

            # --- Áp dụng BPMN-Specific Chunking ---
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