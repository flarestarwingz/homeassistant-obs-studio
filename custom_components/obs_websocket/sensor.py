"""Sensor platform for OBS WebSocket."""

from __future__ import annotations

import logging
from typing import Any, ClassVar

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import get_device_name, OBSConfigEntry, OBSCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def async_setup_entry(  # NOSONAR
    hass: HomeAssistant, entry: OBSConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up OBS WebSocket sensors from a config entry."""
    coordinator = entry.runtime_data.coordinator

    async_add_entities(
        [
            OBSStreamStatusSensor(coordinator, entry),
            OBSStreamServiceSensor(coordinator, entry),
            OBSRecordingSensor(coordinator, entry),
            OBSVirtualCamSensor(coordinator, entry),
        ]
    )


class OBSSensorBase(CoordinatorEntity[OBSCoordinator], SensorEntity):
    """Base class for OBS sensors."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: OBSCoordinator, entry: OBSConfigEntry) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=get_device_name(entry),
            manufacturer="OBS Project",
            sw_version=None,
        )


class OBSStreamStatusSensor(OBSSensorBase):
    """Sensor showing OBS stream status."""

    _attr_name = "Stream status"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options: ClassVar[list[str]] = ["idle", "streaming", "reconnecting"]
    _attr_translation_key = "stream_status"

    def __init__(self, coordinator: OBSCoordinator, entry: OBSConfigEntry) -> None:
        """Initialize."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_stream_status"

    @property
    def native_value(self) -> str | None:
        """Return the stream state."""
        if self.coordinator.data is None:
            return None
        status = self.coordinator.data["stream_status"]
        if getattr(status, "output_reconnecting", False):
            return "reconnecting"
        if getattr(status, "output_active", False):
            return "streaming"
        return "idle"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return stream statistics."""
        if self.coordinator.data is None:
            return {}
        status = self.coordinator.data["stream_status"]
        return {
            "output_bytes": getattr(status, "output_bytes", None),
            "output_duration": getattr(status, "output_duration", None),
            "output_timecode": getattr(status, "output_timecode", None),
            "output_skipped_frames": getattr(status, "output_skipped_frames", None),
            "output_total_frames": getattr(status, "output_total_frames", None),
            "output_congestion": getattr(status, "output_congestion", None),
        }


class OBSStreamServiceSensor(OBSSensorBase):
    """Sensor showing OBS stream service configuration."""

    _attr_name = "Stream service"
    _attr_translation_key = "stream_service"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: OBSCoordinator, entry: OBSConfigEntry) -> None:
        """Initialize."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_stream_service"

    @property
    def native_value(self) -> str | None:
        """Return the stream service type."""
        if self.coordinator.data is None:
            return None
        svc = self.coordinator.data["service_settings"]
        return getattr(svc, "stream_service_type", None)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return stream service settings."""
        if self.coordinator.data is None:
            return {}
        svc = self.coordinator.data["service_settings"]
        settings = getattr(svc, "stream_service_settings", {})
        return {"stream_service_settings": settings}


class OBSRecordingSensor(OBSSensorBase):
    """Sensor showing OBS recording status."""

    _attr_name = "Recording"
    _attr_translation_key = "recording"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options: ClassVar[list[str]] = ["recording", "idle"]

    def __init__(self, coordinator: OBSCoordinator, entry: OBSConfigEntry) -> None:
        """Initialize."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_recording"

    @property
    def native_value(self) -> str | None:
        """Return the recording state."""
        if self.coordinator.data is None:
            return None
        return "recording" if self.coordinator.data.get("recording") else "idle"


class OBSVirtualCamSensor(OBSSensorBase):
    """Sensor showing OBS virtual camera status."""

    _attr_name = "Virtual camera"
    _attr_translation_key = "virtual_cam"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options: ClassVar[list[str]] = ["active", "idle"]

    def __init__(self, coordinator: OBSCoordinator, entry: OBSConfigEntry) -> None:
        """Initialize."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_virtual_cam"

    @property
    def native_value(self) -> str | None:
        """Return the virtual camera state."""
        if self.coordinator.data is None:
            return None
        return "active" if self.coordinator.data.get("virtual_cam_active") else "idle"
