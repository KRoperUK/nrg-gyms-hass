# pyright: reportIncompatibleMethodOverride=false
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, DATA_COORDINATOR, DATA_CONTRACTS_COORDINATOR

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data[DATA_COORDINATOR]
    contracts_coordinator = data[DATA_CONTRACTS_COORDINATOR]

    async_add_entities(
        [
            NrgBookingsCalendar(coordinator, entry),
            NrgNextPaymentCalendar(contracts_coordinator, entry),
        ],
        True,
    )


class NrgBookingsCalendar(CalendarEntity):
    _attr_name = "NRG Upcoming Bookings"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        self.coordinator = coordinator
        self._entry = entry
        self._attr_unique_id = f"{DOMAIN}_calendar_{entry.entry_id}"

    @property
    def should_poll(self) -> bool:  # type: ignore[override]
        return False

    async def async_update(self) -> None:
        await self.coordinator.async_request_refresh()

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        if not self.coordinator.data:
            _LOGGER.debug("No coordinator data for event property")
            return None
        item = self.coordinator.data[0]
        start = item.get("start")
        end = item.get("end")
        if not start:
            _LOGGER.debug("No start time in event item: %s", item)
            return None
        if end is None:
            end = start
        
        # Ensure timezone-aware datetimes
        if start and start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
            _LOGGER.debug("Added UTC timezone to start: %s", start)
        if end and end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
            _LOGGER.debug("Added UTC timezone to end: %s", end)
        
        try:
            _LOGGER.debug("Creating CalendarEvent: summary=%s start=%s (tz=%s) end=%s (tz=%s)", 
                         item.get("summary"), start, start.tzinfo if start else None, 
                         end, end.tzinfo if end else None)
            event = CalendarEvent(
                summary=item.get("summary") or "Booking",
                start=start,
                end=end,
                location=item.get("location"),
                description=item.get("description"),
            )
            _LOGGER.debug("Successfully created CalendarEvent: %s", event)
            return event
        except Exception as e:
            _LOGGER.error("Failed to create CalendarEvent: %s (start: %s, end: %s)", e, start, end)
            return None

    async def async_get_events(self, hass: HomeAssistant, start_date: datetime, end_date: datetime) -> list[CalendarEvent]:
        events: list[CalendarEvent] = []
        _LOGGER.debug("async_get_events called: start=%s end=%s", start_date, end_date)
        for item in self.coordinator.data or []:
            start = item.get("start")
            end = item.get("end")
            if not start:
                _LOGGER.debug("Skipping event without start time: %s", item)
                continue
            if end is None:
                end = start
            if start >= start_date and start <= end_date:
                try:
                    event = CalendarEvent(
                        summary=item.get("summary") or "Booking",
                        start=start,
                        end=end,
                        location=item.get("location"),
                        description=item.get("description"),
                    )
                    events.append(event)
                    _LOGGER.debug("Added event to list: %s", event.summary)
                except Exception as e:
                    _LOGGER.error("Failed to create CalendarEvent: %s", e)
        _LOGGER.debug("async_get_events returning %d events", len(events))
        return events

    @property
    def extra_state_attributes(self) -> Dict[str, Any] | None:  # type: ignore[override]
        return {
            "count": len(self.coordinator.data or []),
        }

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.coordinator.async_add_listener(self.async_write_ha_state))


class NrgNextPaymentCalendar(CalendarEntity):
    _attr_name = "NRG Next Payment"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        self.coordinator = coordinator
        self._entry = entry
        self._attr_unique_id = f"{DOMAIN}_calendar_payment_{entry.entry_id}"

    @property
    def should_poll(self) -> bool:  # type: ignore[override]
        return False

    async def async_update(self) -> None:
        await self.coordinator.async_request_refresh()

    @property
    def event(self) -> CalendarEvent | None:
        data = self.coordinator.data or {}
        active = data.get("active") or {}
        dt = active.get("next_payment_date")
        if not dt:
            return None
        start = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        end = start
        amount = active.get("cost_gross")
        try:
            amount_fmt = f"£{float(amount):.2f}" if amount is not None else None
        except Exception:
            amount_fmt = None
        try:
            return CalendarEvent(
                summary=(f"{amount_fmt} due" if amount_fmt else None) or active.get("name") or "Membership Payment",
                start=start,
                end=end,
                description=f"Next payment for {active.get('name')}" + (f" ({amount_fmt})" if amount_fmt else ""),
                location=active.get("club_name"),
            )
        except Exception as e:
            _LOGGER.error("Failed to create payment CalendarEvent: %s", e)
            return None

    async def async_get_events(self, hass: HomeAssistant, start_date: datetime, end_date: datetime) -> list[CalendarEvent]:
        data = self.coordinator.data or {}
        active = data.get("active") or {}
        dt = active.get("next_payment_date")
        if not dt:
            return []
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if dt < start_date or dt > end_date:
            return []
        try:
            return [
                CalendarEvent(
                    summary=active.get("name") or "Membership Payment",
                    start=dt,
                    end=dt,
                    description=f"Next payment for {active.get('name')}",
                    location=active.get("club_name"),
                )
            ]
        except Exception as e:
            _LOGGER.error("Failed to create payment CalendarEvent in async_get_events: %s", e)
            return []

    @property
    def extra_state_attributes(self) -> Dict[str, Any] | None:  # type: ignore[override]
        data = self.coordinator.data or {}
        active = data.get("active") or {}
        dt = active.get("next_payment_date")
        amount = active.get("cost_gross")
        try:
            amount_fmt = f"£{float(amount):.2f}" if amount is not None else None
        except Exception:
            amount_fmt = None
        return {
            "contract": active.get("name"),
            "next_payment_date": dt.isoformat() if hasattr(dt, "isoformat") and dt else None,
            "amount": amount,
            "amount_formatted": amount_fmt,
        }

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.coordinator.async_add_listener(self.async_write_ha_state))
