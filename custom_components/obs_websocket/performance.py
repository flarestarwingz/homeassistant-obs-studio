"""Low-overhead OBS WebSocket performance monitoring."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

PERFORMANCE_INTERVAL = 10
WARNING_PERCENT = 1.0
WARNING_MIN_FRAMES = 5
WARNING_BAD_SAMPLES = 2
WARNING_GOOD_SAMPLES = 2


class OBSPerformanceCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll GetStats only, without fetching scene and source metadata."""

    def __init__(self, hass: HomeAssistant, connection: Any) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"OBS Performance ({connection.host})",
            update_interval=timedelta(seconds=PERFORMANCE_INTERVAL),
        )
        self.connection = connection
        self._client: Any | None = None
        self._previous: dict[str, int] | None = None
        self._bad_samples = 0
        self._good_samples = 0
        self._warning = False

    def _fetch(self) -> dict[str, Any]:
        """Run on HA's executor. Keep statistics requests off the main OBS client."""
        import obsws_python as obs

        if self._client is None:
            self._client = obs.ReqClient(**self.connection._get_kwargs())
        try:
            stats = self._client.get_stats()
        except Exception:
            self._disconnect()
            raise
        fields = (
            "active_fps",
            "average_frame_render_time",
            "cpu_usage",
            "memory_usage",
            "render_skipped_frames",
            "render_total_frames",
            "output_skipped_frames",
            "output_total_frames",
        )
        return {
            key: value
            if isinstance((value := getattr(stats, key, None)), (int, float)) and not isinstance(value, bool)
            else None
            for key in fields
        }

    def _disconnect(self) -> None:
        if self._client is not None:
            try:
                self._client.disconnect()
            except Exception:
                _LOGGER.debug("Could not close OBS statistics client", exc_info=True)
            finally:
                self._client = None

    async def async_shutdown(self) -> None:
        """Stop updates and disconnect our independent statistics connection."""
        await super().async_shutdown()
        await self.hass.async_add_executor_job(self._disconnect)

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            values = await self.hass.async_add_executor_job(self._fetch)
        except Exception as err:
            self._previous = None
            self._bad_samples = 0
            self._good_samples = 0
            self._warning = False
            raise UpdateFailed(f"OBS GetStats unavailable: {type(err).__name__}") from err

        counters = (
            "render_skipped_frames",
            "render_total_frames",
            "output_skipped_frames",
            "output_total_frames",
        )
        current: dict[str, int] = {}
        for key in counters:
            value = values.get(key)
            if value is None:
                self._previous = None
                raise UpdateFailed(f"OBS GetStats missing {key}")
            current[key] = int(value)

        rates: dict[str, float | None] = {"render_lag_percent": None, "encode_lag_percent": None}
        misses: dict[str, int | None] = {"render_misses": None, "encode_misses": None}
        if self._previous is not None:
            for skipped, total, rate_key, miss_key in (
                ("render_skipped_frames", "render_total_frames", "render_lag_percent", "render_misses"),
                ("output_skipped_frames", "output_total_frames", "encode_lag_percent", "encode_misses"),
            ):
                delta_total = current[total] - self._previous[total]
                delta_skipped = current[skipped] - self._previous[skipped]
                # Counter reset, idle OBS, or missing frames: don't infer health.
                if delta_total > 0 and 0 <= delta_skipped <= delta_total:
                    rates[rate_key] = round(100.0 * delta_skipped / delta_total, 3)
                    misses[miss_key] = delta_skipped
        self._previous = current

        valid = all(value is not None for value in rates.values())
        if valid:
            bad = any(
                rates[name] > WARNING_PERCENT and misses[miss] >= WARNING_MIN_FRAMES
                for name, miss in (
                    ("render_lag_percent", "render_misses"),
                    ("encode_lag_percent", "encode_misses"),
                )
            )
            if bad:
                self._bad_samples += 1
                self._good_samples = 0
                if self._bad_samples >= WARNING_BAD_SAMPLES:
                    self._warning = True
            else:
                self._good_samples += 1
                self._bad_samples = 0
                if self._good_samples >= WARNING_GOOD_SAMPLES:
                    self._warning = False
        else:
            self._bad_samples = 0
            self._good_samples = 0
            self._warning = False

        return {**values, **rates, **misses, "performance_warning": self._warning if valid else None}
