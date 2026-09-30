#!/usr/bin/env bash
# ==============================================================================
# Script: scripts/setup_env.sh
# Description: Tự động thiết lập môi trường ảo Python và cài đặt dependencies
#              cho dự án Voice_Agent_TMA (Dành cho Dev A, Dev B và máy bên cạnh).
# ==============================================================================

set -euo pipefail

# Màu hiển thị console
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo -e "${BLUE}======================================================${NC}"
echo -e "${BLUE}  VOICE AGENT TMA - THIẾT LẬP MÔI TRƯỜNG TỰ ĐỘNG     ${NC}"
echo -e "${BLUE}======================================================${NC}"
echo -e "Thư mục dự án: ${GREEN}${PROJECT_ROOT}${NC}"

# 1. Kiểm tra Python
echo -e "\n${YELLOW}[1/5] Kiểm tra phiên bản Python...${NC}"
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
    PYTHON_CMD="python"
else
    echo -e "${RED}[LỖI] Không tìm thấy Python 3 trên hệ thống! Vui lòng cài đặt Python >= 3.10.${NC}"
    exit 1
fi

PY_VERSION=$($PYTHON_CMD -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo -e "Tìm thấy Python phiên bản: ${GREEN}${PY_VERSION}${NC}"

PY_MAJOR=$($PYTHON_CMD -c 'import sys; print(sys.version_info.major)')
PY_MINOR=$($PYTHON_CMD -c 'import sys; print(sys.version_info.minor)')

if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]); then
    echo -e "${RED}[LỖI] Yêu cầu tối thiểu Python 3.10, phiên bản hiện tại là ${PY_VERSION}!${NC}"
    exit 1
fi

# 2. Kiểm tra thư viện âm thanh OS (PortAudio / ALSA)
echo -e "\n${YELLOW}[2/5] Kiểm tra thư viện âm thanh hệ thống (PortAudio / ALSA)...${NC}"
if ldconfig -p 2>/dev/null | grep -q "libportaudio"; then
    echo -e "Thư viện PortAudio: ${GREEN}Đã cài đặt${NC}"
else
    echo -e "${YELLOW}[CẢNH BÁO] Có thể thiếu libportaudio. Nếu gặp lỗi khi dùng sounddevice, hãy chạy:${NC}"
    echo -e "${YELLOW}  sudo apt-get update && sudo apt-get install -y portaudio19-dev libasound2-dev${NC}"
fi

# 3. Tạo môi trường ảo .venv
echo -e "\n${YELLOW}[3/5] Khởi tạo môi trường ảo .venv...${NC}"
VENV_DIR="${PROJECT_ROOT}/.venv"
if [ ! -d "$VENV_DIR" ]; then
    echo -e "Đang tạo môi trường ảo tại ${VENV_DIR}..."
    $PYTHON_CMD -m venv "$VENV_DIR"
    echo -e "${GREEN}Môi trường ảo đã được tạo thành công!${NC}"
else
    echo -e "Môi trường ảo đã tồn tại tại: ${GREEN}${VENV_DIR}${NC}"
fi

VENV_PYTHON="${VENV_DIR}/bin/python"
VENV_PIP="${VENV_DIR}/bin/pip"

# 4. Nâng cấp pip và cài đặt dependencies
echo -e "\n${YELLOW}[4/5] Cập nhật pip và cài đặt dependencies từ pyproject.toml...${NC}"
"$VENV_PIP" install --upgrade pip setuptools wheel

echo -e "Đang cài đặt các thư viện dự án (chế độ editable)..."
"$VENV_PIP" install -e ".[dev]"

# Đảm bảo sounddevice tìm thấy libportaudio nếu được cài qua conda
PORTAUDIO_DIR=""
if [ -f "${HOME}/anaconda3/lib/libportaudio.so" ]; then
    PORTAUDIO_DIR="${HOME}/anaconda3/lib"
elif command -v conda &>/dev/null; then
    CONDA_BASE=$(conda info --base 2>/dev/null || true)
    if [ -n "$CONDA_BASE" ] && [ -f "$CONDA_BASE/lib/libportaudio.so" ]; then
        PORTAUDIO_DIR="$CONDA_BASE/lib"
    fi
