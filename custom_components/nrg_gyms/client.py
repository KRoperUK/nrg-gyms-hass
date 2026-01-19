from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import requests

_LOGGER = logging.getLogger(__name__)

BASE_URL = "https://nrggym.perfectgym.com"
LOGIN_PATH = "/clientportal2/Auth/Login"
OCCUPANCY_PATH = "/clientportal2/Clubs/Clubs/GetMembersInClubs"
IDENTITY_PATH = "/clientportal2/Auth/Login/Identity"
PRODUCTS_PATH = "/clientportal2/Products/ChooseProducts/GetProductsForUser"
CONTRACTS_PATH = "/clientportal2/Profile/Contracts/ContractList"

# Candidate endpoints for upcoming bookings (best-effort; will try in order)
BOOKINGS_CANDIDATE_PATHS = [
    "/clientportal2/MyCalendar/MyCalendar/GetCalendar",
    "/clientportal2/Booking/GetUpcomingBookings",
    "/clientportal2/Booking/GetFutureBookings",
    "/clientportal2/Bookings/GetUpcoming",
    "/clientportal2/ClassBooking/GetUpcoming",
    "/clientportal2/Calendar/GetMyBookings",
]


class PerfectGymClient:
    def __init__(self, email: str, password: str, bookings_path: Optional[str] = None, club_id: Optional[int] = None) -> None:
        self._email = email
        self._password = password
        self._bookings_path_override = bookings_path
        self._club_id = club_id
        self._session = requests.Session()
        self._session.headers.update({
            "Accept": "application/json, text/plain, */*",
            "CP-LANG": "en",
            "CP-MODE": "desktop",
            "Content-Type": "application/json;charset=UTF-8",
            "Origin": BASE_URL,
            "Referer": f"{BASE_URL}/clientportal2/",
            "X-Requested-With": "XMLHttpRequest",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/143.0.0.0 Safari/537.36"
            ),
        })
        # Cookie hints from portal
        self._session.cookies.set("websiteAnalyticsConsent", "true")
        self._session.cookies.set("customTrackingKey", "true")

    def login(self) -> bool:
        try:
            payload = {
                "RememberMe": True,
                "Login": self._email,
                "Password": self._password,
            }
            # Some portals require X-Hash header mirroring navigation state
            headers = {"X-Hash": "#/Login"}
            resp = self._session.post(BASE_URL + LOGIN_PATH, data=json.dumps(payload), headers=headers, timeout=20)
            if resp.status_code == 200:
                # Response can be JSON or empty; cookies/tokens are set server-side
                _LOGGER.debug("Login response: %s", resp.text[:500])
                self._ensure_auth_header_from_cookie()
                return True
            _LOGGER.error("Login failed: status=%s body=%s", resp.status_code, resp.text[:300])
            return False
        except Exception as e:
            _LOGGER.exception("Login exception: %s", e)
            return False

    def _ensure_auth_header_from_cookie(self) -> None:
        # Portal tends to set CpAuthToken cookie; mirror it in Authorization header
        token = self._session.cookies.get("CpAuthToken")
        if token:
            self._session.headers["Authorization"] = f"Bearer {token}"

    def _try_endpoint(self, path: str, extra_headers: Optional[Dict[str, str]] = None) -> Optional[List[Dict[str, Any]]]:
        url = BASE_URL + path
        try:
            headers = extra_headers or {}
            resp = self._session.get(url, headers=headers, timeout=20)
            if resp.status_code != 200:
                _LOGGER.debug("Endpoint %s returned %s", path, resp.status_code)
                return None
            data = resp.json()
            # Normalize to a list of bookings
            if isinstance(data, dict):
                # Common fields might be under keys like 'Bookings', 'Items', 'Data'
                for key in ("Bookings", "Items", "Data", "Result", "results"):
                    if key in data and isinstance(data[key], list):
                        return data[key]
                # MyCalendar shape: RecentItems/FutureItems/PastItems each with Items list
                items: List[Dict[str, Any]] = []
                for section in ("RecentItems", "FutureItems", "PastItems"):
                    sec = data.get(section)
                    if isinstance(sec, dict) and isinstance(sec.get("Items"), list):
                        items.extend(sec["Items"])  # type: ignore
                if items:
                    return items
                # If dict itself looks like a booking, wrap
                if any(k in data for k in ("Start", "StartDate", "StartTime")):
                    return [data]
                return None
            if isinstance(data, list):
                return data
            return None
        except Exception as e:
            _LOGGER.debug("Error querying %s: %s", path, e)
            return None

    def fetch_upcoming_bookings(self) -> List[Dict[str, Any]]:
        # Try override path first if provided
        paths: List[str] = []
        if self._bookings_path_override:
            paths.append(self._bookings_path_override)
        paths.extend(BOOKINGS_CANDIDATE_PATHS)

        # Define a date range for endpoints that require parameters
        now = datetime.utcnow()
        horizon = now + timedelta(days=30)

        for path in paths:
            # Track extra headers for this path
            extra_headers: Dict[str, str] = {}
            # Special handling for MyCalendar endpoint: set X-Hash including club id and date
            if "/MyCalendar/MyCalendar/GetCalendar" in path:
                # Default to club id 5 (Manchester) if not provided
                club_id = self._club_id or 5
                date_str = now.date().isoformat()
                extra_headers["X-Hash"] = f"#/Classes/{club_id}/Calendar?date={date_str}"
            # If endpoint likely accepts date range, try with params first
            if any(key in path.lower() for key in ("calendar", "schedule")):
                ranged_path = f"{path}?start={now.isoformat()}&end={horizon.isoformat()}"
                bookings = self._try_endpoint(ranged_path, extra_headers)
                if bookings:
                    normalized = [self._normalize_booking(b) for b in bookings]
                    normalized = [b for b in normalized if b.get("start")]
                    _LOGGER.debug("Fetched %d bookings from %s (ranged)", len(normalized), ranged_path)
                    return normalized

            bookings = self._try_endpoint(path, extra_headers)
            if bookings:
                normalized = [self._normalize_booking(b) for b in bookings]
                # Filter out invalid
                normalized = [b for b in normalized if b.get("start")]
                _LOGGER.debug("Fetched %d bookings from %s", len(normalized), path)
                return normalized
        _LOGGER.warning(
            "No known bookings endpoint returned data. Enable debug logs and share portal API paths."
        )
        return []

    @staticmethod
    def _parse_dt(value: Any) -> Optional[datetime]:
        if not value:
            return None
        # Attempt ISO parse
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            # Ensure it has timezone info
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            _LOGGER.debug("Parsed datetime from ISO: %s -> %s", value, dt)
            return dt
        except Exception as e:
            _LOGGER.debug("Failed ISO parse of %s: %s", value, e)
        # Try milliseconds epoch
        try:
            val = int(value)
            # Heuristic: ms vs s
            if val > 10_000_000_000:
                dt = datetime.fromtimestamp(val / 1000, tz=timezone.utc)
            else:
                dt = datetime.fromtimestamp(val, tz=timezone.utc)
            _LOGGER.debug("Parsed datetime from epoch: %s -> %s", value, dt)
            return dt
        except Exception as e:
            _LOGGER.debug("Failed epoch parse of %s: %s", value, e)
            return None

    def _normalize_booking(self, item: Dict[str, Any]) -> Dict[str, Any]:
        # Attempt to map common fields
        title = item.get("Title") or item.get("ClassName") or item.get("Name") or "Booking"
        # Support MyCalendar keys
        start = self._parse_dt(
            item.get("StartTimeUtc")
            or item.get("StartTime")
            or item.get("Start")
            or item.get("StartDate")
        )
        end = self._parse_dt(
            item.get("EndTime")
            or item.get("End")
            or item.get("EndDate")
        )
        location = item.get("Club") or item.get("Zone") or item.get("Location") or item.get("ClubName")
        coach = item.get("TrainerDisplayName") or item.get("Coach") or item.get("Instructor")
        description_parts = []
        if coach:
            description_parts.append(f"Coach: {coach}")
        if item.get("Status"):
            description_parts.append(f"Status: {item.get('Status')}")
        if item.get("Type"):
            description_parts.append(f"Type: {item.get('Type')}")
        if item.get("ClassBookingId"):
            description_parts.append(f"ClassBookingId: {item.get('ClassBookingId')}")
        elif item.get("BookingId"):
            description_parts.append(f"BookingId: {item.get('BookingId')}")
        description = "; ".join(description_parts) if description_parts else None
        normalized = {
            "summary": title,
            "start": start,
            "end": end,
            "location": location,
            "description": description,
        }
        _LOGGER.debug("Normalized booking: title=%s start=%s end=%s location=%s", title, start, end, location)
        return normalized
        description = "; ".join(description_parts) if description_parts else None
        return {
            "summary": title,
            "start": start,
            "end": end,
            "location": location,
            "description": description,
        }

    def fetch_members_in_clubs(self) -> Dict[str, Any]:
        # Ensure auth header is present if cookie exists
        self._ensure_auth_header_from_cookie()
        # Pass X-Hash as per-request header instead of modifying session
        url = BASE_URL + OCCUPANCY_PATH
        try:
            # Endpoint expects POST with empty body
            headers = {"X-Hash": "#/Clubs/MembersInClubs"}
            resp = self._session.post(url, data=b"", headers=headers, timeout=20)
            if resp.status_code != 200:
                _LOGGER.error("Occupancy endpoint failed: status=%s body=%s", resp.status_code, resp.text[:300])
                return {"clubs": [], "total": 0}
            data = resp.json()
            clubs_raw: List[Dict[str, Any]] = []
            if isinstance(data, dict):
                # Example: UsersInClubList: [{ ClubName, UsersCountCurrentlyInClub }]
                if "UsersInClubList" in data and isinstance(data["UsersInClubList"], list):
                    clubs_raw = data["UsersInClubList"]
                for key in ("Clubs", "Items", "Data", "Result", "results"):
                    if key in data and isinstance(data[key], list):
                        clubs_raw = data[key]
                        break
                if not clubs_raw and isinstance(data.get("0"), dict):
                    clubs_raw = list(data.values())
            elif isinstance(data, list):
                clubs_raw = data
            clubs: List[Dict[str, Any]] = []
            total = 0
            for c in clubs_raw:
                name = c.get("ClubName") or c.get("Name") or c.get("Club") or c.get("name") or "Club"
                count = (
                    c.get("UsersCountCurrentlyInClub")
                    or c.get("MembersInClubCount")
                    or c.get("Count")
                    or c.get("members")
                    or c.get("value")
                )
                try:
                    count = int(count) if count is not None else 0
                except Exception:
                    count = 0
                clubs.append({
                    "name": name,
                    "members": count,
                    "id": c.get("ClubId") or c.get("Id") or c.get("id"),
                })
                total += count
            _LOGGER.debug("Fetched occupancy for %d clubs, total=%d", len(clubs), total)
            return {"clubs": clubs, "total": total}
        except Exception as e:
            _LOGGER.exception("Occupancy fetch exception: %s", e)
            return {"clubs": [], "total": 0}

    def fetch_profile(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        self._ensure_auth_header_from_cookie()
        url = BASE_URL + "/clientportal2/Profile/Profile/GetProfileForEdit"
        try:
            _LOGGER.debug("Profile fetch - URL: %s, user_id: %s", url, user_id)
            # Profile endpoint requires userId in both X-Hash header and request body
            if user_id:
                # Merge X-Hash with session headers (Authorization, Content-Type, etc. are in session)
                headers = {"X-Hash": f"#/Profile/Edit?userId={user_id}"}
                body = {"userId": user_id}
                auth_header = self._session.headers.get("Authorization") or ""
                _LOGGER.debug("Profile headers being sent: X-Hash=%s, Authorization=%s", 
                             headers.get("X-Hash"), 
                             auth_header[:50] if auth_header else None)
                resp = self._session.post(url, json=body, headers=headers, timeout=20)
            else:
                # If no user_id provided, try with minimal headers
                resp = self._session.post(url, data=b"", timeout=20)
            _LOGGER.debug("Profile response status: %s, response text: %s", resp.status_code, resp.text[:500])
            if resp.status_code != 200:
                _LOGGER.error("Profile endpoint failed: status=%s body=%s", resp.status_code, resp.text[:300])
                return {}
            data = resp.json()
            model = data.get("Model") or {}
            pd = model.get("PersonalData") or {}
            phone = pd.get("Phone") or {}
            name = " ".join([x for x in [pd.get("FirstName"), pd.get("LastName")] if x])
            normalized = {
                "user_id": model.get("UserId") or user_id,
                "first_name": pd.get("FirstName"),
                "last_name": pd.get("LastName"),
                "email": pd.get("Email"),
                "phone": phone.get("PhoneNumber"),
                "referral_code": pd.get("ReferralCode"),
                "full_name": name or None,
                "photo_url": (pd.get("Photo") or {}).get("Url"),
            }
            # Also fetch club name from products endpoint
            prod = self.fetch_products_for_user()
            if prod and prod.get("club_name"):
                normalized["club_name"] = prod.get("club_name")
            return normalized
        except Exception as e:
            _LOGGER.exception("Profile fetch exception: %s", e)
            return {}

    def fetch_identity(self) -> Dict[str, Any]:
        self._ensure_auth_header_from_cookie()
        # Don't set X-Hash for Identity - may interfere with other calls
        url = BASE_URL + IDENTITY_PATH
        try:
            resp = self._session.post(url, data=b"", timeout=20)
            if resp.status_code != 200:
                _LOGGER.error("Identity endpoint failed: status=%s body=%s", resp.status_code, resp.text[:300])
                return {}
            data = resp.json() or {}
            member = data.get("Member") or {}
            normalized = {
                "user_id": member.get("Id"),
                "first_name": member.get("FirstName"),
                "last_name": member.get("LastName"),
                "email": member.get("Email"),
                "home_club_id": member.get("HomeClubId"),
                "default_club_id": member.get("DefaultClubId"),
                "type": member.get("Type"),
                "photo_url": member.get("PhotoUrl"),
            }
            return normalized
        except Exception as e:
            _LOGGER.exception("Identity fetch exception: %s", e)
            return {}

    def fetch_contracts(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        """Fetch contracts for the user and normalize the primary contract."""
        self._ensure_auth_header_from_cookie()
        url = BASE_URL + CONTRACTS_PATH
        try:
            # If user_id not supplied, attempt identity lookup first
            if user_id is None:
                ident = self.fetch_identity()
                user_id = ident.get("user_id") if ident else None
            if not user_id:
                _LOGGER.warning("Contracts fetch skipped: missing user_id")
                return {"contracts": [], "active": None}

            headers = {"X-Hash": "#/Profile/Contract"}
            body = {"userId": user_id}
            resp = self._session.post(url, json=body, headers=headers, timeout=20)
            _LOGGER.debug("Contracts response status: %s, body: %s", resp.status_code, resp.text[:500])
            if resp.status_code != 200:
                _LOGGER.error("Contracts endpoint failed: status=%s body=%s", resp.status_code, resp.text[:300])
                return {"contracts": [], "active": None}

            data = resp.json() or {}
            contracts_raw = data.get("Contracts") or []
            contracts: List[Dict[str, Any]] = []
            for c in contracts_raw:
                club = c.get("Club") or {}
                cost = c.get("Cost") or {}
                contract = {
                    "id": c.get("Id"),
                    "name": c.get("Name"),
                    "addons": c.get("AddonsNames") or [],
                    "club_id": club.get("Id"),
                    "club_name": club.get("Name"),
                    "start_date": self._parse_dt(c.get("StartDate")),
                    "end_date": self._parse_dt(c.get("EndDate")),
                    "commitment_date": self._parse_dt(c.get("CommitmentDate")),
                    "next_payment_date": self._parse_dt(c.get("NextPaymentDate")),
                    "payment_interval": c.get("PaymentInterval"),
                    "commitment_period": c.get("CommitmentPeriod"),
                    "cost_gross": cost.get("Gross"),
                    "cost_net": cost.get("Net"),
                    "cost_tax": cost.get("Tax"),
                    "short_description": c.get("ShortDescription"),
                }
                contracts.append(contract)

            active = contracts[0] if contracts else None
            return {"contracts": contracts, "active": active}
        except Exception as e:
            _LOGGER.exception("Contracts fetch exception: %s", e)
            return {"contracts": [], "active": None}

    def fetch_products_for_user(self) -> Dict[str, Any]:
        self._ensure_auth_header_from_cookie()
        # View hash isn't strictly required; keep simple
        url = BASE_URL + PRODUCTS_PATH
        try:
            resp = self._session.get(url, timeout=20)
            if resp.status_code != 200:
                _LOGGER.error("Products endpoint failed: status=%s body=%s", resp.status_code, resp.text[:300])
                return {}
            data = resp.json() or {}
            club_name = data.get("ClubName")
            return {"club_name": club_name}
        except Exception as e:
            _LOGGER.exception("Products fetch exception: %s", e)
            return {}
