import sys

def test_environment():
    print("==================================================")
    print(" BẮT ĐẦU KIỂM TRA TOÀN BỘ MÔI TRƯỜNG DỰ ÁN BPLLM")
    print("==================================================")
    
    # 1. Kiểm tra Import các thư viện cốt lõi
    try:
        import langchain
        import sentence_transformers
        from qdrant_client import QdrantClient
        print(" 1. Thư viện LangChain, SentenceTransformers, QdrantClient: ĐÃ CÀI ĐẶT!")
    except ImportError as e:
        print(f" 1. Lỗi thiếu thư viện: {e}")
        print("   Hãy chạy lại lệnh: pip install -e .")
        return False

    # 2. Kiểm tra kết nối gRPC tới Docker Qdrant (Cổng 6334)
    try:
        client = QdrantClient(host="localhost", grpc_port=6334, prefer_grpc=True)
        collections = client.get_collections()
        print(" 2. Kết nối gRPC Docker Qdrant DB (Cổng 6334): THÀNH CÔNG!")
        print(f"   Danh sách Collections hiện có trong DB: {collections}")
    except Exception as e:
        print(f" 2. Lỗi kết nối Docker Qdrant DB: {e}")
        print("    Vui lòng đảm bảo Docker Desktop đang bật và đã chạy 'docker-compose up -d'")
        return False

    # 3. Kiểm tra Mô hình nhúng Embedding (all-MiniLM-L6-v2)
    try:
        from sentence_transformers import SentenceTransformer
        print(" 3. Đang tải/kiểm tra mô hình nhúng 'all-MiniLM-L6-v2'...")
        embedder = SentenceTransformer("all-MiniLM-L6-v2")
        vec = embedder.encode("Test BPMN process chunk")
        print(f" 3. Mô hình nhúng 'all-MiniLM-L6-v2': HOẠT ĐỘNG TỐT!")
        print(f"   Kích thước Vector chuyển đổi: {len(vec)} chiều (Chuẩn 384)")
    except Exception as e:
        print(f"3. Lỗi mô hình nhúng: {e}")
        return False

    print("==================================================")
    print("TẤT CẢ MÔI TRƯỜNG VÀ HẠ TẦNG ĐÃ SẴN SÀNG 100%!")
    print("==================================================")
    return True

if __name__ == "__main__":
    success = test_environment()
    sys.exit(0 if success else 1)