"""Regression and lifecycle tests for OBS performance monitoring."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.obs_websocket.performance import OBSPerformanceCoordinator


def sample(render_missed: int, render_total: int, encode_missed: int, encode_total: int) -> dict:
    return {
        "active_fps": 60.0,
        "average_frame_render_time": 1.0,
        "cpu_usage": 2.0,
        "memory_usage": 400.0,
        "render_skipped_frames": render_missed,
        "render_total_frames": render_total,
        "output_skipped_frames": encode_missed,
        "output_total_frames": encode_total,
    }


async def test_rendering_alert_with_idle_encoder(hass: HomeAssistant) -> None:
    collector = OBSPerformanceCoordinator(hass, MagicMock(host="mock-host"))
    samples = [
        sample(0, 100, 0, 0),
        sample(10, 200, 0, 0),
        sample(20, 300, 0, 0),
        sample(20, 400, 0, 0),
        sample(20, 500, 0, 0),
    ]
    with patch.object(collector, "_fetch", side_effect=samples):
        results = [await collector._async_update_data() for _ in samples]
    assert results[1]["render_lag_percent"] == 10.0
    assert results[1]["encode_lag_percent"] is None
    assert [row["performance_warning"] for row in results] == [None, False, True, True, False]


async def test_encoding_alert_with_invalid_rendering_interval(hass: HomeAssistant) -> None:
    collector = OBSPerformanceCoordinator(hass, MagicMock(host="mock-host"))
    samples = [
        sample(0, 0, 0, 100),
        sample(0, 0, 10, 200),
        sample(0, 0, 20, 300),
    ]
    with patch.object(collector, "_fetch", side_effect=samples):
        results = [await collector._async_update_data() for _ in samples]
    assert results[1]["render_lag_percent"] is None
    assert results[1]["encode_lag_percent"] == 10.0
    assert results[2]["performance_warning"] is True


async def test_failure_resets_baseline_and_allows_recovery(hass: HomeAssistant) -> None:
    collector = OBSPerformanceCoordinator(hass, MagicMock(host="mock-host"))
    sequence = [
        sample(0, 100, 0, 0),
        sample(10, 200, 0, 0),
        sample(20, 300, 0, 0),
        ConnectionError("OBS disconnected"),
        sample(100, 1000, 0, 0),
        sample(100, 1100, 0, 0),
    ]
    with patch.object(collector, "_fetch", side_effect=sequence):
        for _ in range(3):
            await collector._async_update_data()
        assert collector._warning is True
        with pytest.raises(UpdateFailed, match="OBS GetStats unavailable"):
            await collector._async_update_data()
        assert collector._previous is None
        after_reconnect = await collector._async_update_data()
        recovered = await collector._async_update_data()
    assert after_reconnect["performance_warning"] is None
    assert recovered["render_lag_percent"] == 0.0
    assert recovered["performance_warning"] is False


async def test_failed_request_disconnects_and_reconnects_client(hass: HomeAssistant) -> None:
    connection = MagicMock(host="mock-host")
    collector = OBSPerformanceCoordinator(hass, connection)
    bad_client = MagicMock()
    bad_client.get_stats.side_effect = ConnectionError("disconnect")
    good_client = MagicMock()
    good_client.get_stats.return_value = MagicMock(**sample(0, 100, 0, 0))
    with (
        patch.dict(
            "sys.modules",
            {"obsws_python": MagicMock(ReqClient=MagicMock(side_effect=[bad_client, good_client]))},
        ),
    ):
        factory = __import__("obsws_python").ReqClient
        with pytest.raises(UpdateFailed, match="OBS GetStats unavailable"):
            await collector._async_update_data()
        assert collector._client is None
        bad_client.disconnect.assert_called_once()
        result = await collector._async_update_data()
        assert result["render_total_frames"] == 100
        assert factory.call_count == 2
        await collector.async_shutdown()
        good_client.disconnect.assert_called_once()
