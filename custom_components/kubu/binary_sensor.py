"""Binary sensors: door, lock, tamper, battery low, vibration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import STATE_ON, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import KubuConfigEntry
from .const import LOCK_LOGICS, TAMPER_LOGICS
from .coordinator import SensorState
from .entity import KubuEntity


@dataclass(frozen=True, kw_only=True)
class KubuBinaryDescription(BinarySensorEntityDescription):
    value_fn: Callable[[SensorState], bool | None]
    supported_fn: Callable[[int, str | None], bool] = lambda logic, cls: True


def _state(s: SensorState) -> str | None:
    return s.frame.state if s.frame else None


DESCRIPTIONS: tuple[KubuBinaryDescription, ...] = (
    KubuBinaryDescription(
        key="door",
        name=None,
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda s: None if _state(s) is None else _state(s) == "open",
    ),
    KubuBinaryDescription(
        key="lock",
        translation_key="lock",
        device_class=BinarySensorDeviceClass.LOCK,  # on = unlocked
        value_fn=lambda s: None if _state(s) is None else _state(s) != "locked",
        supported_fn=lambda logic, cls: logic in LOCK_LOGICS or cls == "door",
    ),
    KubuBinaryDescription(
        key="tamper",
        device_class=BinarySensorDeviceClass.TAMPER,
        value_fn=lambda s: None if _state(s) is None else _state(s) == "tampered",
        supported_fn=lambda logic, cls: logic in TAMPER_LOGICS or cls == "door",
    ),
    KubuBinaryDescription(
        key="battery_low",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: (
            None if s.battery_level is None else s.battery_level in ("low", "critical")
        ),
    ),
    KubuBinaryDescription(
        key="vibration",
        device_class=BinarySensorDeviceClass.VIBRATION,
        entity_registry_enabled_default=False,
        value_fn=lambda s: None if s.frame is None else s.frame.vibration,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: KubuConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    runtime = entry.runtime_data
    entities = []
    for mac, sensor in runtime.sensors.items():
        logic, cls = int(sensor.get("type") or 0), sensor.get("sensorClass")
        entities += [
            KubuBinarySensor(runtime, mac, d)
            for d in DESCRIPTIONS
            if d.supported_fn(logic, cls)
        ]
    async_add_entities(entities)


class KubuBinarySensor(KubuEntity, BinarySensorEntity, RestoreEntity):
    entity_description: KubuBinaryDescription
    _restored: bool | None = None

    async def async_added_to_hass(self) -> None:
        if (last := await self.async_get_last_state()) is not None and last.state in (
            "on",
            "off",
        ):
            self._restored = last.state == STATE_ON
        await super().async_added_to_hass()

    def _current_value(self) -> bool | None:
        return self.is_on

    @property
    def is_on(self) -> bool | None:
        value = self.entity_description.value_fn(self.sensor_state)
        return self._restored if value is None else value
