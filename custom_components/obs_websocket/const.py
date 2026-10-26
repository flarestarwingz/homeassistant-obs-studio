"""Constants for the OBS WebSocket integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "obs_websocket"

DEFAULT_HOST: Final = "localhost"
DEFAULT_PORT: Final = 4455

HEARTBEAT_INTERVAL: Final = 60

# Coalesce rapid OBS state changes into one trailing refresh.
EVENT_REFRESH_COOLDOWN: Final = 0.5

PLATFORMS: Final[list[str]] = [
    "binary_sensor",
    "button",
    "sensor",
    "select",
    "switch",
]

OPTION_DEVICE_NAME: Final = "device_name"
OPTION_SCENE_ITEM_MODE: Final = "scene_item_mode"
OPTION_SCENE_ITEM_SCENES: Final = "scene_item_scenes"
OPTION_INCLUDE_SCENE_SOURCES: Final = "include_scene_sources"

SCENE_ITEM_MODE_SOURCES: Final = "sources"
SCENE_ITEM_MODE_ALL: Final = "all"

DEFAULT_DEVICE_NAME: Final = "OBS Studio"
DEFAULT_SCENE_ITEM_MODE: Final = SCENE_ITEM_MODE_SOURCES
DEFAULT_INCLUDE_SCENE_SOURCES: Final = True
