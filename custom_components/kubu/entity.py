"""Base entity for Kubu sensors."""

from __future__ import annotations

from typing import Any

from homeassistant.core import callback
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity, EntityDescription

from .const import DOMAIN, MANUFACTURER, signal_update
from .coordinator import KubuRuntime, SensorState


def _pretty_mac(mac: str) -> str:
    return ":".join(mac[i : i + 2] for i in range(0, 12, 2))


class KubuEntity(Entity):
    """One value of one Kubu sensor, pushed from Bluetooth adverts."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _last_written: Any = None

    def __init__(
        self, runtime: KubuRuntime, mac: str, description: EntityDescription
    ) -> None:
        self.runtime = runtime
        self.mac = mac
        self.entity_description = description
        sensor: dict[str, Any] = runtime.sensors[mac]
        self._attr_unique_id = f"{mac}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mac)},
            connections={(CONNECTION_BLUETOOTH, _pretty_mac(mac))},
            name=sensor.get("devAlias") or sensor.get("name") or f"Kubu {mac[-4:]}",
            manufacturer=MANUFACTURER,
            model=sensor.get("productType") or sensor.get("sensorClass"),
            sw_version=sensor.get("fwVer"),
            hw_version=sensor.get("hwRev"),
        )

    @property
    def sensor_state(self) -> SensorState:
        return self.runtime.states[self.mac]

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._last_written = self._current_value()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                signal_update(self.runtime.entry_id, self.mac),
                self._handle_update,
            )
        )

    def _current_value(self) -> Any:
        """The value this entity reports; writes are skipped while it is unchanged."""
        raise NotImplementedError

    def _should_write(self, previous: Any, current: Any) -> bool:
        return current != previous

    @callback
    def _handle_update(self) -> None:
        # Sensors re-broadcast about every 30 s with a new counter even when nothing
        # changed, so only write (and log activity) when this entity's value moves.
        current = self._current_value()
        if not self._should_write(self._last_written, current):
            return
        self._last_written = current
        self.async_write_ha_state()
