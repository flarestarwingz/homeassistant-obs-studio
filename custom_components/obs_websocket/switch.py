"""Switch platform for OBS WebSocket scene item visibility."""

from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import get_device_name, OBSConfigEntry, OBSCoordinator
from .const import (
    DEFAULT_INCLUDE_SCENE_SOURCES,
    DEFAULT_SCENE_ITEM_MODE,
    DOMAIN,
    OPTION_INCLUDE_SCENE_SOURCES,
    OPTION_SCENE_ITEM_MODE,
    OPTION_SCENE_ITEM_SCENES,
    SCENE_ITEM_MODE_ALL,
    SCENE_ITEM_MODE_SOURCES,
)

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

SOURCE_TYPE_SCENE = "OBS_SOURCE_TYPE_SCENE"


async def async_setup_entry(
    hass: HomeAssistant, entry: OBSConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up OBS WebSocket scene item switches from a config entry.

    Entities are created once at setup and are never removed, so they remain
    stable for use in automations and dashboards.
    """
    coordinator = entry.runtime_data.coordinator
    mode = entry.options.get(OPTION_SCENE_ITEM_MODE, DEFAULT_SCENE_ITEM_MODE)
    selected_scenes = entry.options.get(OPTION_SCENE_ITEM_SCENES, [])
    include_scene_sources = entry.options.get(
        OPTION_INCLUDE_SCENE_SOURCES, DEFAULT_INCLUDE_SCENE_SOURCES
    )

    scene_items = coordinator.data.get("scene_items", {}) if coordinator.data else {}

    if selected_scenes:
        scene_items = {
            scene: items for scene, items in scene_items.items() if scene in selected_scenes
        }

    if not include_scene_sources:
        scene_items = {
            scene: [item for item in items if item.get("type") != SOURCE_TYPE_SCENE]
            for scene, items in scene_items.items()
        }

    entities: list[OBSSceneItemSwitch] = []

    if mode == SCENE_ITEM_MODE_ALL:
        for scene, items in scene_items.items():
            for item in items:
                entities.append(
                    OBSSceneItemSwitch(
                        coordinator,
                        entry,
                        source_name=item["name"],
                        scene_name=scene,
                        item_id=item["id"],
                    )
                )
    else:
        seen: set[str] = set()
        for items in scene_items.values():
            for item in items:
                if item["name"] not in seen:
                    seen.add(item["name"])
                    entities.append(
                        OBSSceneItemSwitch(
                            coordinator,
                            entry,
                            source_name=item["name"],
                        )
                    )

    async_add_entities(entities)


class OBSSceneItemSwitch(CoordinatorEntity[OBSCoordinator], SwitchEntity):
    """Switch to enable/disable a scene item in OBS.

    In "sources" mode the switch represents one source and operates on that
    source's item in the currently active scene. In "all" mode the switch
    represents one item in a fixed scene.
    """

    def __init__(
        self,
        coordinator: OBSCoordinator,
        entry: OBSConfigEntry,
        source_name: str,
        scene_name: str | None = None,
        item_id: int | None = None,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._connection = coordinator.connection
        self._source_name = source_name
        self._fixed_scene = scene_name
        self._fixed_item_id = item_id

        if scene_name is not None and item_id is not None:
            self._attr_unique_id = f"{entry.entry_id}_scene_item_all_{scene_name}_{item_id}"
            self._attr_name = f"{scene_name} - {source_name}"
        else:
            self._attr_unique_id = f"{entry.entry_id}_scene_item_{source_name}"
            self._attr_name = source_name

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=get_device_name(entry),
            manufacturer="OBS Project",
            sw_version=None,
        )

    def _resolve(self) -> tuple[str, int] | None:
        """Return (scene_name, item_id) for this switch, if available."""
        if self._fixed_scene is not None and self._fixed_item_id is not None:
            return self._fixed_scene, self._fixed_item_id

        if self.coordinator.data is None:
            return None
        scene = self.coordinator.data.get("current_program_scene")
        items = self.coordinator.data.get("scene_items", {}).get(scene, [])
        for item in items:
            if item["name"] == self._source_name:
                return scene, item["id"]
        return None

    @property
    def is_on(self) -> bool:
        """Return whether the scene item is visible in the active scene.

        In "sources" mode a source that is not present in the active scene is
        reported as off (not visible). The switch always stays available.
        """
        if self.coordinator.data is None:
            return False
        resolved = self._resolve()
        if resolved is None:
            return False
        scene, item_id = resolved
        for item in self.coordinator.data.get("scene_items", {}).get(scene, []):
            if item["id"] == item_id:
                return item["enabled"]
        return False

    @property
    def icon(self) -> str:
        """Return icon based on state."""
        return "mdi:eye" if self.is_on else "mdi:eye-off"

    async def _set(self, enabled: bool) -> None:
        resolved = self._resolve()
        if resolved is None:
            raise HomeAssistantError(
                f"Scene item '{self._source_name}' is not present in the current OBS scene."
            )
        scene, item_id = resolved
        try:
            await self._connection.async_set_scene_item_enabled(scene, item_id, enabled)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="scene_item_toggle_failed",
                translation_placeholders={
                    "host": self._connection.host,
                    "scene": scene,
                    "source": self._source_name,
                    "error": str(err),
                },
            ) from err

    async def async_turn_on(self, **kwargs) -> None:
        """Enable the scene item."""
        await self._set(True)

    async def async_turn_off(self, **kwargs) -> None:
        """Disable the scene item."""
        await self._set(False)
