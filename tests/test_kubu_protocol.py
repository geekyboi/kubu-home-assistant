import sys
from pathlib import Path

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
from kubu_protocol import battery_level, parse, sensor_state

KEY = "00112233445566778899aabbccddeeff"


def enc(plain: bytes) -> bytes:
    e = Cipher(algorithms.AES(bytes.fromhex(KEY)), modes.ECB()).encryptor()
    return e.update(plain) + e.finalize()


def frame(status: int, mv: int = 3000, b0: int = 0x01, b10: int = 0) -> bytes:
    p = bytearray(16)
    p[0], p[2:4], p[8:10], p[10] = (
        b0,
        mv.to_bytes(2, "big"),
        status.to_bytes(2, "big"),
        b10,
    )
    return enc(bytes(p))


def test_door_states():
    assert parse(frame(0xFF11), KEY, 0, "door").state == "open"
    assert parse(frame(0xFF10), KEY, 0, "door").state == "locked"
    assert parse(frame(0xFFFF), KEY, 0, "door").state == "tampered"


def test_battery():
    f = parse(frame(0xFF11, mv=2150), KEY, 0, "door")
    assert f.battery_mv == 2150 and f.battery_level == "low"
    assert battery_level(0) == "unknown" and battery_level(2000) == "critical"


def test_logic_variants():
    assert sensor_state(63, 2) == "open" and sensor_state(0, 2) == "closed"
    assert sensor_state(1 << 6, 3) == "open"
    assert sensor_state(42, 8) == "locked" and sensor_state(63, 8) == "open"
    assert sensor_state(2, 41) == "closed" and sensor_state(3, 40) == "secure"
    assert sensor_state(63, 4) == "open" and sensor_state(21, 5) == "tampered"
    assert (
        sensor_state(0b110000, 4) == "secure" and sensor_state(0b001100, 4) == "closed"
    )
    assert sensor_state(0b000011, 5) == "secure"


def test_vibration_flag():
    assert parse(frame(0, b0=0x10, b10=0x20), KEY, 2).vibration
    assert not parse(frame(0, b0=0x01, b10=0x20), KEY, 2).vibration
