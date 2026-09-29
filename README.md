# Enterprise Voice & Text Agent Architecture

Dự án triển khai kiến trúc hợp nhất cho Hệ thống Trí tuệ Nhân tạo Tác tử (Agentic AI) và Tác tử Thoại Thời gian thực (Real-time Voice Agent), tuân thủ nguyên lý Kiến trúc Sạch (Clean Architecture).

## Tài liệu nghiên cứu chi tiết
Toàn bộ nội dung báo cáo kiến trúc chuyên sâu được lưu trữ tại:
👉 [`docs/architecture_research.md`](docs/architecture_research.md)

## Cấu trúc thư mục dự án

```text
├── .github/workflows/    # CI/CD pipelines & Two-bot simulation tests
├── config/               # Cấu hình tập trung (Pydantic, YAML models, audio params)
├── data/                 # Knowledge base, indices (FAISS/BM25/Graph), storage (SQLite)
├── deploy/               # Dockerfiles (Voice, API), docker-compose, k8s
├── docs/                 # Toàn bộ tài liệu kiến trúc & nghiên cứu
├── src/                  # Mã nguồn chính theo Clean Architecture
│   ├── core/             # Domain Core: Thực thể và giao diện trừu tượng
│   ├── gateway/          # Tầng 1: WebRTC, DSP, AEC, Silero VAD, STT, Routing
│   ├── orchestration/    # Tầng 2: Turn Loop FSM, Dialog Planner, Reflection
│   ├── memory/           # Tầng 3: Bộ nhớ phân cấp 5 tầng (Working, Buffer, Episodic, Vector, Context)
│   ├── knowledge/        # Tầng 4: Advanced Hybrid RAG (FAISS+BM25+RRF), Cross-Encoder, GraphRAG
│   ├── tools/            # Tầng 5: Streaming Action Markers, Anthropic MCP, Sandboxed Execution
│   ├── guardrails/       # Tầng 6: ASR Hallucination Filter, Grace Guard, Strict Unicode Guard
│   ├── observability/    # Tầng 7: Circular Ring Buffer, OpenTelemetry, Token Accounting
│   └── serving/          # FastAPI REST/SSE endpoints & WebRTC realtime worker
├── scripts/              # Kịch bản nạp tri thức, sync graph, chạy benchmark
└── tests/                # Unit tests, integration tests, E2E voice & barge-in tests
```

## Khởi động nhanh

1. Sao chép biến môi trường:
   ```bash
   cp .env.example .env
   ```
2. Cài đặt các gói phụ thuộc:
   ```bash
   pip install -e ".[dev]"
   ```
3. Chạy máy chủ kiểm thử:
   ```bash
   python src/serving/main.py
   ```
