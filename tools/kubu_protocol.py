"""Decode Kubu BLE advertisements (manufacturer ID 0x0DCF, AES-128-ECB)."""

from __future__ import annotations

from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

MANUFACTURER_ID = 3535  # 0x0DCF

CLASS_NAMES = {1: "RetroPro", 2: "Window", 3: "Door", 4: "RetroOne", 5: "RetroUltra"}
DOOR_STATES = {0xFF01: "unlocked", 0xFF10: "locked", 0xFF11: "open", 0xFFFF: "tampered"}


@dataclass
class KubuFrame:
    raw: bytes
    frame_type: int
    battery_mv: int
    battery_level: str
    status_word: int
    state: str
    vibration: bool

    @property
    def is_setup_frame(self) -> bool:
        return self.frame_type == 0x0F


def decrypt(payload: bytes, key_hex: str) -> bytes:
    if len(payload) != 16:
        raise ValueError(f"expected 16-byte payload, got {len(payload)}")
    dec = Cipher(algorithms.AES(bytes.fromhex(key_hex)), modes.ECB()).decryptor()
    return dec.update(payload) + dec.finalize()


def battery_level(mv: int) -> str:
    if mv == 0:
        return "unknown"
    if mv <= 2134:
        return "critical"
    if mv < 2181:
        return "low"
    return "ok"


def _fields(v: int) -> tuple[int, int, int, int]:
    i = v & 63
    return i, v & 3, (i >> 2) & 3, (i >> 4) & 3


def sensor_state(status: int, logic: int, sensor_class: str | None = None) -> str:
    """Port of BLEScannerService.evaluateSensorState / evaluateDoorSensorState."""
    if sensor_class == "door":
        return DOOR_STATES.get(status, "unknown")
    if logic == 2:
        return "open" if (status & 63) in (55, 59, 63) else "closed"
    if logic == 3:
        return "open" if (status >> 6) & 1 else "closed"
    if logic == 8:
        i = status & 63
        if i in (42, 43, 46):
            return "locked"
        if i in (58, 59, 62):
            return "closed"
        return "open" if i == 63 else "tampered"
    if logic in (40, 41):
        return {1: "open", 2: "closed", 3: "secure"}.get(status & 0xFF, "unknown")
    if logic == 4:
        i, a, b, c = _fields(status)
        if i in (42, 21):
            return "tampered"
        if i == 63:
            return "open"
        t = (a == 3, b == 3, c == 3)
        if t in {
            (True, False, True),
            (True, True, False),
            (True, False, False),
            (False, False, False),
            (False, True, False),
        }:
            return "closed"
        if t in {(False, False, True), (False, True, True)}:
            return "secure"
        return "tampered"
    if logic in (5, 11, 12):
        i, a, b, c = _fields(status)
        if i in (42, 21):
            return "tampered"
        if i == 63:
            return "open"
        t = (a == 3, b == 3, c == 3)
        if t in {
            (True, False, True),
            (False, True, True),
            (False, False, True),
            (False, False, False),
            (False, True, False),
        }:
            return "closed"
        if t in {(True, False, False), (True, True, False)}:
            return "secure"
        return "tampered"
    return "open"  # app default for unknown logic types


def parse(
    payload: bytes, key_hex: str, logic: int, sensor_class: str | None = None
) -> KubuFrame:
    d = decrypt(payload, key_hex)
    mv = int.from_bytes(d[2:4], "big")
    status = int.from_bytes(d[8:10], "big")
    return KubuFrame(
        raw=d,
        frame_type=d[0],
        battery_mv=mv,
        battery_level=battery_level(mv),
        status_word=status,
        state=sensor_state(status, logic, sensor_class),
        vibration=d[0] == 0x10 and d[10] in (0x10, 0x20),
    )
