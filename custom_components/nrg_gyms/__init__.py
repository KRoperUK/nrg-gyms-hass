from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DOMAIN,
    DEFAULT_UPDATE_INTERVAL_SECONDS,
    DATA_CLIENT,
    DATA_COORDINATOR,
    CONF_BOOKINGS_PATH,
    DATA_OCCUPANCY_COORDINATOR,
    DATA_PROFILE_COORDINATOR,
    DATA_CONTRACTS_COORDINATOR,
    CONF_USER_ID,
    CONF_CLUB_ID,
    DATA_IDENTITY_COORDINATOR,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL_SECONDS,
)
from .client import PerfectGymClient

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = ["calendar", "sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    email: str = str(entry.data.get("email") or "")
    password: str = str(entry.data.get("password") or "")

    # Allow user override of update interval via options; fallback to default
    try:
        interval_seconds = int(entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL_SECONDS))
        if interval_seconds <= 0:
            interval_seconds = DEFAULT_UPDATE_INTERVAL_SECONDS
    except Exception:
        interval_seconds = DEFAULT_UPDATE_INTERVAL_SECONDS

    bookings_path = entry.options.get(CONF_BOOKINGS_PATH)
    club_id = entry.options.get(CONF_CLUB_ID)
    client = PerfectGymClient(email=email, password=password, bookings_path=bookings_path, club_id=club_id)

    # Run login in executor to avoid blocking
    success = await hass.async_add_executor_job(client.login)
    if not success:
        _LOGGER.error("NRG Gyms: Login failed; check credentials or portal availability.")
        # Still set up; coordinator will retry

    # If club_id not specified, default to identity home club
    if club_id is None:
        ident = await hass.async_add_executor_job(client.fetch_identity)
        if ident and ident.get("home_club_id"):
            client._club_id = ident.get("home_club_id")  # runtime default

    async def async_update_data():
        return await hass.async_add_executor_job(client.fetch_upcoming_bookings)

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="NRG Gyms Bookings",
        update_method=async_update_data,
        update_interval=timedelta(seconds=interval_seconds),
    )

    await coordinator.async_config_entry_first_refresh()

    async def async_update_occupancy():
        return await hass.async_add_executor_job(client.fetch_members_in_clubs)

    occupancy_coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="NRG Gyms Club Occupancy",
        update_method=async_update_occupancy,
        update_interval=timedelta(seconds=interval_seconds),
    )

    await occupancy_coordinator.async_config_entry_first_refresh()

    async def async_update_profile():
        # First fetch identity to get the actual user_id
        identity = await hass.async_add_executor_job(client.fetch_identity)
        _LOGGER.debug("Identity response: %s", identity)
        user_id = identity.get("user_id") if identity else None
        _LOGGER.debug("Extracted user_id from identity: %s", user_id)
        if user_id:
            return await hass.async_add_executor_job(client.fetch_profile, user_id)
        _LOGGER.warning("No user_id found in identity response, skipping profile fetch")
        return {}

    profile_coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="NRG Gyms Profile",
        update_method=async_update_profile,
        update_interval=timedelta(seconds=interval_seconds),
    )

    await profile_coordinator.async_config_entry_first_refresh()

    async def async_update_contracts():
        identity = await hass.async_add_executor_job(client.fetch_identity)
        user_id = identity.get("user_id") if identity else None
        if user_id:
            return await hass.async_add_executor_job(client.fetch_contracts, user_id)
        _LOGGER.warning("No user_id found; skipping contracts fetch")
        return {"contracts": [], "active": None}

    contracts_coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="NRG Gyms Contracts",
        update_method=async_update_contracts,
        update_interval=timedelta(seconds=interval_seconds),
    )

    await contracts_coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        DATA_CLIENT: client,
        DATA_COORDINATOR: coordinator,
        DATA_OCCUPANCY_COORDINATOR: occupancy_coordinator,
        DATA_PROFILE_COORDINATOR: profile_coordinator,
        DATA_CONTRACTS_COORDINATOR: contracts_coordinator,
    }

    # Create devices for grouping
    device_registry = await hass.async_add_executor_job(dr.async_get, hass)
    
    # Occupancy device
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{entry.entry_id}_occupancy")},
        name="NRG Gyms Occupancy",
        manufacturer="NRG Gyms",
        model="Occupancy Monitor",
    )
    
    # Profile device
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{entry.entry_id}_profile")},
        name="NRG Gyms Profile",
        manufacturer="NRG Gyms",
        model="Member Profile",
    )

    # Contracts device
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{entry.entry_id}_contracts")},
        name="NRG Gyms Contracts",
        manufacturer="NRG Gyms",
        model="Membership Contracts",
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
