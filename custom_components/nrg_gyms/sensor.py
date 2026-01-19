# pyright: reportIncompatibleMethodOverride=false
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN, DATA_COORDINATOR, DATA_OCCUPANCY_COORDINATOR, DATA_PROFILE_COORDINATOR, DATA_CLIENT, DATA_CONTRACTS_COORDINATOR


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data[DATA_COORDINATOR]
    occupancy_coordinator = data[DATA_OCCUPANCY_COORDINATOR]
    profile_coordinator = data[DATA_PROFILE_COORDINATOR]
    contracts_coordinator = data[DATA_CONTRACTS_COORDINATOR]
    client = data[DATA_CLIENT]

    # Fetch identity to determine home club for filtering; fall back to first club
    home_club_id = None
    try:
        ident = await hass.async_add_executor_job(client.fetch_identity)
        home_club_id = ident.get("home_club_id")
    except Exception:
        pass

    entities = [
        UpcomingBookingsCountSensor(coordinator, entry),
        NextBookingSensor(coordinator, entry),
        ClubOccupancyTotalSensor(occupancy_coordinator, entry),
        ProfileSensor(profile_coordinator, entry),
        MemberIdSensor(profile_coordinator, entry),
        HomeClubSensor(profile_coordinator, entry),
        EmailSensor(profile_coordinator, entry),
        ActiveContractSensor(contracts_coordinator, entry),
        NextPaymentAmountSensor(contracts_coordinator, entry),
    ]
    
    # Add per-club occupancy sensors; enable only home club (or first club if home unknown)
    if occupancy_coordinator.data and occupancy_coordinator.data.get("clubs"):
        preferred_id = home_club_id
        preferred_name = None
        if preferred_id is None and occupancy_coordinator.data["clubs"]:
            first = occupancy_coordinator.data["clubs"][0]
            preferred_id = first.get("id")
            preferred_name = first.get("name")
        for club in occupancy_coordinator.data["clubs"]:
            club_name = club.get("name", "Unknown")
            club_id = club.get("id")
            is_home = bool(
                (preferred_id is not None and club_id == preferred_id)
                or (preferred_id is None and preferred_name is not None and club_name == preferred_name)
            )
            entities.append(
                ClubOccupancySensor(occupancy_coordinator, entry, club_name, club_id, is_home)
            )
    
    async_add_entities(entities, True)


class BaseNrgSensor(SensorEntity):
    def __init__(self, coordinator, entry: ConfigEntry, name: str, unique_suffix: str) -> None:
        self.coordinator = coordinator
        self._entry = entry
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_sensor_{unique_suffix}_{entry.entry_id}"
        self._attr_should_poll = False

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.coordinator.async_add_listener(self.async_write_ha_state))

    async def async_update(self) -> None:
        await self.coordinator.async_request_refresh()


class UpcomingBookingsCountSensor(BaseNrgSensor):
    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "NRG Upcoming Bookings Count", "count")

    @property
    def native_value(self) -> int:  # type: ignore[override]
        return len(self.coordinator.data or [])


class NextBookingSensor(BaseNrgSensor):
    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "NRG Next Booking", "next")

    @property
    def native_value(self) -> str | None:  # type: ignore[override]
        bookings = list(self.coordinator.data or [])
        if not bookings:
            return None
        # Find nearest future booking
        now = datetime.now(bookings[0]["start"].tzinfo) if bookings[0].get("start") else datetime.now()
        upcoming = [b for b in bookings if b.get("start") and b["start"] >= now]
        if not upcoming:
            return None
        upcoming.sort(key=lambda b: b["start"])  # type: ignore
        b = upcoming[0]
        dt = b["start"].strftime("%Y-%m-%d %H:%M")
        summary = b.get("summary") or "Booking"
        location = b.get("location")
        if location:
            return f"{summary} @ {location} on {dt}"
        return f"{summary} on {dt}"

    @property
    def extra_state_attributes(self) -> Dict[str, Any] | None:  # type: ignore[override]
        bookings = list(self.coordinator.data or [])
        if not bookings:
            return None
        now = datetime.now(bookings[0]["start"].tzinfo) if bookings[0].get("start") else datetime.now()
        upcoming = [b for b in bookings if b.get("start") and b["start"] >= now]
        if not upcoming:
            return None
        upcoming.sort(key=lambda b: b["start"])  # type: ignore
        b = upcoming[0]
        return {
            "summary": b.get("summary"),
            "start": b.get("start").isoformat() if b.get("start") else None,
            "end": b.get("end").isoformat() if b.get("end") else None,
            "location": b.get("location"),
            "description": b.get("description"),
        }


