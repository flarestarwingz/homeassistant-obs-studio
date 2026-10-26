"""Binary sensors for OBS performance monitoring."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import OBSConfigEntry
from .performance_sensor import OBSPerformanceWarning


async def async_setup_entry(
    hass: HomeAssistant, entry: OBSConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Register the consolidated rendering/encoding performance warning."""
    performance = getattr(entry.runtime_data, "performance", None)
    if performance is not None:
        async_add_entities([OBSPerformanceWarning(performance, entry)])
