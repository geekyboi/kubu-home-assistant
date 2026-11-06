"""Decrypted frames captured from Ollie's RetroPro (unlock, open, close, lock, twice)."""

import sys
from pathlib import Path

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

sys.path.insert(0, str(Path(__file__).parents[1] / "custom_components" / "kubu"))
from protocol import parse

KEY = "00112233445566778899aabbccddeeff"
CAPTURE = [
    ("10010adaae93f4d7fffa000010ff0428", "closed", 2778),
    ("10010a65ae941ba5ffff000010ff0428", "open", 2661),
    ("10010119ae956567fffa000010ff0428", "closed", 281),
    ("10010a84ae965ce7ffea000010ff0428", "locked", 2692),
    ("10010aecae977f2bfffa000010ff0428", "closed", 2796),
    ("10010a5dae987a3fffff000010ff0428", "open", 2653),
    ("10010114ae99281afffa000010ff0428", "closed", 276),
    ("10010a2dae9a1c00ffea000010ff0428", "locked", 2605),
]


def enc(plain_hex: str) -> bytes:
    e = Cipher(algorithms.AES(bytes.fromhex(KEY)), modes.ECB()).encryptor()
    return e.update(bytes.fromhex(plain_hex)) + e.finalize()


def test_retropro_capture():
    counters = []
    for plain, state, mv in CAPTURE:
        f = parse(enc(plain), KEY, 8, "retroPro")
        assert (f.state, f.battery_mv, f.class_id, f.frame_type) == (state, mv, 1, 0x10)
        assert not f.vibration
        counters.append(f.counter)
    assert counters == list(range(counters[0], counters[0] + len(CAPTURE)))
