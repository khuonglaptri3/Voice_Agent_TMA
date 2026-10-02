#!/usr/bin/env bash
# ==============================================================================
# Script: scripts/start_server.sh
# Description: Khởi chạy Voice Agent FastAPI Server & Web Studio Interface.
#              Hỗ trợ tự động kiểm tra venv, file .env, port conflict và các cờ tùy biến.
# Usage:
#   ./scripts/start_server.sh                     # Chạy mặc định (0.0.0.0:8000, reload)
#   ./scripts/start_server.sh --port 8080         # Đổi port sang 8080
#   ./scripts/start_server.sh --host 127.0.0.1    # Chỉ lắng nghe localhost
#   ./scripts/start_server.sh --prod              # Chế độ production (tắt reload)
# ==============================================================================

set -euo pipefail

# Màu hiển thị console
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Xác định thư mục gốc của dự án
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Giá trị mặc định
HOST="0.0.0.0"
PORT="8000"
RELOAD=true
WORKERS=1

# Hiển thị hướng dẫn
show_help() {
    cat << EOF
Sử dụng: $(basename "$0") [TÙY CHỌN]

Khởi chạy FastAPI Voice Agent Server và giao diện Web Studio.

TÙY CHỌN:
  -p, --port PORT       Cổng chạy server (mặc định: 8000)
  -h, --host HOST       Địa chỉ IP lắng nghe (mặc định: 0.0.0.0)
      --prod, --no-reload
                        Chạy chế độ production, tắt auto-reload (mặc định: dev reload bật)
  -w, --workers NUM     Số lượng worker process (chỉ áp dụng khi tắt reload, mặc định: 1)
      --help            Hiển thị trợ giúp này và thoát

VÍ DỤ:
  ./scripts/start_server.sh
  ./scripts/start_server.sh -p 8088
  ./scripts/start_server.sh --host 127.0.0.1 --port 9000
  ./scripts/start_server.sh --prod --workers 2
EOF
    exit 0
}

# Phân tích tham số dòng lệnh
while [[ $# -gt 0 ]]; do
    case "$1" in
        -p|--port)
            PORT="$2"
            shift 2
            ;;
        -h|--host)
            HOST="$2"
            shift 2
            ;;
        --prod|--no-reload)
            RELOAD=false
            shift
            ;;
        -w|--workers)
            WORKERS="$2"
            RELOAD=false
            shift 2
            ;;
        --help)
            show_help
            ;;
        *)
            echo -e "${RED}[LỖI] Tham số không hợp lệ: $1${NC}"
            echo -e "Chạy ${YELLOW}./scripts/start_server.sh --help${NC} để xem hướng dẫn."
            exit 1
            ;;
    esac
done

echo -e "${BLUE}================================================================${NC}"
echo -e "${BLUE}    TMA ENTERPRISE VOICE AGENT - SPEECH-TO-SPEECH SERVER        ${NC}"
echo -e "${BLUE}================================================================${NC}"

# 1. Kiểm tra môi trường ảo Python
VENV_PYTHON="${PROJECT_ROOT}/.venv/bin/python"
if [ -f "$VENV_PYTHON" ]; then
    PYTHON_CMD="$VENV_PYTHON"
    echo -e "Python môi trường ảo: ${GREEN}${PYTHON_CMD}${NC}"
elif command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
    echo -e "${YELLOW}[CẢNH BÁO] Không tìm thấy .venv, sử dụng Python hệ thống: $(command -v python3)${NC}"
    echo -e "${YELLOW}           Khuyến nghị chạy ./scripts/setup_env.sh để thiết lập môi trường chuẩn.${NC}"
else
    echo -e "${RED}[LỖI] Không tìm thấy Python! Vui lòng cài đặt Python 3.10+ hoặc chạy scripts/setup_env.sh.${NC}"
    exit 1
fi

# 2. Kiểm tra file cấu hình .env
if [ ! -f "${PROJECT_ROOT}/.env" ]; then
    echo -e "${RED}[CẢNH BÁO] Không tìm thấy file .env tại thư mục gốc!${NC}"
    if [ -f "${PROJECT_ROOT}/.env.example" ]; then
        echo -e "${YELLOW}           Hãy sao chép file mẫu: cp .env.example .env và cấu hình GEMINI_API_KEY.${NC}"
    fi
