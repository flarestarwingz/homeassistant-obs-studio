"""OBS WebSocket integration with persistent push connection."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DEFAULT_DEVICE_NAME,
    DOMAIN,
    EVENT_REFRESH_COOLDOWN,
    HEARTBEAT_INTERVAL,
    OPTION_DEVICE_NAME,
    PLATFORMS,
)

_LOGGER = logging.getLogger(__name__)


def get_device_name(entry: ConfigEntry) -> str:
    """Return the configured friendly device name."""
    return str(entry.options.get(OPTION_DEVICE_NAME, DEFAULT_DEVICE_NAME))


@dataclass
class OBSRuntimeData:
    """Runtime data for the OBS WebSocket integration."""

    connection: OBSConnection
    coordinator: OBSCoordinator


type OBSConfigEntry = ConfigEntry[OBSRuntimeData]


class OBSConnection:
    """Persistent OBS WebSocket connection with event-driven updates."""

    def __init__(self, hass: HomeAssistant, host: str, port: int, password: str) -> None:
        self.hass = hass
        self.host = host
        self._port = port
        self._password = password
        self._req_client: Any | None = None
        self._event_client: Any | None = None
        self.coordinator: DataUpdateCoordinator[dict[str, Any]] | None = None

    @property
    def connected(self) -> bool:
        return self._req_client is not None

    def _get_kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "host": self.host,
            "port": self._port,
            "timeout": 10,
        }
        if self._password:
            kwargs["password"] = self._password
        return kwargs

    async def async_connect(self) -> None:
        """Create persistent ReqClient and EventClient connections."""
        conn = self

        def _connect() -> None:
            import obsws_python as obs

            conn._req_client = obs.ReqClient(**conn._get_kwargs())

            class _Events(obs.EventClient):
                def on_stream_state_changed(self_: Any, data: Any) -> None:
                    conn._on_event()

                def on_current_program_scene_changed(self_: Any, data: Any) -> None:
                    conn._on_event()

                def on_scene_item_enable_state_changed(self_: Any, data: Any) -> None:
                    conn._on_event()

                def on_scene_item_created(self_: Any, data: Any) -> None:
                    conn._on_event()

                def on_scene_item_removed(self_: Any, data: Any) -> None:
                    conn._on_event()

                def on_scene_list_changed(self_: Any, data: Any) -> None:
                    conn._on_event()

                def on_record_state_changed(self_: Any, data: Any) -> None:
                    conn._on_event()

                def on_virtualcam_state_changed(self_: Any, data: Any) -> None:
                    conn._on_event()

            events = _Events(**conn._get_kwargs())

            events.callback.register(events.on_stream_state_changed)
            events.callback.register(events.on_current_program_scene_changed)
            events.callback.register(events.on_scene_item_enable_state_changed)
            events.callback.register(events.on_scene_item_created)
            events.callback.register(events.on_scene_item_removed)
            events.callback.register(events.on_scene_list_changed)
            events.callback.register(events.on_record_state_changed)
            events.callback.register(events.on_virtualcam_state_changed)

            conn._event_client = events

        await self.hass.async_add_executor_job(_connect)

    def _on_event(self) -> None:
        """Handle OBS event from EventClient thread."""
        if self.coordinator is None:
            return
        asyncio.run_coroutine_threadsafe(
            self.coordinator.async_request_refresh(),
            self.hass.loop,
        )

    async def async_fetch_data(self) -> dict[str, Any]:
        """Fetch current state using the persistent ReqClient."""

        def _fetch() -> dict[str, Any]:
            status = self._req_client.get_stream_status()
            service = self._req_client.get_stream_service_settings()

            current_scene: str | None = None
            scene_list: list[str] = []
            scene_items: dict[str, list[dict[str, Any]]] = {}
            try:
                current_scene_resp = self._req_client.get_current_program_scene()
                current_scene = current_scene_resp.scene_name if current_scene_resp else None

                scene_list_resp = self._req_client.get_scene_list()
                scenes = list(scene_list_resp.scenes) if scene_list_resp else []
                scene_list = [s["sceneName"] if isinstance(s, dict) else s.scene_name for s in scenes]

                for scene in scenes:
                    name = scene["sceneName"] if isinstance(scene, dict) else scene.scene_name
                    try:
                        items_resp = self._req_client.get_scene_item_list(name)
                        raw_items = list(items_resp.scene_items) if items_resp else []
                        scene_items[name] = [
                            {
                                "id": i["sceneItemId"] if isinstance(i, dict) else i.scene_item_id,
                                "name": i["sourceName"] if isinstance(i, dict) else i.source_name,
                                "enabled": i["sceneItemEnabled"] if isinstance(i, dict) else i.scene_item_enabled,
                                "type": i["sourceType"] if isinstance(i, dict) else getattr(i, "source_type", None),
                                "is_group": i["isGroup"] if isinstance(i, dict) else getattr(i, "is_group", None),
                            }
                            for i in raw_items
                        ]
                    except Exception:
                        scene_items[name] = []
            except Exception:
                _LOGGER.debug("Failed to fetch OBS scene data", exc_info=True)

            recording: bool | None = None
            try:
                record_resp = self._req_client.get_record_status()
                recording = record_resp.output_active if record_resp else None
            except Exception:
                _LOGGER.debug("Failed to fetch OBS record status", exc_info=True)

            virtual_cam_active: bool | None = None
            try:
                vcam_resp = self._req_client.get_virtual_cam_status()
                virtual_cam_active = vcam_resp.output_active if vcam_resp else None
            except Exception:
                _LOGGER.debug("Failed to fetch OBS virtual cam status", exc_info=True)

            return {
                "stream_status": status,
                "service_settings": service,
                "current_program_scene": current_scene,
                "scene_list": scene_list,
                "scene_items": scene_items,
                "recording": recording,
                "virtual_cam_active": virtual_cam_active,
            }

        return await self.hass.async_add_executor_job(_fetch)

    async def async_start_stream(self) -> None:
        """Start streaming in OBS."""
        await self.hass.async_add_executor_job(self._req_client.start_stream)

    async def async_stop_stream(self) -> None:
        """Stop streaming in OBS."""
        await self.hass.async_add_executor_job(self._req_client.stop_stream)

    async def async_set_current_program_scene(self, scene_name: str) -> None:
        """Switch to the given scene."""
        await self.hass.async_add_executor_job(self._req_client.set_current_program_scene, scene_name)

    async def async_set_scene_item_enabled(self, scene_name: str, item_id: int, enabled: bool) -> None:
        """Enable or disable a scene item."""
        await self.hass.async_add_executor_job(self._req_client.set_scene_item_enabled, scene_name, item_id, enabled)

    async def async_toggle_record(self) -> None:
        """Toggle recording."""
        await self.hass.async_add_executor_job(self._req_client.toggle_record)

    async def async_toggle_virtual_cam(self) -> None:
        """Toggle virtual camera."""
        await self.hass.async_add_executor_job(self._req_client.toggle_virtual_cam)

    async def async_disconnect(self) -> None:
        """Disconnect both clients."""

        def _disconnect() -> None:
            for client in (self._event_client, self._req_client):
                if client:
                    with contextlib.suppress(Exception):
                        client.disconnect()
            self._event_client = None
            self._req_client = None

        await self.hass.async_add_executor_job(_disconnect)


class OBSCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator with persistent connection and event-driven refresh."""

    def __init__(self, hass: HomeAssistant, connection: OBSConnection) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"OBS WebSocket ({connection.host})",
            update_interval=timedelta(seconds=HEARTBEAT_INTERVAL),
            request_refresh_debouncer=Debouncer(
                hass,
                _LOGGER,
                cooldown=EVENT_REFRESH_COOLDOWN,
                immediate=True,
            ),
        )
        self.connection = connection
        self._was_available = True

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            if not self.connection.connected:
                await self.connection.async_connect()
            data = await self.connection.async_fetch_data()
        except Exception as err:
            await self.connection.async_disconnect()
            if self._was_available:
                _LOGGER.warning(
                    "OBS WebSocket (%s) is unavailable: %s",
                    self.connection.host,
                    err,
                )
                self._was_available = False
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={
                    "host": self.connection.host,
                    "error": str(err),
                },
            ) from err

        if not self._was_available:
            _LOGGER.info("OBS WebSocket (%s) is available again", self.connection.host)
            self._was_available = True
        return data


