import sys

def test_environment():
    print("==================================================")
    print(" BẮT ĐẦU KIỂM TRA TOÀN BỘ MÔI TRƯỜNG DỰ ÁN BPLLM")
    print("==================================================")
    
    # 1. Kiểm tra Import các thư viện cốt lõi
    try:
        from bpllm.config import get_settings
        import langchain
        import sentence_transformers
        from qdrant_client import QdrantClient
        print(" 1. Thư viện LangChain, SentenceTransformers, QdrantClient: ĐÃ CÀI ĐẶT!")
    except ImportError as e:
        print(f" 1. Lỗi thiếu thư viện: {e}")
        print('   Hãy chạy lại lệnh: pip install -e ".[dev]"')
        return False

    settings = get_settings()

    # 2. Kiểm tra kết nối gRPC tới Docker Qdrant
    try:
        client = QdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_http_port,
            grpc_port=settings.qdrant_grpc_port,
            prefer_grpc=settings.qdrant_prefer_grpc,
        )
        collections = client.get_collections()
        print(f" 2. Kết nối Docker Qdrant DB ({settings.qdrant_host}:{settings.qdrant_grpc_port}): THÀNH CÔNG!")
        print(f"   Danh sách Collections hiện có trong DB: {collections}")
    except Exception as e:
        print(f" 2. Lỗi kết nối Docker Qdrant DB: {e}")
        print("    Vui lòng đảm bảo Docker Desktop đang bật và đã chạy 'docker compose -f docker_compose.yml up -d'")
        return False

    # 3. Kiểm tra Mô hình nhúng Embedding
    try:
        from sentence_transformers import SentenceTransformer
        print(f" 3. Đang tải/kiểm tra mô hình nhúng '{settings.embedding_model}'...")
        embedder = SentenceTransformer(settings.embedding_model)
        vec = embedder.encode("Test BPMN process chunk")
        print(f" 3. Mô hình nhúng '{settings.embedding_model}': HOẠT ĐỘNG TỐT!")
        print(f"   Kích thước Vector chuyển đổi: {len(vec)} chiều")
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