#!/usr/bin/env bash
# ==============================================================================
# Script: scripts/cron_sync_setup.sh
# Description: Tự động đồng bộ mã nguồn Git và cập nhật môi trường ảo.
#              Được thiết kế để chạy định kỳ thông qua Cron trên máy bên cạnh.
# ==============================================================================

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

LOG_DIR="${PROJECT_ROOT}/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="${LOG_DIR}/cron_sync_setup.log"

# Giới hạn kích thước file log (nếu > 5MB thì giữ lại 1000 dòng gần nhất)
if [ -f "$LOG_FILE" ] && [ $(stat -c%s "$LOG_FILE" 2>/dev/null || stat -f%z "$LOG_FILE" 2>/dev/null) -gt 5242880 ]; then
    tail -n 1000 "$LOG_FILE" > "${LOG_FILE}.tmp" && mv "${LOG_FILE}.tmp" "$LOG_FILE"
fi

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

log "=== BẮT ĐẦU KIỂM TRA ĐỒNG BỘ DỰ ÁN ==="

# 1. Kiểm tra môi trường ảo có sẵn chưa
NEED_SETUP=0
if [ ! -d "${PROJECT_ROOT}/.venv" ]; then
    log "[CẢNH BÁO] Chưa tìm thấy .venv, cần kích hoạt thiết lập ban đầu."
    NEED_SETUP=1
fi

# 2. Kiểm tra Git remote và kéo code mới nếu có
if command -v git &>/dev/null && [ -d "${PROJECT_ROOT}/.git" ]; then
    CURRENT_BRANCH=$(git branch --show-current || echo "main")
    log "Nhánh hiện tại: $CURRENT_BRANCH"

    # Lấy thông tin mới nhất từ remote
    if git fetch origin "$CURRENT_BRANCH" >> "$LOG_FILE" 2>&1; then
        LOCAL_HASH=$(git rev-parse HEAD)
        REMOTE_HASH=$(git rev-parse "origin/$CURRENT_BRANCH" 2>/dev/null || echo "$LOCAL_HASH")

        if [ "$LOCAL_HASH" != "$REMOTE_HASH" ]; then
            log "Phát hiện commit mới trên remote ($LOCAL_HASH -> $REMOTE_HASH). Đang kéo mã nguồn về..."
            if git pull --rebase origin "$CURRENT_BRANCH" >> "$LOG_FILE" 2>&1; then
                log "Kéo mã nguồn thành công!"
                NEED_SETUP=1
            else
                log "[LỖI] Kéo mã nguồn thất bại! Vui lòng kiểm tra xung đột git thủ công."
            fi
        else
            log "Mã nguồn đã ở trạng thái mới nhất."
        fi
    else
        log "[LỖI] Không thể kết nối tới remote git để fetch."
    fi
else
    log "[LỖI] Thư mục hiện tại không phải git repository hoặc không có git."
fi

# 3. Kích hoạt thiết lập nếu cần
if [ "$NEED_SETUP" -eq 1 ]; then
    log "Đang kích hoạt scripts/setup_env.sh..."
    if bash "${PROJECT_ROOT}/scripts/setup_env.sh" >> "$LOG_FILE" 2>&1; then
        log "[THÀNH CÔNG] Cập nhật môi trường hoàn tất!"
    else
        log "[LỖI] Quá trình setup_env.sh gặp lỗi! Xem chi tiết trong log trên."
    fi
else
    log "Môi trường đã sẵn sàng, không cần thiết lập lại."
fi

log "=== KẾT THÚC LƯỢT ĐỒNG BỘ ==="