fi

if [ -n "$PORTAUDIO_DIR" ]; then
    if ! grep -q "LD_LIBRARY_PATH.*$PORTAUDIO_DIR" "$VENV_DIR/bin/activate"; then
        echo -e "\n# Tự động nạp libportaudio cho sounddevice" >> "$VENV_DIR/bin/activate"
        echo "export LD_LIBRARY_PATH=\"$PORTAUDIO_DIR:\${LD_LIBRARY_PATH:-}\"" >> "$VENV_DIR/bin/activate"
    fi
    export LD_LIBRARY_PATH="$PORTAUDIO_DIR:${LD_LIBRARY_PATH:-}"
    # Tự động nạp qua .pth trong site-packages để không phụ thuộc vào lệnh source
    SITE_PACKAGES=$("$VENV_PYTHON" -c "import site; print(site.getsitepackages()[0])" 2>/dev/null || echo "")
    if [ -n "$SITE_PACKAGES" ] && [ -d "$SITE_PACKAGES" ]; then
        echo "import os; p = '${PORTAUDIO_DIR}'; os.environ['LD_LIBRARY_PATH'] = f\"{p}:{os.environ.get('LD_LIBRARY_PATH', '')}\" if os.path.isdir(p) else os.environ.get('LD_LIBRARY_PATH', '')" > "${SITE_PACKAGES}/portaudio_path.pth"
    fi
fi

# Tự động nạp CA cert hệ thống để tránh lỗi SSL trong mạng TMA
if [ -f "/etc/ssl/certs/ca-certificates.crt" ]; then
    if ! grep -q "SSL_CERT_FILE" "$VENV_DIR/bin/activate"; then
        echo -e "\n# Tự động cấu hình CA bundle cho mạng nội bộ" >> "$VENV_DIR/bin/activate"
        echo "export SSL_CERT_FILE=\"/etc/ssl/certs/ca-certificates.crt\"" >> "$VENV_DIR/bin/activate"
    fi
    export SSL_CERT_FILE="/etc/ssl/certs/ca-certificates.crt"
fi

# 5. Cấu hình file .env
echo -e "\n${YELLOW}[5/5] Kiểm tra file cấu hình .env...${NC}"
if [ ! -f "${PROJECT_ROOT}/.env" ]; then
    if [ -f "${PROJECT_ROOT}/.env.example" ]; then
        cp "${PROJECT_ROOT}/.env.example" "${PROJECT_ROOT}/.env"
        echo -e "${GREEN}Đã tạo file .env từ .env.example!${NC}"
        echo -e "${YELLOW}LƯU Ý: Hãy điền GOOGLE_API_KEY hợp lệ vào file .env.${NC}"
    else
        echo -e "${YELLOW}Không tìm thấy .env.example để sao chép.${NC}"
    fi
else
    echo -e "File .env đã tồn tại: ${GREEN}OK${NC}"
fi

# 6. Kiểm tra tính toàn vẹn (Smoke Test)
echo -e "\n${BLUE}======================================================${NC}"
echo -e "${BLUE}  KIỂM TRA TÍNH TOÀN VẸN (SMOKE TEST)                ${NC}"
echo -e "${BLUE}======================================================${NC}"
"$VENV_PYTHON" -c '
import sys
modules = ["fastapi", "uvicorn", "pydantic", "google.genai", "websockets", "sounddevice", "numpy"]
errors = []
for mod in modules:
    try:
        __import__(mod)
        print(f"  [OK] Module {mod}")
    except Exception as e:
        print(f"  [FAIL] Module {mod}: {e}")
        errors.append(mod)

if errors:
    print(f"\nCó {len(errors)} module chưa sẵn sàng: {errors}")
    sys.exit(1)
else:
    print("\nToàn bộ dependencies cốt lõi đã sẵn sàng!")
'

echo -e "\n${GREEN}>>> THIẾT LẬP MÔI TRƯỜNG HOÀN TẤT THÀNH CÔNG! <<<${NC}"
echo -e "Để kích hoạt môi trường ảo trong terminal, chạy:"
echo -e "  ${YELLOW}source .venv/bin/activate${NC}\n"
