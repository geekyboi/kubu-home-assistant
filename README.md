# Kubu Smart for Home Assistant (local Bluetooth)

Reads Kubu door and window sensors (tested on an Anywhere PRO / RetroPro) straight from
their Bluetooth adverts. Setup signs in to your Kubu account **once** to fetch each sensor's
encryption key; after that it is fully local and your password isn't stored.

## Install

**Manual:** copy `custom_components/kubu` into your Home Assistant `config/custom_components/`
folder, restart, then go to Settings → Devices & services. Kubu should be discovered
automatically (or use "Add integration" → Kubu). Enter your Kubu email and password.

**HACS (recommended):** HACS → ⋮ → Custom repositories → add
`https://github.com/geekyboi/kubu-home-assistant` as type **Integration**, then download
"Kubu Smart (local Bluetooth)" and restart Home Assistant. Updates then show up in HACS.

Added a sensor in the Kubu app later? Open the integration's ⋮ menu → Reconfigure and sign in again.

## What you get per sensor

| Entity | Meaning |
|---|---|
| `binary_sensor.<name>` (door) | on = open |
| `binary_sensor.<name>_lock` | on = unlocked (Home Assistant's lock convention) |
| `binary_sensor.<name>_tamper` | on = tampered |
| `binary_sensor.<name>_battery` | on = battery low |
| `sensor.<name>_state` | open / closed / locked / tampered … |
| `sensor.<name>_battery_voltage`, `_last_seen` | diagnostics |
| vibration, signal strength | disabled by default |

States are restored after a restart, since sensors only advertise when something changes.

## Repo layout

- `custom_components/kubu/`: the integration
- `protocol-findings.md`: how the protocol was worked out
- `tools/`: Mac scripts used to confirm it (`kubu_keys.py`, `kubu_scan.py`)
- `tests/`: `pip install pytest-homeassistant-custom-component && pytest`

## Troubleshooting: entities never change

Kubu sensors put their state in the **scan response**, so the scanner that hears them
must use **active** scanning. Since Home Assistant 2026.6, ESPHome Bluetooth proxies
default to **Auto (passive)**, which overrides `active: true` in the proxy's YAML.

Fix: Settings → Devices & services → ESPHome → your proxy → **Configure** →
Bluetooth scanning mode → **Active**. For a local adapter, do the same under the
Bluetooth integration.

To check, enable debug logging for Kubu: each line `Kubu advert from …` should show a
different `raw=` value when you open or close a door.
