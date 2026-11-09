<picture>
  <source media="(prefers-color-scheme: dark)" srcset="custom_components/kubu/brand/dark_logo@2x.png">
  <img src="custom_components/kubu/brand/logo@2x.png" alt="Kubu Local (unofficial)" height="64">
</picture>

# Kubu Smart for Home Assistant (local Bluetooth, unofficial)

> This is an unofficial, community integration. It is not affiliated with, endorsed by, or
> supported by Kubu. Kubu and its product names are trade marks of their owners and are used
> only to identify compatible devices. It reads data your own sensors broadcast, using keys from
> your own Kubu account. The Kubu cloud is contacted only during setup and reconfigure.

Reads Kubu door and window sensors (tested on an Anywhere PRO / RetroPro) straight from
their Bluetooth adverts. Setup signs in to your Kubu account **once** to fetch each sensor's
encryption key; after that it is fully local and your password isn't stored.

## Install

**Manual:** copy `custom_components/kubu` into your Home Assistant `config/custom_components/`
folder, restart, then go to Settings → Devices & services. Kubu should be discovered
automatically (or use "Add integration" → Kubu). Enter your Kubu email and password.

**HACS (recommended):** open HACS, search for "Kubu Smart (local Bluetooth, unofficial)",
download it and restart Home Assistant. Updates then show up in HACS.

[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=geekyboi&repository=kubu-home-assistant&category=integration)

Added a sensor in the Kubu app later? Open the integration's ⋮ menu → Reconfigure and sign in again.

## What you get per sensor

| Entity | Meaning |
|---|---|
| `binary_sensor.<name>` (door) | on = open |
| `binary_sensor.<name>_lock` | on = unlocked (Home Assistant's lock convention) |
| `binary_sensor.<name>_tamper` | on = tampered |
| `binary_sensor.<name>_battery` | on = battery low |
| `sensor.<name>_state` | open / closed / locked / tampered … |
| `sensor.<name>_battery_voltage` | diagnostic |
| `sensor.<name>_last_seen` | disabled by default; refreshes at most every 15 min |
| vibration, signal strength | disabled by default |

Sensors re-broadcast about every 30 s; entities only update when their value changes, so the
logbook only shows real events. States are restored after a restart.

## Repo layout

- `custom_components/kubu/`: the integration
- `protocol-findings.md`: the advertisement format, as observed from real sensors
- `tools/`: Mac scripts used to confirm it (`kubu_keys.py`, `kubu_scan.py`)
- `tests/`: `pip install pytest-homeassistant-custom-component && pytest`

## Troubleshooting: entities never change, or change late

Kubu sensors put their state in the **scan response**, so the scanner that hears them
must use **active** scanning. Since Home Assistant 2026.6, scanners and ESPHome proxies
default to **Auto**, which scans passively and overrides `active: true` in a proxy's YAML.

From v0.1.3 the integration asks Auto-mode scanners for an active window of 35 s every
60 s per sensor (the tightest Home Assistant allows), so states arrive without any
setup, but can lag by up to ~25 s. For instant updates set the scanner to Active:

Settings → Devices & services → ESPHome → your proxy → **Configure** →
Bluetooth scanning mode → **Active**. For a local adapter, do the same under the
Bluetooth integration.

To check, enable debug logging for Kubu: each line `Kubu advert from …` should show a
different `raw=` value when you open or close a door.
