"""Listen for Kubu adverts and keep the latest decoded state per sensor."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util import dt as dt_util

from .const import MIN_VALID_BATTERY_MV, normalize_mac, signal_update
from .protocol import CLASS_NAMES, MANUFACTURER_ID, KubuFrame, parse

_LOGGER = logging.getLogger(__name__)


@dataclass
class SensorState:
    """Latest known values for one sensor."""

    frame: KubuFrame | None = None
    battery_mv: int | None = None
    battery_level: str | None = None
    last_seen: datetime | None = None
    rssi: int | None = None
    last_payload: bytes | None = field(default=None, repr=False)


class KubuRuntime:
    """Owns the Bluetooth callback for one config entry."""

    def __init__(
        self, hass: HomeAssistant, entry_id: str, sensors: list[dict[str, Any]]
    ) -> None:
        self.hass = hass
        self.entry_id = entry_id
        self.sensors = {normalize_mac(s["mac"]): s for s in sensors}
        self.states = {mac: SensorState() for mac in self.sensors}
        # Advertised address -> configured sensor MAC, for sensors whose serial
        # (sNo) is not the address Home Assistant sees.
        self.aliases: dict[str, str] = {}
        self._unmatched_logged: set[str] = set()

    @callback
    def async_start(self) -> bluetooth.CALLBACK_TYPE:
        """Register for adverts; returns the unregister callback."""
        return bluetooth.async_register_callback(
            self.hass,
            self._async_on_advert,
            bluetooth.BluetoothCallbackMatcher(
                manufacturer_id=MANUFACTURER_ID, connectable=False
            ),
            bluetooth.BluetoothScanningMode.ACTIVE,
        )

    def _match_by_key(self, adv_mac: str, payload: bytes) -> str | None:
        """Find the sensor whose key decrypts this payload into a plausible frame."""
        claimed = set(self.aliases.values())
        for mac, sensor in self.sensors.items():
            if mac in claimed or self.states[mac].last_seen is not None:
                continue
            try:
                frame = parse(
                    payload,
                    sensor["dpKey"],
                    int(sensor.get("type") or 0),
                    sensor.get("sensorClass"),
                )
            except ValueError:
                return None
            if (
                frame.frame_type in (0x0F, 0x10)
                and frame.class_id in CLASS_NAMES
                and 0 < frame.battery_mv <= 3700
            ):
                _LOGGER.warning(
                    "Kubu sensor %s is advertising as %s; matched by its key",
                    mac,
                    adv_mac,
                )
                self.aliases[adv_mac] = mac
                return mac
        return None

    @callback
    def _async_on_advert(
        self,
        info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        payload = info.manufacturer_data.get(MANUFACTURER_ID)
        if payload is None:
            return
        adv_mac = normalize_mac(info.address)
        _LOGGER.debug(
            "Kubu advert from %s rssi=%s raw=%s",
            info.address,
            info.rssi,
            bytes(payload).hex(),
        )
        mac = self.aliases.get(adv_mac, adv_mac)
        if mac not in self.sensors:
            mac = self._match_by_key(adv_mac, bytes(payload))
            if mac is None:
                if adv_mac not in self._unmatched_logged:
                    self._unmatched_logged.add(adv_mac)
                    _LOGGER.warning(
                        "Kubu advert from %s doesn't match any configured sensor (%s)",
                        info.address,
                        ", ".join(self.sensors),
                    )
                return
        sensor = self.sensors[mac]
        state = self.states[mac]
        state.rssi = info.rssi
        if payload == state.last_payload:
            return
        try:
            frame = parse(
                bytes(payload),
                sensor["dpKey"],
                int(sensor.get("type") or 0),
                sensor.get("sensorClass"),
            )
        except ValueError as err:
            _LOGGER.debug("Ignoring Kubu advert from %s: %s", info.address, err)
            return
        state.last_payload = payload
        state.frame = frame
        state.last_seen = dt_util.utcnow()
        if frame.battery_mv >= MIN_VALID_BATTERY_MV:
            state.battery_mv = frame.battery_mv
            state.battery_level = frame.battery_level
        _LOGGER.debug(
            "Kubu %s: %s (status 0x%04X, counter %d)",
            mac,
            frame.state,
            frame.status_word,
            frame.counter,
        )
        async_dispatcher_send(self.hass, signal_update(self.entry_id, mac))
