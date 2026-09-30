#!/usr/bin/env bash
# ==============================================================================
# Script: scripts/install_cron.sh
# Description: Cài đặt hoặc gỡ bỏ Cron Job chạy đồng bộ môi trường tự động
#              trên máy phụ / máy bên cạnh.
#
# Cách dùng:
#   bash scripts/install_cron.sh             # Mặc định chạy mỗi 15 phút
#   bash scripts/install_cron.sh "*/30 * * * *"  # Tùy chỉnh tần suất
#   bash scripts/install_cron.sh --uninstall # Gỡ bỏ Cron Job
# ==============================================================================

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_SCRIPT="${PROJECT_ROOT}/scripts/cron_sync_setup.sh"
CRON_TAG="# VOICE_AGENT_TMA_SYNC_JOB"

# Đảm bảo target script có quyền thực thi
chmod +x "$TARGET_SCRIPT"

if [ "${1:-}" == "--uninstall" ]; then
    echo "Đang gỡ bỏ Cron Job đồng bộ của Voice_Agent_TMA..."
    crontab -l 2>/dev/null | grep -v "$CRON_TAG" | crontab - || true
    echo "Đã gỡ bỏ thành công khỏi crontab!"
    exit 0
fi

SCHEDULE="${1:-*/15 * * * *}" # Mặc định 15 phút một lần
CRON_COMMAND="${SCHEDULE} /bin/bash ${TARGET_SCRIPT} >/dev/null 2>&1 ${CRON_TAG}"

echo "=========================================================="
echo " CÀI ĐẶT CRON JOB TỰ ĐỘNG THIẾT LẬP MÔI TRƯỜNG DỰ ÁN"
echo "=========================================================="
echo "Lịch chạy: $SCHEDULE"
echo "Script đích: $TARGET_SCRIPT"

# Lấy crontab hiện tại, xóa job cũ nếu có và thêm job mới
EXISTING_CRON=$(crontab -l 2>/dev/null | grep -v "$CRON_TAG" || true)

if [ -z "$EXISTING_CRON" ]; then
    NEW_CRON="$CRON_COMMAND"
else
    NEW_CRON="${EXISTING_CRON}
${CRON_COMMAND}"
fi

echo "$NEW_CRON" | crontab -

echo -e "\n[THÀNH CÔNG] Đã ghi nhận Cron Job vào crontab của người dùng $(whoami)!"
echo "Xem danh sách cron job bằng lệnh: crontab -l"
echo "File nhật ký ghi lại quá trình chạy tại: ${PROJECT_ROOT}/logs/cron_sync_setup.log"
echo "Để gỡ bỏ bất kỳ lúc nào, chạy: bash scripts/install_cron.sh --uninstall"
