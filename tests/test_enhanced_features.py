"""Tests of enhanced OBS WebSocket entities and credential protections."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.obs_websocket.button import OBSRecordToggleButton, OBSVirtualCamToggleButton
from custom_components.obs_websocket.const import DOMAIN
from custom_components.obs_websocket.select import OBSSceneSelect
from custom_components.obs_websocket.sensor import OBSRecordingSensor, OBSStreamServiceSensor, OBSVirtualCamSensor
from custom_components.obs_websocket.switch import OBSSceneItemSwitch

from .conftest import MOCK_CONFIG, MOCK_HOST, MOCK_PORT


def _entities(hass: HomeAssistant):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_HOST,
        data=MOCK_CONFIG.copy(),
        unique_id=f"{MOCK_HOST}:{MOCK_PORT}",
    )
    coordinator = MagicMock()
    coordinator.hass = hass
    coordinator.connection.host = MOCK_HOST
    coordinator.connection.async_toggle_record = AsyncMock()
    coordinator.connection.async_toggle_virtual_cam = AsyncMock()
    coordinator.connection.async_set_current_program_scene = AsyncMock()
    coordinator.connection.async_set_scene_item_enabled = AsyncMock()
    coordinator.async_request_refresh = AsyncMock()
    coordinator.data = {
        "service_settings": SimpleNamespace(
            stream_service_type="rtmp_common",
            stream_service_settings={
                "key": "DO_NOT_EXPOSE",
                "password": "DO_NOT_EXPOSE",
                "provider_secret": "DO_NOT_EXPOSE",
            },
        ),
        "recording": False,
        "virtual_cam_active": False,
        "current_program_scene": "Main",
        "scene_list": ["Main", "Break"],
        "scene_items": {"Main": [{"id": 10, "name": "Webcam", "enabled": True}]},
    }
    return coordinator, entry


async def test_stream_service_never_exposes_raw_settings(hass: HomeAssistant) -> None:
    coordinator, entry = _entities(hass)
    sensor = OBSStreamServiceSensor(coordinator, entry)
    assert sensor.native_value == "rtmp_common"
    assert sensor.extra_state_attributes == {}


@pytest.mark.parametrize(
    "field,entity,expected",
    [
        ("recording", OBSRecordingSensor, "recording"),
        ("virtual_cam_active", OBSVirtualCamSensor, "active"),
    ],
)
async def test_output_state_distinguishes_unknown(hass: HomeAssistant, field, entity, expected) -> None:
    coordinator, entry = _entities(hass)
    sensor = entity(coordinator, entry)
    coordinator.data[field] = None
    assert sensor.native_value is None
    coordinator.data[field] = True
    assert sensor.native_value == expected


@pytest.mark.parametrize(
    "button,method",
    [
        (OBSRecordToggleButton, "async_toggle_record"),
        (OBSVirtualCamToggleButton, "async_toggle_virtual_cam"),
    ],
)
async def test_toggle_buttons_refresh(hass: HomeAssistant, button, method) -> None:
    coordinator, entry = _entities(hass)
    entity = button(coordinator, entry)
    await entity.async_press()
    getattr(coordinator.connection, method).assert_awaited_once_with()
    coordinator.async_request_refresh.assert_awaited_once_with()


async def test_scene_selection_changes_scene(hass: HomeAssistant) -> None:
    coordinator, entry = _entities(hass)
    entity = OBSSceneSelect(coordinator, entry)
    assert entity.current_option == "Main"
    assert entity.options == ["Main", "Break"]
    await entity.async_select_option("Break")
    coordinator.connection.async_set_current_program_scene.assert_awaited_once_with("Break")
    coordinator.async_request_refresh.assert_awaited_once_with()


async def test_source_switch_resolves_active_scene(hass: HomeAssistant) -> None:
    coordinator, entry = _entities(hass)
    entity = OBSSceneItemSwitch(coordinator, entry, source_name="Webcam")
    assert entity.is_on is True
    await entity.async_turn_off()
    coordinator.connection.async_set_scene_item_enabled.assert_awaited_once_with("Main", 10, False)
    coordinator.async_request_refresh.assert_awaited_once_with()


async def test_recreated_scene_item_resolves_new_id(hass: HomeAssistant) -> None:
    coordinator, entry = _entities(hass)
    entity = OBSSceneItemSwitch(coordinator, entry, source_name="Webcam", scene_name="Main", item_id=5)
    assert entity.is_on is True
    await entity.async_turn_off()
    coordinator.connection.async_set_scene_item_enabled.assert_awaited_once_with("Main", 10, False)


async def test_ambiguous_recreated_item_not_toggled(hass: HomeAssistant) -> None:
    coordinator, entry = _entities(hass)
    coordinator.data["scene_items"]["Main"].append({"id": 11, "name": "Webcam", "enabled": True})
    entity = OBSSceneItemSwitch(coordinator, entry, source_name="Webcam", scene_name="Main", item_id=5)
    with pytest.raises(HomeAssistantError):
        await entity.async_turn_off()
    coordinator.connection.async_set_scene_item_enabled.assert_not_awaited()