else
    # Kiểm tra xem GEMINI_API_KEY có giá trị không
    if grep -q "^GEMINI_API_KEY=" "${PROJECT_ROOT}/.env"; then
        API_KEY_VAL=$(grep "^GEMINI_API_KEY=" "${PROJECT_ROOT}/.env" | cut -d '=' -f2- | tr -d ' "\r')
        if [ -z "$API_KEY_VAL" ] || [ "$API_KEY_VAL" = "your_gemini_api_key_here" ]; then
            echo -e "${YELLOW}[LƯU Ý] GEMINI_API_KEY trong file .env chưa được cấu hình!${NC}"
            echo -e "${YELLOW}        Live Session kết nối Gemini có thể sẽ thông báo lỗi thiếu API Key.${NC}"
        else
            echo -e "File cấu hình .env:   ${GREEN}Đã tìm thấy & có GEMINI_API_KEY${NC}"
        fi
    fi
fi

# 3. Kiểm tra xung đột cổng (Port conflict)
PORT_IN_USE=false
if command -v lsof &>/dev/null; then
    if lsof -Pi ":$PORT" -sTCP:LISTEN -t >/dev/null 2>&1; then
        PORT_IN_USE=true
        OCCUPIER_PID=$(lsof -Pi ":$PORT" -sTCP:LISTEN -t 2>/dev/null | head -n 1)
    fi
elif command -v ss &>/dev/null; then
    if ss -tulpn | grep -q ":$PORT "; then
        PORT_IN_USE=true
        OCCUPIER_PID="unknown"
    fi
fi

if [ "$PORT_IN_USE" = true ]; then
    echo -e "${RED}[LỖI] Cổng ${PORT} hiện đang được sử dụng (PID: ${OCCUPIER_PID:-không rõ})!${NC}"
    echo -e "${YELLOW}      Bạn có thể giải phóng cổng này hoặc chạy server trên cổng khác:${NC}"
    echo -e "${YELLOW}      ./scripts/start_server.sh --port 8080${NC}"
    exit 1
fi

# 4. Thiết lập PYTHONPATH
export PYTHONPATH="${PROJECT_ROOT}:${PYTHONPATH:-}"

# Lấy địa chỉ IP mạng nội bộ (nếu có)
LOCAL_IP=""
if command -v hostname &>/dev/null; then
    LOCAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "")
fi

# 5. Hiển thị thông tin truy cập
echo -e "\n${BOLD}Địa chỉ truy cập dịch vụ:${NC}"
echo -e "  🌐 Web Studio (Giao diện):  ${CYAN}http://localhost:${PORT}/web${NC}"
if [ -n "$LOCAL_IP" ] && [ "$HOST" = "0.0.0.0" ]; then
echo -e "  📱 Truy cập qua mạng LAN:    ${CYAN}http://${LOCAL_IP}:${PORT}/web${NC}"
fi
echo -e "  ⚡ WebSocket Live API:       ${CYAN}ws://localhost:${PORT}/ws/live${NC}"
echo -e "  📚 Tài liệu Swagger Docs:   ${CYAN}http://localhost:${PORT}/docs${NC}"
echo -e "  🩺 Kiểm tra sức khỏe:       ${CYAN}http://localhost:${PORT}/health${NC}"
echo -e "----------------------------------------------------------------"
if [ "$RELOAD" = true ]; then
echo -e "Chế độ: ${GREEN}Development (Auto-reload: BẬT)${NC}"
else
echo -e "Chế độ: ${GREEN}Production (Workers: ${WORKERS})${NC}"
fi
echo -e "Nhấn ${BOLD}Ctrl + C${NC} để dừng server.\n"

# 6. Khởi chạy Uvicorn server
UVICORN_ARGS=(
    "src.serving.main:app"
    "--host" "$HOST"
    "--port" "$PORT"
)

if [ "$RELOAD" = true ]; then
    UVICORN_ARGS+=("--reload")
else
    UVICORN_ARGS+=("--workers" "$WORKERS")
fi

exec "$PYTHON_CMD" -m uvicorn "${UVICORN_ARGS[@]}"