async def async_setup_entry(hass: HomeAssistant, entry: OBSConfigEntry) -> bool:
    """Set up OBS WebSocket from a config entry."""
    connection = OBSConnection(
        hass,
        host=entry.data["host"],
        port=entry.data["port"],
        password=entry.data.get("password", ""),
    )

    try:
        await connection.async_connect()
    except Exception as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="connection_failed",
            translation_placeholders={"host": entry.data["host"], "error": str(err)},
        ) from err

    coordinator = OBSCoordinator(hass, connection)
    connection.coordinator = coordinator
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = OBSRuntimeData(
        connection=connection,
        coordinator=coordinator,
    )

    _migrate_device_name(hass, entry)

    entry.async_on_unload(entry.add_update_listener(async_options_updated))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


def _migrate_device_name(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Rename devices created before the configurable device name existed.

    Only corrects names that still match the legacy "OBS Studio (host)" default
    so user-customized device names are never overwritten.
    """
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_device_by_identifier((DOMAIN, entry.entry_id), entry.entry_id)
    if device is None or device.name == get_device_name(entry):
        return
    if device.name is None or device.name.startswith("OBS Studio ("):
        dev_reg.async_update_device(device.id, name=get_device_name(entry))


async def async_options_updated(hass: HomeAssistant, entry: OBSConfigEntry) -> None:
    """Reload the integration when options are changed."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: OBSConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        connection = entry.runtime_data.connection
        # Stop late OBS events from triggering a refresh that would reconnect.
        connection.coordinator = None
        await entry.runtime_data.coordinator.async_shutdown()
        await connection.async_disconnect()
    return unload_ok
