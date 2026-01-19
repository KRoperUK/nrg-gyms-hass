from __future__ import annotations

import logging
from typing import Any, Dict

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector
import voluptuous as vol

from .const import DOMAIN, CONF_EMAIL, CONF_PASSWORD, CONF_BOOKINGS_PATH, CONF_USER_ID, CONF_CLUB_ID, CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL_SECONDS
from .client import PerfectGymClient

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: Dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        errors: Dict[str, str] = {}

        if user_input is not None:
            email = user_input[CONF_EMAIL]
            password = user_input[CONF_PASSWORD]

            client = PerfectGymClient(email=email, password=password)
            ok = await self.hass.async_add_executor_job(client.login)
            if not ok:
                errors["base"] = "auth_failed"
            else:
                await self.async_set_unique_id(f"nrg_gyms_{email}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=f"NRG Gyms ({email})", data=user_input)

        data_schema = vol.Schema({
            vol.Required(CONF_EMAIL): selector.TextSelector(),
            vol.Required(CONF_PASSWORD): selector.TextSelector({"type": "password"}),
        })

        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)


class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        return await self.async_step_options(user_input)

    async def async_step_options(self, user_input=None):
        errors: Dict[str, str] = {}

        if user_input is not None:
            # No validation beyond presence; client will attempt usage
            return self.async_create_entry(title="Options", data=user_input)

        data_schema = vol.Schema({
            vol.Optional(CONF_BOOKINGS_PATH, default=""): selector.TextSelector(),
            vol.Optional(CONF_USER_ID): selector.NumberSelector({"min": 1, "mode": "box"}),
            vol.Optional(CONF_CLUB_ID): selector.NumberSelector({"min": 1, "mode": "box"}),
            vol.Optional(CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL_SECONDS): selector.NumberSelector({"min": 300, "mode": "box", "step": 60}),
        })
        # Home Assistant's show_form does not support suggested_values; embed defaults in schema above
        return self.async_show_form(step_id="options", data_schema=data_schema, errors=errors)


async def async_get_options_flow(config_entry: config_entries.ConfigEntry):
    return OptionsFlowHandler(config_entry)