class ClubOccupancyTotalSensor(BaseNrgSensor):
    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "NRG Club Occupancy Total", "occupancy_total")
        self._attr_icon = "mdi:account-group"

    @property
    def device_info(self) -> DeviceInfo:  # type: ignore[override]
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry.entry_id}_occupancy")},
            name="NRG Gyms Occupancy",
        )

    @property
    def native_value(self) -> int:  # type: ignore[override]
        data = self.coordinator.data or {}
        return int(data.get("total", 0))

    @property
    def extra_state_attributes(self) -> Dict[str, Any] | None:  # type: ignore[override]
        data = self.coordinator.data or {}
        clubs = data.get("clubs") or []
        # Map of club name -> members
        mapping = {c.get("name"): c.get("members") for c in clubs if c.get("name")}
        return {
            "clubs": mapping,
            "count": len(clubs),
        }


class ClubOccupancySensor(BaseNrgSensor):
    def __init__(self, coordinator, entry: ConfigEntry, club_name: str, club_id: int | None, is_home: bool) -> None:
        self.club_name = club_name
        self.club_id = club_id
        self._is_home = is_home
        self._attr_entity_registry_enabled_by_default = bool(is_home)
        # Use outline variant for non-home clubs
        self._attr_icon = "mdi:account-group" if is_home else "mdi:account-group-outline"
        suffix = f"occupancy_{club_id}" if club_id else f"occupancy_{club_name.replace(' ', '_').lower()}"
        super().__init__(coordinator, entry, f"NRG {club_name} Occupancy", suffix)

    @property
    def device_info(self) -> DeviceInfo:  # type: ignore[override]
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry.entry_id}_occupancy")},
            name="NRG Gyms Occupancy",
        )

    @property
    def native_value(self) -> int | None:  # type: ignore[override]
        data = self.coordinator.data or {}
        clubs = data.get("clubs") or []
        for c in clubs:
            if c.get("name") == self.club_name:
                return int(c.get("members", 0))
        return None


class ProfileSensor(BaseNrgSensor):
    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "NRG Profile", "profile")
        self._attr_icon = "mdi:account"

    @property
    def device_info(self) -> DeviceInfo:  # type: ignore[override]
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry.entry_id}_profile")},
            name="NRG Gyms Profile",
        )

    @property
    def native_value(self) -> str | None:  # type: ignore[override]
        data = self.coordinator.data or {}
        return data.get("full_name")

    @property
    def entity_picture(self) -> str | None:  # type: ignore[override]
        data = self.coordinator.data or {}
        return data.get("photo_url")

    @property
    def extra_state_attributes(self) -> Dict[str, Any] | None:  # type: ignore[override]
        data = self.coordinator.data or {}
        if not data:
            return None
        return {
            "user_id": data.get("user_id"),
            "email": data.get("email"),
            "first_name": data.get("first_name"),
            "last_name": data.get("last_name"),
            "phone": data.get("phone"),
            "referral_code": data.get("referral_code"),
            "photo_url": data.get("photo_url"),
            "home_club_id": data.get("home_club_id"),
            "default_club_id": data.get("default_club_id"),
            "club_name": data.get("club_name"),
        }


class MemberIdSensor(BaseNrgSensor):
    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "NRG Member ID", "member_id")
        self._attr_icon = "mdi:card-account-details"

    @property
    def device_info(self) -> DeviceInfo:  # type: ignore[override]
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry.entry_id}_profile")},
            name="NRG Gyms Profile",
        )

    @property
    def native_value(self) -> int | None:  # type: ignore[override]
        data = self.coordinator.data or {}
        return data.get("user_id")


