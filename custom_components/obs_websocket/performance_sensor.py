"""OBS GetStats diagnostic sensors and performance warning binary sensor."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import get_device_name
from .const import DOMAIN
from .performance import OBSPerformanceCoordinator


class _OBSPerformanceBase(CoordinatorEntity[OBSPerformanceCoordinator]):
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: OBSPerformanceCoordinator, entry: Any, key: str, name: str) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_performance_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=get_device_name(entry),
            manufacturer="OBS Project",
        )


class OBSPerformanceSensor(_OBSPerformanceBase, SensorEntity):
    """Expose raw OBS statistics and interval-based lag percentages."""

    def __init__(
        self,
        coordinator: OBSPerformanceCoordinator,
        entry: Any,
        key: str,
        name: str,
        unit: str | None,
    ) -> None:
        super().__init__(coordinator, entry, key, name)
        self._attr_native_unit_of_measurement = unit
        self._attr_suggested_display_precision = {
            "active_fps": 2,
            "average_frame_render_time": 2,
            "cpu_usage": 1,
            "memory_usage": 1,
            "render_lag_percent": 2,
            "encode_lag_percent": 2,
        }.get(key, 0)

    @property
    def native_value(self) -> float | int | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self._key)


class OBSPerformanceWarning(_OBSPerformanceBase, BinarySensorEntity):
    """Two consecutive bad samples cause an alert; two good samples clear it."""

    def __init__(self, coordinator: OBSPerformanceCoordinator, entry: Any) -> None:
        super().__init__(coordinator, entry, "performance_warning", "Performance warning")

    @property
    def is_on(self) -> bool | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("performance_warning")


def create_sensors(coordinator: OBSPerformanceCoordinator, entry: Any) -> list[OBSPerformanceSensor]:
    return [
        OBSPerformanceSensor(coordinator, entry, key, name, unit)
        for key, name, unit in (
            ("active_fps", "Actual FPS", "fps"),
            ("average_frame_render_time", "Average render time", "ms"),
            ("cpu_usage", "OBS CPU usage", "%"),
            ("memory_usage", "OBS memory usage", "MB"),
            ("render_skipped_frames", "Total rendering misses", "frames"),
            ("render_total_frames", "Total rendered frames", "frames"),
            ("output_skipped_frames", "Total encoding skips", "frames"),
            ("output_total_frames", "Total encoded frames", "frames"),
            ("render_lag_percent", "Recent rendering lag", "%"),
            ("encode_lag_percent", "Recent encoding lag", "%"),
        )
    ]
