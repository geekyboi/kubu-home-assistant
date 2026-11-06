# Kubu BLE protocol findings

Worked out for interoperability, so that Kubu sensors you own can be read locally in
Home Assistant. It describes the data format the sensors broadcast and the account data the
official app uses; no Kubu code is included in this repository.

## Headline

Day-to-day status needs **no connection**. Sensors broadcast their state in BLE
advertisements, and the official app only listens passively. That suits Home Assistant
well: a passive Bluetooth integration with no pairing and no GATT.

## Advertisement format

- Filter: manufacturer-specific data, company ID **3535 (0x0DCF)**.
- Payload: 16 bytes, encrypted with **AES-128-ECB, no padding**.
- Key: per-sensor **`dpKey`** (hex string, 16 bytes).
- Sensor identity: BLE MAC address with colons stripped == the node's `sNo`.
- The app drops duplicates: it only processes a decrypted payload that differs from the last one for that MAC.

## Decrypted payload (byte offsets; app works on hex string, so hex offset = 2x)

| Bytes | Meaning |
|---|---|
| 0 | Frame type. `0x0F` = setup/discovery frame; `0x10` = SureShield (armed/attack) frame |
| 1 | Class identifier in setup frames: 1 RetroPro, 2 Window, 3 Door, 4 RetroOne, 5 RetroUltra |
| 2-3 | Battery voltage, big-endian mV (0 = unknown; <=2134 critical; 2135-2180 low; >=2600 ok) |
| 8-9 | Raw status word, decoded per sensor `type` ("logic") below |
| 10 | Vibration/attack: `0x10` or `0x20` = vibration alert (with byte 0 = `0x10`) |
| 10-15 | In setup frames: sensor MAC |

### Status decode

`sensorClass == "door"`: bytes 8-9 as hex: `FF01` unlocked, `FF10` locked, `FF11` open, `FFFF` tampered.

Otherwise by `type` (v = bytes 8-9 as int):
- 2: `v & 63` in {55,59,63} -> open, else closed
- 3: bit 6 set -> open, else closed
- 4, 5/11/12: 2-bit fields a=v&3, b=(v>>2)&3, c=(v>>4)&3 over `v&63`; 63 open; 42/21 tampered; otherwise closed/secure by field pattern (see `sensor_state` in `protocol.py`)
- 8: {42,43,46} locked, {58,59,62} closed, 63 open, else tampered
- 40/41: byte 9: 1 open, 2 closed, 3 secure
- anything else: open

Which `type` the Anywhere PRO uses is set by the cloud per node. To be confirmed from your account (step 2).

## The one catch: the key

`dpKey` is not derived on the phone. The app gets it from Kubu's cloud when the
sensor is added (`POST /nodes` whitelist check by serial) and again from the
dashboard (`GET /view/rooms?homeId=...` -> `bleNodes[]`, fields `sNo`, `dpKey`,
`type`, `sensorClass`, `productType`). Base URL `https://api-green.kubusmart.com`.

So the plan needs a one-time key fetch. After that, everything runs locally:
1. Config flow logs in to Kubu once and reads `bleNodes` (sNo, dpKey, type, class), or
2. You capture the key yourself (for example with mitmproxy on the iPhone) and paste it in.

## Confirmed on Ollie's RetroPro (6 Nov 2026)

Sequence unlock → open → close → lock, twice. Every advert decrypted with the cloud dpKey.

| Decrypted frame | Status | Meaning |
|---|---|---|
| `10 01 0ada ae93 f4d7 fffa 0000 10ff 0428` | 0xFFFA (58) | shut, unlocked ("closed") |
| `10 01 0a65 ae94 1ba5 ffff ...` | 0xFFFF (63) | open |
| `10 01 0119 ae95 6567 fffa ...` | 0xFFFA | shut again, battery field reads 281 mV |
| `10 01 0a84 ae96 5ce7 ffea ...` | 0xFFEA (42) | locked |

- Logic type 8: 58 = closed (shut, unlocked), 63 = open, 42 = locked.
- Byte 1 = 0x01 = RetroPro class.
- Bytes 4-5 are a frame counter (+1 per advert); bytes 6-7 vary (likely a nonce); bytes 10-15 were constant (`0000 10ff 0428`).
- The frame sent right after the door shuts reads ~280 mV in bytes 2-3, between ~2.7 V readings. The app has no special case for it, so the integration ignores battery readings under 1.5 V.
- Still unknown: how often the sensor re-advertises when nothing changes, and what tamper/vibration look like.
