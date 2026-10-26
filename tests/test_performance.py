"""Tests for per-interval OBS GetStats calculations."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from homeassistant.core import HomeAssistant

from custom_components.obs_websocket.performance import OBSPerformanceCoordinator


def stats(render_skipped: int, render_total: int, encode_skipped: int, encode_total: int) -> dict:
    return {
        "active_fps": 60.0,
        "average_frame_render_time": 2.5,
        "cpu_usage": 3.0,
        "memory_usage": 450.0,
        "render_skipped_frames": render_skipped,
        "render_total_frames": render_total,
        "output_skipped_frames": encode_skipped,
        "output_total_frames": encode_total,
    }


async def test_performance_warning_and_recovery(hass: HomeAssistant) -> None:
    conn = MagicMock(host="localhost")
    collector = OBSPerformanceCoordinator(hass, conn)
    sequence = [
        stats(0, 100, 0, 100),
        stats(20, 200, 0, 200),
        stats(40, 300, 0, 300),
        stats(40, 400, 0, 400),
        stats(40, 500, 0, 500),
    ]
    with patch.object(collector, "_fetch", side_effect=sequence):
        states = [await collector._async_update_data() for _ in sequence]
    assert states[0]["performance_warning"] is None
    assert states[1]["render_lag_percent"] == 20.0
    assert states[1]["performance_warning"] is False
    assert states[2]["performance_warning"] is True
    assert states[3]["performance_warning"] is True
    assert states[4]["performance_warning"] is False


async def test_counter_reset_does_not_create_warning(hass: HomeAssistant) -> None:
    conn = MagicMock(host="localhost")
    collector = OBSPerformanceCoordinator(hass, conn)
    with patch.object(collector, "_fetch", side_effect=[stats(100, 1000, 30, 500), stats(0, 0, 0, 0)]):
        await collector._async_update_data()
        result = await collector._async_update_data()
    assert result["render_lag_percent"] is None
    assert result["encode_lag_percent"] is None
    assert result["performance_warning"] is None
