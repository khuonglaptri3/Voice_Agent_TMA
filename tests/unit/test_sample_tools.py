"""Unit tests for sample tools: get_current_time and check_meeting_room (Day 5 - Dev A)."""
from __future__ import annotations

from src.tools.sample_tools import (
    SAMPLE_TOOLS,
    TOOL_REGISTRY,
    check_meeting_room,
    get_current_time,
)


def test_get_current_time_returns_vietnamese_datetime():
    """Verify get_current_time produces formatted Vietnamese time string."""
    time_str = get_current_time()
    assert isinstance(time_str, str)
    assert "Hiện tại là" in time_str
    assert "giờ" in time_str
    assert "phút" in time_str
    assert "ngày" in time_str
    assert "tháng" in time_str
    assert "năm" in time_str


def test_get_current_time_handles_custom_timezone():
    """Verify get_current_time handles timezone argument gracefully."""
    time_str = get_current_time("Asia/Bangkok")
    assert "Hiện tại là" in time_str

    # Invalid timezone falls back gracefully
    time_str_fallback = get_current_time("Invalid/Timezone_XYZ")
    assert "Hiện tại là" in time_str_fallback


def test_check_meeting_room_existing_rooms():
    """Verify check_meeting_room correctly queries mock TMA meeting rooms."""
    # Test Room A
    res_a = check_meeting_room("Phòng Lab A")
    assert res_a["found"] is True
    assert res_a["room_name"] == "Phòng Lab A"
    assert res_a["status"] == "Trống"
    assert res_a["capacity"] == 15

    # Test Room B (currently occupied)
    res_b = check_meeting_room("hội nghị b")
    assert res_b["found"] is True
    assert res_b["room_name"] == "Phòng Hội nghị B"
    assert res_b["status"] == "Đang có lịch họp"
    assert res_b["capacity"] == 30
    assert "next_available" in res_b

    # Test Room 101
    res_101 = check_meeting_room("101")
    assert res_101["found"] is True
    assert res_101["status"] == "Trống"


def test_check_meeting_room_unknown_room():
    """Verify check_meeting_room handles non-existent room query."""
    res_unknown = check_meeting_room("Phòng VIP Không Tồn Tại 999")
    assert res_unknown["found"] is False
    assert res_unknown["status"] == "Không xác định"
    assert "Không tìm thấy" in res_unknown["details"]


def test_sample_tools_registry():
    """Verify SAMPLE_TOOLS and TOOL_REGISTRY contracts."""
    assert len(SAMPLE_TOOLS) >= 2
    assert get_current_time in SAMPLE_TOOLS
    assert check_meeting_room in SAMPLE_TOOLS

    assert "get_current_time" in TOOL_REGISTRY
    assert "check_meeting_room" in TOOL_REGISTRY
    assert callable(TOOL_REGISTRY["get_current_time"])
    assert callable(TOOL_REGISTRY["check_meeting_room"])
