"""Tests for the NRG Gyms config flow."""
from unittest.mock import MagicMock, patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.core import HomeAssistant
from custom_components.nrg_gyms.const import DOMAIN, CONF_EMAIL, CONF_PASSWORD


async def test_flow_user_init(hass: HomeAssistant) -> None:
    """Test user initialized flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"


@patch("custom_components.nrg_gyms.config_flow.PerfectGymClient.login")
async def test_flow_user_valid(mock_login: MagicMock, hass: HomeAssistant) -> None:
    """Test user flow with valid credentials."""
    mock_login.return_value = True

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: "test@example.com", CONF_PASSWORD: "test"},
    )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "NRG Gyms (test@example.com)"
    assert result["data"] == {
        CONF_EMAIL: "test@example.com",
        CONF_PASSWORD: "test",
    }


@patch("custom_components.nrg_gyms.config_flow.PerfectGymClient.login")
async def test_flow_user_invalid(mock_login: MagicMock, hass: HomeAssistant) -> None:
    """Test user flow with invalid credentials."""
    mock_login.return_value = False

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: "test@example.com", CONF_PASSWORD: "wrong"},
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": "auth_failed"}
