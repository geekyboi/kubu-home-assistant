"""Listen for Kubu adverts and keep the latest decoded state per sensor."""

from __future__ import annotations

import inspect
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

# Kubu sensors keep their latest state in the scan response, which only an
# active scan fetches. HA 2026.6+ scanners default to "Auto" (passive unless an
# integration asks), so ask for the tightest active cadence HA allows for each
# sensor: a 35 s active window every 60 s. Scanners set to Active ignore this.
ACTIVE_SCAN_INTERVAL = 60.0
ACTIVE_SCAN_DURATION = 35.0
_SUPPORTS_ACTIVE_REQUESTS = (
    "scan_interval" in inspect.signature(bluetooth.async_register_callback).parameters
)


def _colon_mac(mac: str) -> str:
    return ":".join(mac[i : i + 2] for i in range(0, 12, 2))


@dataclass
class SensorState:
    """Latest known values for one sensor."""

    frame: KubuFrame | None = None
    battery_mv: int | None = None
    battery_level: str | None = None
    last_seen: datetime | None = None
    rssi: int | None = None
    last_payload: bytes | None = field(default=None, repr=False)


@callback
def _ignore_advert(
    info: bluetooth.BluetoothServiceInfoBleak, change: bluetooth.BluetoothChange
) -> None:
    """Placeholder callback: these registrations exist only to request active scans."""


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
        self._cancels: list[bluetooth.CALLBACK_TYPE] = []

    @callback
    def async_start(self) -> bluetooth.CALLBACK_TYPE:
        """Register for adverts; returns the unregister callback."""
        self._cancels = cancels = [
            bluetooth.async_register_callback(
                self.hass,
                self._async_on_advert,
                bluetooth.BluetoothCallbackMatcher(
                    manufacturer_id=MANUFACTURER_ID, connectable=False
                ),
                bluetooth.BluetoothScanningMode.ACTIVE,
            )
        ]
        if _SUPPORTS_ACTIVE_REQUESTS:
            cancels += [self._async_request_active(mac) for mac in self.sensors]
        else:
            _LOGGER.debug(
                "This Home Assistant can't request active scans; set scanners to Active"
            )

        @callback
        def _cancel() -> None:
            for cancel in self._cancels:
                cancel()
            self._cancels.clear()

        return _cancel

    @callback
    def _async_request_active(self, mac: str) -> bluetooth.CALLBACK_TYPE:
        """Ask Auto-mode scanners to actively scan this sensor's address."""
        return bluetooth.async_register_callback(
            self.hass,
            _ignore_advert,
            bluetooth.BluetoothCallbackMatcher(
                address=_colon_mac(mac), connectable=False
            ),
            bluetooth.BluetoothScanningMode.ACTIVE,
            scan_interval=ACTIVE_SCAN_INTERVAL,
            scan_duration=ACTIVE_SCAN_DURATION,
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
                if _SUPPORTS_ACTIVE_REQUESTS:
                    self._cancels.append(self._async_request_active(adv_mac))
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
