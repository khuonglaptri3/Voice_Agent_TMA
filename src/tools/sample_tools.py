"""sample_tools.py
----------------
Sample ADK-compatible Python tools for Mid-Speech Function Calling (Day 5 - Dev A).

Defines callable functions with clear docstrings and type annotations that can be
registered with Gemini Live API for real-time tool calling during voice conversation.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Callable, Dict, List
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

# Mock database of TMA Solutions meeting rooms
MEETING_ROOMS_DB: dict[str, dict[str, Any]] = {
    "phòng lab a": {
        "room_name": "Phòng Lab A",
        "status": "Trống",
        "capacity": 15,
        "floor": "Tầng 2, Tòa nhà TMA Innovation",
        "next_booking": "14:00 hôm nay",
    },
    "phòng hội nghị b": {
        "room_name": "Phòng Hội nghị B",
        "status": "Đang có lịch họp",
        "capacity": 30,
        "floor": "Tầng 3, Tòa nhà TMA Innovation",
        "current_meeting": "Họp dự án AI Voice Agent (10:00 - 11:30)",
        "next_available": "11:30 hôm nay",
    },
    "phòng 101": {
        "room_name": "Phòng 101",
        "status": "Trống",
        "capacity": 8,
        "floor": "Tầng 1, Tòa nhà Lab 6",
        "next_booking": "Cả ngày trống",
    },
    "phòng 102": {
        "room_name": "Phòng 102",
        "status": "Đang có lịch họp",
        "capacity": 10,
        "floor": "Tầng 1, Tòa nhà Lab 6",
        "current_meeting": "Daily Standup Team Mobile (09:00 - 10:00)",
        "next_available": "10:00 hôm nay",
    },
}

VIETNAMESE_DAYS = {
    0: "thứ Hai",
    1: "thứ Ba",
    2: "thứ Tư",
    3: "thứ Năm",
    4: "thứ Sáu",
    5: "thứ Bảy",
    6: "Chủ nhật",
}


def get_current_time(timezone_name: str = "Asia/Ho_Chi_Minh") -> str:
    """Lấy thời gian và ngày hiện tại của hệ thống theo múi giờ.

    Args:
        timezone_name: Tên múi giờ IANA chuẩn (mặc định là 'Asia/Ho_Chi_Minh' cho giờ Việt Nam).

    Returns:
        Chuỗi mô tả giờ, phút, thứ, ngày, tháng, năm bằng tiếng Việt.
    """
    try:
        tz = ZoneInfo(timezone_name)
    except Exception:
        tz = ZoneInfo("Asia/Ho_Chi_Minh")

    now = datetime.now(tz)
    weekday_name = VIETNAMESE_DAYS.get(now.weekday(), f"thứ {now.weekday() + 2}")
    result = (
        f"Hiện tại là {now.hour} giờ {now.minute:02d} phút, {weekday_name}, "
        f"ngày {now.day:02d} tháng {now.month:02d} năm {now.year}."
    )
    logger.info("Tool executed: get_current_time -> %s", result)
    return result


def check_meeting_room(room_name: str) -> dict[str, Any]:
    """Tra cứu trạng thái phòng họp (Trống hoặc Đang có lịch) tại TMA Solutions.

    Args:
        room_name: Tên hoặc mã số phòng họp (ví dụ: 'Phòng Lab A', 'Phòng Hội nghị B', 'Phòng 101', 'Phòng 102').

    Returns:
        Dict chi tiết về trạng thái phòng, sức chứa, địa điểm và lịch trình tiếp theo.
    """
    normalized_key = room_name.strip().lower()

    # Direct match or partial match
    matched_info = None
    for key, info in MEETING_ROOMS_DB.items():
        if key in normalized_key or normalized_key in key:
            matched_info = info
            break

    if matched_info:
        result = {
            "found": True,
            "room_name": matched_info["room_name"],
            "status": matched_info["status"],
            "capacity": matched_info["capacity"],
            "location": matched_info["floor"],
            "details": (
                f"Phòng {matched_info['room_name']} hiện đang {matched_info['status']}. "
                f"Sức chứa: {matched_info['capacity']} người tại {matched_info['floor']}."
            ),
        }
        if "next_available" in matched_info:
            result["next_available"] = matched_info["next_available"]
    else:
        # Default fallback for unknown rooms
        result = {
            "found": False,
            "room_name": room_name,
            "status": "Không xác định",
            "details": (
                f"Không tìm thấy thông tin phòng họp '{room_name}'. "
                f"Các phòng có sẵn gồm: Phòng Lab A, Phòng Hội nghị B, Phòng 101, Phòng 102."
            ),
        }

    logger.info("Tool executed: check_meeting_room(%s) -> %s", room_name, result)
    return result


SAMPLE_TOOLS: list[Callable[..., Any]] = [get_current_time, check_meeting_room]

TOOL_REGISTRY: dict[str, Callable[..., Any]] = {
    "get_current_time": get_current_time,
    "check_meeting_room": check_meeting_room,
}
