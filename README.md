# NRG Gyms Home Assistant Integration

Custom integration that logs into NRG Gyms (PerfectGym client portal) and exposes upcoming bookings as:

 - Calendar entity: "NRG Upcoming Bookings" showing events (from MyCalendar with configurable club ID)
- Sensors: bookings count and next booking summary
 - Sensors: club occupancy total with per-club counts
 - Sensor: user profile (name as value, attributes for email/phone/referral)

Refresh interval: hourly.

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
