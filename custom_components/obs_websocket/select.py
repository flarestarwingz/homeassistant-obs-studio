"""Select platform for OBS WebSocket scene switching."""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import get_device_name, OBSConfigEntry, OBSCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant, entry: OBSConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up OBS WebSocket scene select from a config entry."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities([OBSSceneSelect(coordinator, entry)])


class OBSSceneSelect(CoordinatorEntity[OBSCoordinator], SelectEntity):
    """Select entity to switch OBS scenes."""

    _attr_has_entity_name = True
    _attr_name = "Scene"
    _attr_translation_key = "scene"

    def __init__(self, coordinator: OBSCoordinator, entry: OBSConfigEntry) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_scene"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=get_device_name(entry),
            manufacturer="OBS Project",
            sw_version=None,
        )
        self._connection = coordinator.connection

    @property
    def current_option(self) -> str | None:
        """Return the current scene."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("current_program_scene")

    @property
    def options(self) -> list[str]:
        """Return the list of available scenes."""
        if self.coordinator.data is None:
            return []
        return self.coordinator.data.get("scene_list", [])

    async def async_select_option(self, option: str) -> None:
        """Switch to the selected scene."""
        try:
            await self._connection.async_set_current_program_scene(option)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_scene_failed",
                translation_placeholders={
                    "host": self._connection.host,
                    "scene": option,
                    "error": str(err),
                },
            ) from err
