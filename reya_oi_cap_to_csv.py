#!/usr/bin/env python3
"""Reya OI exporter + small website.

- CLI mode (default): fetch API data and write reya_oi_caps.csv
- Website mode (--serve): render the CSV/API data in a table
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from flask import Flask, Response, jsonify, render_template, request
import requests

API_URL = "https://api.reya.xyz/v2/marketDefinitions"
OUTPUT_CSV = Path("reya_oi_caps.csv")


@dataclass
class ExportResult:
    rows: list[dict[str, str]]
    fetched_at_utc: str


def as_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def extract_markets(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if isinstance(payload, dict):
        for key in ("markets", "data", "marketDefinitions", "result"):
            candidate = payload.get(key)
            if isinstance(candidate, list):
                return [item for item in candidate if isinstance(item, dict)]
        if payload and all(isinstance(v, dict) for v in payload.values()):
            return list(payload.values())

    raise ValueError("Unexpected response shape; expected list or object with a market list")


def market_name(market: dict[str, Any], idx: int) -> str:
    for key in ("symbol", "market", "name", "id"):
        value = market.get(key)
        if value not in (None, ""):
            return str(value)
    return f"market_{idx}"


def extract_current_oi(market: dict[str, Any]) -> Decimal | None:
    # Likely fields for current open interest in Reya payload variants.
    candidates = (
        "currentOi",
        "current_oi",
        "openInterest",
        "open_interest",
        "oi",
        "currentOpenInterest",
        "totalOpenInterest",
    )
    for field in candidates:
        oi = as_decimal(market.get(field))
        if oi is not None:
            return oi

    for nested_key in ("stats", "metrics"):
        nested = market.get(nested_key)
        if not isinstance(nested, dict):
            continue
        for field in candidates:
            oi = as_decimal(nested.get(field))
            if oi is not None:
                return oi

    long_oi = as_decimal(market.get("longOi")) or as_decimal(market.get("long_oi"))
    short_oi = as_decimal(market.get("shortOi")) or as_decimal(market.get("short_oi"))
    if long_oi is not None and short_oi is not None:
        return long_oi + short_oi

    return None


def fetch_rows() -> ExportResult:
    response = requests.get(API_URL, timeout=30)
    response.raise_for_status()
    payload = response.json()
    markets = extract_markets(payload)

    rows: list[dict[str, str]] = []
    for idx, market in enumerate(markets, start=1):
        oi_cap = as_decimal(market.get("oiCap"))
        if oi_cap is None:
            continue

        current_oi = extract_current_oi(market)
        rows.append(
            {
                "market": market_name(market, idx),
                "current_oi": "" if current_oi is None else format(current_oi, "f"),
                "oiCap": format(oi_cap, "f"),
            }
        )

    rows.sort(key=lambda row: Decimal(row["oiCap"]))
    fetched_at_utc = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return ExportResult(rows=rows, fetched_at_utc=fetched_at_utc)


def write_csv(rows: list[dict[str, str]], fetched_at_utc: str, output_csv: Path = OUTPUT_CSV) -> None:
    with output_csv.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=["market", "current_oi", "oiCap", "fetched_at_utc"])
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "market": row["market"],
                    "current_oi": row["current_oi"],
                    "oiCap": row["oiCap"],
                    "fetched_at_utc": fetched_at_utc,
                }
            )


def read_csv_rows(output_csv: Path = OUTPUT_CSV) -> ExportResult:
    with output_csv.open("r", newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        rows = [
            {
                "market": row.get("market", ""),
                "current_oi": row.get("current_oi", ""),
                "oiCap": row.get("oiCap", ""),
                "fetched_at_utc": row.get("fetched_at_utc", ""),
            }
            for row in reader
        ]
    fetched_at_utc = rows[0]["fetched_at_utc"] if rows else ""
    return ExportResult(rows=rows, fetched_at_utc=fetched_at_utc)


def export_to_csv() -> ExportResult:
    result = fetch_rows()
    write_csv(result.rows, result.fetched_at_utc)

    print(f"Saved {len(result.rows)} markets to {OUTPUT_CSV}")
    print("10 lowest oiCap markets:")
    for row in result.rows[:10]:
        current = row["current_oi"] or "n/a"
        print(f"- {row['market']}: oiCap={row['oiCap']}, current_oi={current}")

    return result


def load_for_view(refresh: bool) -> tuple[ExportResult, str, str]:
    error = ""
    source = ""

    if refresh or not OUTPUT_CSV.exists():
        try:
            result = export_to_csv()
            source = "live API"
        except Exception as exc:  # noqa: BLE001
            if OUTPUT_CSV.exists():
                result = read_csv_rows()
                source = "cached CSV"
                error = f"Live refresh failed, showing cached CSV: {exc}"
            else:
                result = ExportResult(rows=[], fetched_at_utc="")
                source = "none"
                error = f"Live refresh failed and no cached CSV exists: {exc}"
    else:
        result = read_csv_rows()
        source = "cached CSV"

    return result, source, error


def build_app() -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def index() -> str:
        refresh = request.args.get("refresh") == "1"
        result, source, error = load_for_view(refresh)
        return render_template(
            "index.html",
            rows=result.rows,
            fetched_at_utc=result.fetched_at_utc,
            source=source,
            error=error,
        )

    @app.get("/api/markets")
    def api_markets() -> Response:
        refresh = request.args.get("refresh") == "1"
        result, source, error = load_for_view(refresh)
        payload = {
            "source": source,
            "error": error,
            "fetched_at_utc": result.fetched_at_utc,
            "rows": result.rows,
        }
        return jsonify(payload)

    @app.get("/healthz")
    def healthz() -> Response:
        return Response("ok\n", mimetype="text/plain")

    return app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Reya OI data and optionally serve a website")
    parser.add_argument("--serve", action="store_true", help="Run a local website with an OI table")
    parser.add_argument("--host", default="127.0.0.1", help="Host for --serve mode")
    parser.add_argument("--port", type=int, default=8000, help="Port for --serve mode")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.serve:
        app = build_app()
        app.run(host=args.host, port=args.port)
        return 0

    export_to_csv()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