class HomeClubSensor(BaseNrgSensor):
    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "NRG Home Club", "home_club")
        self._attr_icon = "mdi:home-account"

    @property
    def device_info(self) -> DeviceInfo:  # type: ignore[override]
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry.entry_id}_profile")},
            name="NRG Gyms Profile",
        )

    @property
    def native_value(self) -> str | None:  # type: ignore[override]
        data = self.coordinator.data or {}
        club_name = data.get("club_name")
        home_club_id = data.get("home_club_id")
        if club_name:
            return f"{club_name} ({home_club_id})"
        return str(home_club_id) if home_club_id else None


class EmailSensor(BaseNrgSensor):
    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "NRG Email", "email")
        self._attr_icon = "mdi:email"

    @property
    def device_info(self) -> DeviceInfo:  # type: ignore[override]
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry.entry_id}_profile")},
            name="NRG Gyms Profile",
        )

    @property
    def native_value(self) -> str | None:  # type: ignore[override]
        data = self.coordinator.data or {}
        return data.get("email")


class ActiveContractSensor(BaseNrgSensor):
    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "NRG Active Contract", "active_contract")
        self._attr_icon = "mdi:file-document"

    @property
    def device_info(self) -> DeviceInfo:  # type: ignore[override]
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry.entry_id}_contracts")},
            name="NRG Gyms Contracts",
        )

    @property
    def native_value(self) -> str | None:  # type: ignore[override]
        data = self.coordinator.data or {}
        active = data.get("active") or {}
        return active.get("name")

    @property
    def extra_state_attributes(self) -> Dict[str, Any] | None:  # type: ignore[override]
        data = self.coordinator.data or {}
        active = data.get("active")
        if not active:
            return None

        def _dt_to_iso(dt: Any) -> str | None:
            return dt.isoformat() if hasattr(dt, "isoformat") and dt else None

        return {
            "contract_id": active.get("id"),
            "club_name": active.get("club_name"),
            "club_id": active.get("club_id"),
            "start_date": _dt_to_iso(active.get("start_date")),
            "end_date": _dt_to_iso(active.get("end_date")),
            "commitment_date": _dt_to_iso(active.get("commitment_date")),
            "next_payment_date": _dt_to_iso(active.get("next_payment_date")),
            "payment_interval": active.get("payment_interval"),
            "commitment_period": active.get("commitment_period"),
            "cost_gross": active.get("cost_gross"),
            "cost_net": active.get("cost_net"),
            "cost_tax": active.get("cost_tax"),
            "addons": active.get("addons"),
            "description": active.get("short_description"),
        }


class NextPaymentAmountSensor(BaseNrgSensor):
    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "NRG Next Payment Amount", "next_payment_amount")
        self._attr_icon = "mdi:cash"
        self._attr_native_unit_of_measurement = "GBP"

    @property
    def device_info(self) -> DeviceInfo:  # type: ignore[override]
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry.entry_id}_contracts")},
            name="NRG Gyms Contracts",
        )

    @property
    def native_value(self) -> float | None:  # type: ignore[override]
        data = self.coordinator.data or {}
        active = data.get("active") or {}
        amount = active.get("cost_gross")
        try:
            return float(amount) if amount is not None else None
        except Exception:
            return None

    @property
    def extra_state_attributes(self) -> Dict[str, Any] | None:  # type: ignore[override]
        data = self.coordinator.data or {}
        active = data.get("active") or {}
        if not active:
            return None
        dt = active.get("next_payment_date")
        amount = active.get("cost_gross")
        try:
            amount_fmt = f"£{float(amount):.2f}" if amount is not None else None
        except Exception:
            amount_fmt = None
        return {
            "contract": active.get("name"),
            "next_payment_date": dt.isoformat() if hasattr(dt, "isoformat") and dt else None,
            "commitment_period": active.get("commitment_period"),
            "amount_formatted": amount_fmt,
        }
