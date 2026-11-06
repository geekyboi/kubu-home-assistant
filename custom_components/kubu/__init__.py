"""Kubu Smart door and window sensors over local Bluetooth."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_SENSORS
from .coordinator import KubuRuntime

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

type KubuConfigEntry = ConfigEntry[KubuRuntime]


async def async_setup_entry(hass: HomeAssistant, entry: KubuConfigEntry) -> bool:
    """Set up from a config entry."""
    runtime = KubuRuntime(hass, entry.entry_id, entry.data[CONF_SENSORS])
    entry.runtime_data = runtime
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(runtime.async_start())
    return True


async def async_unload_entry(hass: HomeAssistant, entry: KubuConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
