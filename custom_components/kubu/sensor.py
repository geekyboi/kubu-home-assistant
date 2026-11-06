"""Sensors: raw state, battery voltage, last seen, signal strength."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfElectricPotential,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import KubuConfigEntry
from .coordinator import SensorState
from .entity import KubuEntity

STATE_OPTIONS = [
    "open",
    "closed",
    "locked",
    "unlocked",
    "secure",
    "tampered",
    "unknown",
]


@dataclass(frozen=True, kw_only=True)
class KubuSensorDescription(SensorEntityDescription):
    value_fn: Callable[[SensorState], Any]


DESCRIPTIONS: tuple[KubuSensorDescription, ...] = (
    KubuSensorDescription(
        key="state",
        translation_key="state",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_OPTIONS,
        value_fn=lambda s: s.frame.state if s.frame else None,
    ),
    KubuSensorDescription(
        key="battery_voltage",
        translation_key="battery_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: s.battery_mv,
    ),
    KubuSensorDescription(
        key="last_seen",
        translation_key="last_seen",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: s.last_seen,
    ),
    KubuSensorDescription(
        key="rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda s: s.rssi,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: KubuConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    runtime = entry.runtime_data
    async_add_entities(
        KubuSensor(runtime, mac, d) for mac in runtime.sensors for d in DESCRIPTIONS
    )


class KubuSensor(KubuEntity, RestoreSensor):
    entity_description: KubuSensorDescription
    _restored: Any = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if self.entity_description.key != "rssi" and (
            data := await self.async_get_last_sensor_data()
        ):
            self._restored = data.native_value

    @property
    def native_value(self) -> str | int | datetime | None:
        value = self.entity_description.value_fn(self.sensor_state)
        return self._restored if value is None else value
