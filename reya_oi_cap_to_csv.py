#!/usr/bin/env python3
"""Fetch Reya market definitions and export OI caps to CSV."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import requests

API_URL = "https://api.reya.xyz/v2/marketDefinitions"
OUTPUT_CSV = Path("reya_oi_caps.csv")


def as_decimal(value: Any) -> Decimal | None:
    """Convert a value to Decimal when possible."""
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def extract_markets(payload: Any) -> list[dict[str, Any]]:
    """Normalize API payload into a list of market-like dictionaries."""
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if isinstance(payload, dict):
        for key in ("markets", "data", "marketDefinitions", "result"):
            candidate = payload.get(key)
            if isinstance(candidate, list):
                return [item for item in candidate if isinstance(item, dict)]
        # Some APIs may return a dict keyed by market symbol.
        if payload and all(isinstance(v, dict) for v in payload.values()):
            return list(payload.values())

    raise ValueError("Unexpected response shape; expected list or object with a market list")


def market_name(market: dict[str, Any], idx: int) -> str:
    for key in ("symbol", "market", "name", "id"):
        value = market.get(key)
        if value not in (None, ""):
            return str(value)
    return f"market_{idx}"


def main() -> int:
    response = requests.get(API_URL, timeout=30)
    response.raise_for_status()
    payload = response.json()

    markets = extract_markets(payload)

    rows: list[dict[str, str]] = []
    for idx, market in enumerate(markets, start=1):
        oi_cap = as_decimal(market.get("oiCap"))
        if oi_cap is None:
            continue
        rows.append(
            {
                "market": market_name(market, idx),
                "oiCap": format(oi_cap, "f"),
            }
        )

    rows.sort(key=lambda row: Decimal(row["oiCap"]))
    fetched_at_utc = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=["market", "oiCap", "fetched_at_utc"])
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "market": row["market"],
                    "oiCap": row["oiCap"],
                    "fetched_at_utc": fetched_at_utc,
                }
            )

    print(f"Saved {len(rows)} markets to {OUTPUT_CSV}")
    print("10 lowest oiCap markets:")
    for row in rows[:10]:
        print(f"- {row['market']}: {row['oiCap']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
