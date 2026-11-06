"""Listen for Kubu adverts and decode them with keys from kubu_keys.json.

Usage: python kubu_scan.py [seconds]   (default 120; open and close a door meanwhile)

macOS hides real MAC addresses, so on a Mac every key is tried and a decode is
shown when exactly one key gives a plausible frame. On Linux/HA the MAC is used.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from bleak import BleakScanner
from kubu_protocol import MANUFACTURER_ID, parse

KEYS = json.loads(Path(__file__).with_name("kubu_keys.json").read_text())
BY_MAC = {n["sNo"].upper(): n for n in KEYS}
last: dict[str, bytes] = {}


def plausible(f) -> bool:
    return f.frame_type in (0x0F, 0x10) or 1800 <= f.battery_mv <= 3600


def on_adv(device, adv) -> None:
    payload = adv.manufacturer_data.get(MANUFACTURER_ID)
    if payload is None or last.get(device.address) == payload:
        return
    last[device.address] = payload
    mac = device.address.replace(":", "").upper()
    nodes = [BY_MAC[mac]] if mac in BY_MAC else KEYS
    hits = []
    for n in nodes:
        try:
            f = parse(bytes(payload), n["dpKey"], n["type"], n["sensorClass"])
        except ValueError as e:
            print(f"{device.address}: {e} raw={payload.hex()}")
            return
        if len(nodes) == 1 or plausible(f):
            hits.append((n, f))
    print(f"\n{device.address} rssi={adv.rssi} raw={payload.hex()}")
    if not hits:
        print("  no key gave a plausible decode")
    for n, f in hits:
        print(
            f"  {n.get('devAlias') or n['sNo']}: state={f.state} battery={f.battery_mv}mV ({f.battery_level})"
            f" type=0x{f.frame_type:02X} status=0x{f.status_word:04X} vib={f.vibration} dec={f.raw.hex()}"
        )


async def main(seconds: int) -> None:
    async with BleakScanner(on_adv):
        print(f"Scanning for {seconds}s... open and close a door or window now.")
        await asyncio.sleep(seconds)


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 120))
