"""Live end-to-end tests for NRG Gyms config flow."""

import os
from unittest.mock import MagicMock, patch

import pytest
from homeassistant import config_entries, data_entry_flow
from homeassistant.core import HomeAssistant

from custom_components.nrg_gyms.const import CONF_EMAIL, CONF_PASSWORD, DOMAIN


# Skipped unless NRG_EMAIL and NRG_PASSWORD env vars are set
# Run with: pytest tests/test_config_flow_live.py
@pytest.mark.live
@pytest.mark.skipif(
    not os.getenv("NRG_EMAIL") or not os.getenv("NRG_PASSWORD"),
    reason="NRG_EMAIL and NRG_PASSWORD environment variables not set",
)
async def test_config_flow_live_valid_credentials(hass: HomeAssistant) -> None:
    """Test standard config flow with valid live credentials."""
    email = os.getenv("NRG_EMAIL")
    password = os.getenv("NRG_PASSWORD")

    # Start the config flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    # Submit form with valid credentials
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: email, CONF_PASSWORD: password},
    )

    # Should create entry
    if result["type"] != data_entry_flow.FlowResultType.CREATE_ENTRY:
        print(f"Flow failed with result: {result}")
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == f"NRG Gyms ({email})"
    assert result["data"][CONF_EMAIL] == email
    assert result["data"][CONF_PASSWORD] == password


@pytest.mark.live
@pytest.mark.skipif(
    not os.getenv("NRG_EMAIL") or not os.getenv("NRG_PASSWORD"),
    reason="NRG_EMAIL and NRG_PASSWORD environment variables not set",
)
async def test_config_flow_live_invalid_credentials(hass: HomeAssistant) -> None:
    """Test standard config flow with INVALID live credentials."""
    # Use real email but wrong password to test auth failure against real server
    email = os.getenv("NRG_EMAIL")
    password = "wrong_password_123"

    # Start the config flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    # Submit form with invalid credentials
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: email, CONF_PASSWORD: password},
    )

    # Should return to form with error
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": "auth_failed"}
