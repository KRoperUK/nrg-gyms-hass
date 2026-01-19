# NRG Gyms Home Assistant Integration

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=KRoperUK&repository=nrg-gyms-hass)

Custom integration for NRG Gyms (PerfectGym portal) exposing bookings, occupancy, profile, and contracts.

## Entities
- Calendar: **NRG Upcoming Bookings** (next event + full event list)
- Calendar: **NRG Next Payment** (next membership payment date/amount)
- Sensors:
  - Bookings count, next booking summary (with attributes for start/end/location/description)
  - Occupancy total + per-club occupancy (home club enabled by default)
  - Profile (value = full name; attributes for user ID, email, phone, referral code, club name, photo URL)
  - Member ID, Home Club, Email
  - Contracts: active contract summary + next payment amount (GBP)

## Configuration
1) Install (HACS custom repo or manual copy) to `custom_components/nrg_gyms`.
2) Add integration via Settings → Devices & Services → Add Integration → "NRG Gyms"; enter email/password.
3) Options (post-setup):
   - Bookings path override (advanced)
   - User ID / Club ID overrides
   - Update interval (seconds; default 3600)

## Notes
- Bookings use MyCalendar endpoint with X-Hash; set club ID in Options if needed.
- Occupancy via `Clubs/GetMembersInClubs`; auth from CpAuthToken cookie.
- Profile/Contracts fetch identity first to get `user_id` and set home club; profile sensor shows avatar from portal photo URL.

## Debug Logging
Add to `configuration.yaml`:

```yaml
logger:
  default: warning
  logs:
    custom_components.nrg_gyms: debug
    custom_components.nrg_gyms.client: debug
```

## Development

Use the helper CLI to test login/bookings/occupancy/profile/contracts:

```
export NRG_EMAIL=you@example.com
export NRG_PASSWORD=yourpassword
./.venv/bin/python scripts/test_client.py
```

## Installation

- Copy `custom_components/nrg_gyms` into your Home Assistant `config/custom_components` directory.
- Restart Home Assistant.
- Add the integration from Settings → Devices & Services → Add Integration → "NRG Gyms".
- Enter your portal email and password.

Credentials are stored securely in Home Assistant and used to authenticate against the client portal. This integration does not log or expose your password.

## Notes

 - The PerfectGym portal has multiple possible endpoints for bookings. This integration now targets `MyCalendar/MyCalendar/GetCalendar` by default and uses `X-Hash` like `#/Classes/<clubId>/Calendar?date=YYYY-MM-DD`. Set your club ID in the integration Options.
 - Occupancy uses `Clubs/Clubs/GetMembersInClubs`. Authorization is taken from the `CpAuthToken` cookie set after login.
 - Profile uses `Profile/Profile/GetProfileForEdit`. If your portal requires a `userId`, set it in the integration Options.

### Enable Debug Logging

Add to `configuration.yaml`:

```
logger:
  default: warning
  logs:
    custom_components.nrg_gyms: debug
    custom_components.nrg_gyms.client: debug
```

## Development

Use the helper CLI script to test login, bookings, occupancy, and profile retrieval using environment variables:

```
export NRG_EMAIL=you@example.com
export NRG_PASSWORD=yourpassword
export NRG_USER_ID=402166  # optional
./.venv/bin/python scripts/test_client.py
```
