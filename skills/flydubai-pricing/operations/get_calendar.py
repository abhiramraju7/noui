#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import ssl
import sys
import urllib.parse
import urllib.request

import certifi


def execute(
    origin: str,
    destination: str,
    from_date: str = "",
    is_origin_metro: str = "false",
    is_dest_metro: str = "false",
) -> dict:
    url = f"https://www.flydubai.com/api/Calendar/{origin}/{destination}"
    params = {
        "fromDate": from_date,
        "isOriginMetro": is_origin_metro,
        "isDestMetro": is_dest_metro,
    }
    params = {k: v for k, v in params.items() if v not in ("", None)}

    if params:
        url += "?" + urllib.parse.urlencode(params)

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json,*/*",
            "Referer": "https://www.flydubai.com/en-in/",
        },
        method="GET",
    )

    context = ssl.create_default_context(cafile=certifi.where())
    with urllib.request.urlopen(req, timeout=30, context=context) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="get_calendar")
    parser.add_argument("--origin", required=True)
    parser.add_argument("--destination", required=True)
    parser.add_argument("--from-date", dest="from_date", default="")
    parser.add_argument("--is-origin-metro", dest="is_origin_metro", default="false")
    parser.add_argument("--is-dest-metro", dest="is_dest_metro", default="false")
    args = parser.parse_args(argv)

    try:
        result = execute(
            origin=args.origin,
            destination=args.destination,
            from_date=args.from_date,
            is_origin_metro=args.is_origin_metro,
            is_dest_metro=args.is_dest_metro,
        )
    except Exception as exc:
        print(f"get_calendar failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
