"""Config flow and entity tests against Home Assistant's test harness."""

from types import SimpleNamespace
from unittest.mock import patch

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kubu.api import CannotConnect, InvalidAuth
from custom_components.kubu.const import DOMAIN

KEY = "00112233445566778899aabbccddeeff"
MAC = "D0:D5:CB:8F:12:34"
SENSOR = {
    "mac": "D0D5CB8F1234",
    "name": "KubuRetroPro-CB-8F",
    "devAlias": "Front door",
    "dpKey": KEY,
    "type": 8,
    "sensorClass": "retroPro",
    "productType": "Anywhere PRO",
    "fwVer": "1.2",
    "hwRev": "A",
}
FETCH = "custom_components.kubu.config_flow.async_fetch_sensors"


def advert(plain_hex: str) -> SimpleNamespace:
    e = Cipher(algorithms.AES(bytes.fromhex(KEY)), modes.ECB()).encryptor()
    payload = e.update(bytes.fromhex(plain_hex)) + e.finalize()
    return SimpleNamespace(address=MAC, rssi=-50, manufacturer_data={3535: payload})


async def test_user_flow_creates_entry(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    with patch(FETCH, return_value=("acct1", [SENSOR])):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"email": "o@example.com", "password": "pw"}
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["sensors"] == [SENSOR]
    assert "password" not in result["data"]


async def test_user_flow_errors(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    for exc, err in ((InvalidAuth, "invalid_auth"), (CannotConnect, "cannot_connect")):
        with patch(FETCH, side_effect=exc):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {"email": "o@example.com", "password": "pw"}
            )
        assert result["errors"] == {"base": err}
    with patch(FETCH, return_value=("acct1", [])):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"email": "o@example.com", "password": "pw"}
        )
    assert result["errors"] == {"base": "no_sensors"}


async def test_adverts_update_entities(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="acct1",
        data={"email": "o@example.com", "account_id": "acct1", "sensors": [SENSOR]},
    )
    entry.add_to_hass(hass)
    captured = {}

    def fake_register(_hass, cb, _matcher, _mode):
        captured["cb"] = cb
        return lambda: None

    with patch(
        "custom_components.kubu.coordinator.bluetooth.async_register_callback",
        fake_register,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    door, lock = "binary_sensor.front_door", "binary_sensor.front_door_lock"
    battery_v, state = "sensor.front_door_battery_voltage", "sensor.front_door_state"
    assert hass.states.get(door).state == "unknown"

    def send(plain):
        captured["cb"](advert(plain), None)

    send("10010adaae93f4d7fffa000010ff0428")  # unlocked, shut
    await hass.async_block_till_done()
    assert hass.states.get(door).state == "off"
    assert hass.states.get(lock).state == "on"  # on = unlocked
    assert hass.states.get(state).state == "closed"
    assert hass.states.get(battery_v).state == "2778"

    send("10010a65ae941ba5ffff000010ff0428")  # open
    await hass.async_block_till_done()
    assert hass.states.get(door).state == "on"

    send("10010119ae956567fffa000010ff0428")  # shut again; 281 mV glitch ignored
    await hass.async_block_till_done()
    assert hass.states.get(door).state == "off"
    assert hass.states.get(battery_v).state == "2661"
    assert hass.states.get("binary_sensor.front_door_battery").state == "off"

    send("10010a84ae965ce7ffea000010ff0428")  # locked
    await hass.async_block_till_done()
    assert hass.states.get(lock).state == "off"
    assert hass.states.get(state).state == "locked"
    assert hass.states.get("binary_sensor.front_door_tamper").state == "off"

    # Adverts from unknown devices are ignored.
    captured["cb"](
        SimpleNamespace(
            address="11:22:33:44:55:66", rssi=-40, manufacturer_data={3535: bytes(16)}
        ),
        None,
    )
    captured["cb"](
        SimpleNamespace(
            address="AA:BB:CC:DD:EE:FF", rssi=-40, manufacturer_data={3535: b"x" * 16}
        ),
        None,
    )
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_bluetooth_discovery_and_reconfigure(hass: HomeAssistant) -> None:
    info = advert("10010adaae93f4d7fffa000010ff0428")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_BLUETOOTH}, data=info
    )
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "user"
    with patch(FETCH, return_value=("acct1", [SENSOR])):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"email": "o@example.com", "password": "pw"}
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    # A second discovery is ignored once an account is set up.
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_BLUETOOTH}, data=info
    )
    assert result["reason"] == "already_configured"

    second = SENSOR | {"mac": "D0D5CB8F9999", "devAlias": "Back door"}
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )
    with patch(FETCH, return_value=("acct1", [SENSOR, second])):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"email": "o@example.com", "password": "pw"}
        )
        await hass.async_block_till_done()
    assert result["reason"] == "reconfigure_successful"
    assert len(entry.data["sensors"]) == 2
    assert hass.states.get("binary_sensor.back_door") is not None


async def test_sensor_matched_by_key_when_address_differs(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="acct1",
        data={
            "email": "o@example.com",
            "account_id": "acct1",
            "sensors": [SENSOR | {"mac": "AABBCCDDEEFF"}],
        },
    )
    entry.add_to_hass(hass)
    captured = {}

    def fake_register(_hass, cb, _matcher, _mode):
        captured["cb"] = cb
        return lambda: None

    with patch(
        "custom_components.kubu.coordinator.bluetooth.async_register_callback",
        fake_register,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    captured["cb"](advert("10010a65ae941ba5ffff000010ff0428"), None)  # open, from MAC
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.front_door").state == "on"
    captured["cb"](advert("10010a84ae965ce7ffea000010ff0428"), None)  # locked
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.front_door_lock").state == "off"
