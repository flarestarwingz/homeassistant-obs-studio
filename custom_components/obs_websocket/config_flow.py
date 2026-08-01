"""Config flow for OBS WebSocket."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector

from .const import (
    DEFAULT_DEVICE_NAME,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_INCLUDE_SCENE_SOURCES,
    DEFAULT_SCENE_ITEM_MODE,
    DOMAIN,
    OPTION_DEVICE_NAME,
    OPTION_INCLUDE_SCENE_SOURCES,
    OPTION_SCENE_ITEM_MODE,
    OPTION_SCENE_ITEM_SCENES,
    SCENE_ITEM_MODE_ALL,
    SCENE_ITEM_MODE_SOURCES,
)


async def _test_connection(hass: HomeAssistant, host: str, port: int, password: str) -> None:
    """Test that we can connect to OBS WebSocket. Raises on failure."""
    import obsws_python as obs

    def _connect() -> None:
        kwargs: dict[str, Any] = {"host": host, "port": port, "timeout": 5}
        if password:
            kwargs["password"] = password
        client = obs.ReqClient(**kwargs)
        client.get_version()
        client.disconnect()

    await hass.async_add_executor_job(_connect)


async def _get_scene_names(hass: HomeAssistant, host: str, port: int, password: str) -> list[str]:
    """Fetch the list of scene names from OBS. Returns empty list on failure."""
    import obsws_python as obs

    def _fetch() -> list[str]:
        kwargs: dict[str, Any] = {"host": host, "port": port, "timeout": 5}
        if password:
            kwargs["password"] = password
        client = obs.ReqClient(**kwargs)
        try:
            resp = client.get_scene_list()
            return [
                s["sceneName"] if isinstance(s, dict) else s.scene_name
                for s in (resp.scenes or [])
            ]
        finally:
            client.disconnect()

    try:
        return await hass.async_add_executor_job(_fetch)
    except Exception:
        return []


class OBSWebSocketConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OBS WebSocket."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return OBSWebSocketOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input["host"]
            port = user_input["port"]
            password = user_input.get("password", "")

            try:
                await _test_connection(self.hass, host, port, password)
            except Exception:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(f"{host}:{port}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=host,
                    data={"host": host, "port": port, "password": password},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("host", default=DEFAULT_HOST): str,
                    vol.Required("port", default=DEFAULT_PORT): int,
                    vol.Optional("password", default=""): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle reauthorization when password changes."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle reauth confirmation."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            password = user_input.get("password", "")
            try:
                await _test_connection(
                    self.hass,
                    reauth_entry.data["host"],
                    reauth_entry.data["port"],
                    password,
                )
            except Exception:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data={**reauth_entry.data, "password": password},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Optional("password", default=""): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle reconfiguration."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            host = user_input["host"]
            port = user_input["port"]
            password = user_input.get("password", "")

            try:
                await _test_connection(self.hass, host, port, password)
            except Exception:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(f"{host}:{port}")
                self._abort_if_unique_id_configured()
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data={"host": host, "port": port, "password": password},
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required("host", default=reconfigure_entry.data.get("host", DEFAULT_HOST)): str,
                    vol.Required("port", default=reconfigure_entry.data.get("port", DEFAULT_PORT)): int,
                    vol.Optional("password", default=reconfigure_entry.data.get("password", "")): str,
                }
            ),
            errors=errors,
        )


class OBSWebSocketOptionsFlow(config_entries.OptionsFlow):
    """Handle OBS WebSocket options."""

    # Display labels used as schema keys. Because some environments do not
    # apply strings.json translations, friendly labels are used directly as
    # the schema keys and mapped back to the internal option keys on save.
    _FIELD_DEVICE_NAME = "Device name"
    _FIELD_SCENE_ITEM_MODE = "Scene item switches"
    _FIELD_SCENE_ITEM_SCENES = "Scenes to include"
    _FIELD_INCLUDE_SCENE_SOURCES = "Include nested scenes"

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the options step."""
        if user_input is not None:
            data = {
                OPTION_DEVICE_NAME: user_input.get(
                    self._FIELD_DEVICE_NAME, DEFAULT_DEVICE_NAME
                ),
                OPTION_SCENE_ITEM_MODE: user_input.get(
                    self._FIELD_SCENE_ITEM_MODE, DEFAULT_SCENE_ITEM_MODE
                ),
                OPTION_SCENE_ITEM_SCENES: user_input.get(
                    self._FIELD_SCENE_ITEM_SCENES, []
                ),
                OPTION_INCLUDE_SCENE_SOURCES: user_input.get(
                    self._FIELD_INCLUDE_SCENE_SOURCES, DEFAULT_INCLUDE_SCENE_SOURCES
                ),
            }
            return self.async_create_entry(title="", data=data)

        scenes = await _get_scene_names(
            self.hass,
            self.config_entry.data["host"],
            self.config_entry.data["port"],
            self.config_entry.data.get("password", ""),
        )

        stored = self.config_entry.options.get(OPTION_SCENE_ITEM_SCENES, [])
        if not isinstance(stored, list):
            stored = [stored] if stored else []
        default_scenes = [str(s) for s in stored]

        if scenes:
            # Keep only stored selections that still exist as options.
            default_scenes = [s for s in default_scenes if s in scenes]
        else:
            # OBS may be unreachable; keep previously selected scenes as the
            # only options so the form still renders.
            scenes = default_scenes

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        self._FIELD_DEVICE_NAME,
                        default=self.config_entry.options.get(
                            OPTION_DEVICE_NAME, DEFAULT_DEVICE_NAME
                        ),
                    ): str,
                    vol.Optional(
                        self._FIELD_SCENE_ITEM_MODE,
                        default=self.config_entry.options.get(
                            OPTION_SCENE_ITEM_MODE, DEFAULT_SCENE_ITEM_MODE
                        ),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(
                                    value=SCENE_ITEM_MODE_SOURCES,
                                    label="One switch per source (active scene)",
                                ),
                                selector.SelectOptionDict(
                                    value=SCENE_ITEM_MODE_ALL,
                                    label="One switch per scene item",
                                ),
                            ]
                        )
                    ),
                    vol.Optional(
                        self._FIELD_SCENE_ITEM_SCENES,
                        default=default_scenes,
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=scenes,
                            multiple=True,
                            custom_value=False,
                        )
                    ),
                    vol.Optional(
                        self._FIELD_INCLUDE_SCENE_SOURCES,
                        default=self.config_entry.options.get(
                            OPTION_INCLUDE_SCENE_SOURCES, DEFAULT_INCLUDE_SCENE_SOURCES
                        ),
                    ): selector.BooleanSelector(),
                }
            ),
        )
