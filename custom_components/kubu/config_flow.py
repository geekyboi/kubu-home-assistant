"""Config flow: one-time Kubu sign-in to fetch sensor keys; everything after is local."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CannotConnect, InvalidAuth, async_fetch_sensors
from .const import CONF_ACCOUNT_ID, CONF_SENSORS, DOMAIN

SCHEMA = vol.Schema({vol.Required(CONF_EMAIL): str, vol.Required(CONF_PASSWORD): str})


class KubuConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Kubu."""

    VERSION = 1

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """A Kubu advert was seen; offer setup once per account."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")
        await self.async_set_unique_id(f"{DOMAIN}_discovery")
        self._abort_if_unique_id_configured()
        return await self.async_step_user()

    async def _async_sign_in(
        self, user_input: dict[str, Any]
    ) -> tuple[str | None, list, dict[str, str]]:
        try:
            account_id, sensors = await async_fetch_sensors(
                async_get_clientsession(self.hass),
                user_input[CONF_EMAIL],
                user_input[CONF_PASSWORD],
            )
        except InvalidAuth:
            return None, [], {"base": "invalid_auth"}
        except CannotConnect:
            return None, [], {"base": "cannot_connect"}
        if not sensors:
            return None, [], {"base": "no_sensors"}
        return account_id, sensors, {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            account_id, sensors, errors = await self._async_sign_in(user_input)
            if not errors:
                await self.async_set_unique_id(account_id, raise_on_progress=False)
                self._abort_if_unique_id_configured()
                # The password is not stored: it is only needed to fetch keys.
                return self.async_create_entry(
                    title=user_input[CONF_EMAIL],
                    data={
                        CONF_EMAIL: user_input[CONF_EMAIL],
                        CONF_ACCOUNT_ID: account_id,
                        CONF_SENSORS: sensors,
                    },
                )
        return self.async_show_form(step_id="user", data_schema=SCHEMA, errors=errors)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Sign in again to pick up newly added sensors."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            account_id, sensors, errors = await self._async_sign_in(user_input)
            if not errors:
                await self.async_set_unique_id(account_id)
                self._abort_if_unique_id_mismatch(reason="wrong_account")
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CONF_SENSORS: sensors,
                        CONF_EMAIL: user_input[CONF_EMAIL],
                    },
                )
        schema = self.add_suggested_values_to_schema(
            SCHEMA, {CONF_EMAIL: entry.data.get(CONF_EMAIL)}
        )
        return self.async_show_form(
            step_id="reconfigure", data_schema=schema, errors=errors
        )
