from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .client import PerfectGymClient

_LOGGER = logging.getLogger(__name__)


class NrgCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, client: PerfectGymClient, interval_seconds: int) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="NRG Gyms Bookings",
            update_interval=timedelta(seconds=interval_seconds),
        )
        self._client = client

    async def _async_update_data(self):
        return await self.hass.async_add_executor_job(self._client.fetch_upcoming_bookings)
