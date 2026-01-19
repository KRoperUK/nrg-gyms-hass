#!/usr/bin/env python3
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.DEBUG, format='%(name)s - %(levelname)s - %(message)s')

# Allow import when running outside HA
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "custom_components", "nrg_gyms"))
from client import PerfectGymClient  # type: ignore


def main():
    email = os.getenv("NRG_EMAIL")
    password = os.getenv("NRG_PASSWORD")
    if not email or not password:
        print("Set NRG_EMAIL and NRG_PASSWORD env vars.")
        return 1
    client = PerfectGymClient(email=email, password=password)
    ok = client.login()
    print(f"Login: {'OK' if ok else 'FAILED'}")
    bookings = client.fetch_upcoming_bookings()
    print(f"Bookings found: {len(bookings)}")
    for b in sorted([x for x in bookings if x.get('start')], key=lambda y: y['start']):
        dt = b['start'].strftime('%Y-%m-%d %H:%M') if b.get('start') else 'N/A'
        loc = f" @ {b.get('location')}" if b.get('location') else ''
        print(f"- {b.get('summary')}{loc} on {dt}")
    # Occupancy
    occ = client.fetch_members_in_clubs()
    print(f"Occupancy total: {occ.get('total')}")
    clubs = occ.get('clubs') or []
    for c in clubs:
        print(f"- {c.get('name')}: {c.get('members')} members")
    # Identity first to get user_id
    ident = client.fetch_identity()
    user_id = ident.get("user_id") if ident else None
    if ident:
        print(f"Identity home club id: {ident.get('home_club_id')} default: {ident.get('default_club_id')}")
    # Profile (now with user_id from identity)
    prof = client.fetch_profile(user_id)
    if prof:
        print(f"Profile: {prof.get('full_name')} (ID: {prof.get('user_id')})")
        print(f"Email: {prof.get('email')} Phone: {prof.get('phone')} Referral: {prof.get('referral_code')}")
    prod = client.fetch_products_for_user()
    if prod:
        print(f"Club name: {prod.get('club_name')}")
    contracts = client.fetch_contracts(user_id)
    active = (contracts or {}).get("active")
    if active:
        npd = active.get("next_payment_date")
        npd_str = npd.isoformat() if hasattr(npd, "isoformat") else npd
        print(
            f"Active contract: {active.get('name')} @ {active.get('club_name')} cost={active.get('cost_gross')} next_payment={npd_str}"
        )
        addons = active.get("addons") or []
        if addons:
            print(f"Addons: {', '.join(addons)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
