#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import ssl
import sys
import urllib.request
from datetime import datetime

import certifi

API_URL = "https://flights2.flydubai.com/api/flights/7"


def _format_date(date_str: str) -> str:
    return datetime.strptime(date_str, "%Y-%m-%d").strftime("%m/%d/%Y 12:00 AM")


def build_payload(
    origin: str,
    destination: str,
    depart_date: str,
    return_date: str = "",
    adults: int = 1,
    children: int = 0,
    infants: int = 0,
    cabin_class: str = "Economy",
) -> dict:
    criteria = [
        {
            "date": _format_date(depart_date),
            "dest": destination,
            "direction": "outBound",
            "origin": origin,
            "isOriginMetro": False,
            "isDestMetro": False,
        }
    ]

    if return_date:
        criteria.append(
            {
                "date": _format_date(return_date),
                "dest": origin,
                "direction": "inBound",
                "origin": destination,
                "isOriginMetro": False,
                "isDestMetro": False,
            }
        )

    return {
        "promoCode": "",
        "campaignCode": "",
        "cabinClass": cabin_class,
        "isDestMetro": "false",
        "isOriginMetro": "false",
        "paxInfo": {"adultCount": adults, "childCount": children, "infantCount": infants},
        "searchCriteria": criteria,
        "variant": "1",
    }


def execute(
    origin: str,
    destination: str,
    depart_date: str,
    return_date: str = "",
    adults: int = 1,
    children: int = 0,
    infants: int = 0,
    cabin_class: str = "Economy",
    include_nearby: bool = True,
) -> list[dict]:
    payload = build_payload(
        origin, destination, depart_date, return_date, adults, children, infants, cabin_class
    )

    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://flights2.flydubai.com",
            "Referer": "https://flights2.flydubai.com/",
            "appID": "DESKTOP",
            "User-Agent": "Mozilla/5.0",
        },
        method="POST",
    )

    context = ssl.create_default_context(cafile=certifi.where())
    with urllib.request.urlopen(req, timeout=60, context=context) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    requested_dates = {depart_date}
    if return_date:
        requested_dates.add(return_date)

    results = []
    for seg in data.get("segments", []):
        fare = seg.get("lowestAdultFarePerPax")
        departure = seg.get("departureDate", "")
        departure_day = departure[:10]

        if not fare or fare == "0.00":
            continue
        if not include_nearby and departure_day not in requested_dates:
            continue

        results.append(
            {
                "route": seg.get("route"),
                "direction": seg.get("direction"),
                "departureDate": departure,
                "fare": fare,
                "tax": seg.get("lowestAdultFareTaxSumPerPax"),
                "currency": seg.get("currencyCode"),
                "soldOut": seg.get("isSoldOut"),
            }
        )

    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="search_flights")
    parser.add_argument("--origin", required=True)
    parser.add_argument("--destination", required=True)
    parser.add_argument("--depart-date", required=True)
    parser.add_argument("--return-date", default="")
    parser.add_argument("--adults", type=int, default=1)
    parser.add_argument("--children", type=int, default=0)
    parser.add_argument("--infants", type=int, default=0)
    parser.add_argument("--cabin-class", default="Economy")
    parser.add_argument("--exact-dates-only", action="store_true")
    args = parser.parse_args(argv)

    try:
        result = execute(
            origin=args.origin,
            destination=args.destination,
            depart_date=args.depart_date,
            return_date=args.return_date,
            adults=args.adults,
            children=args.children,
            infants=args.infants,
            cabin_class=args.cabin_class,
            include_nearby=not args.exact_dates_only,
        )
    except Exception as exc:
        print(f"search_flights failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
