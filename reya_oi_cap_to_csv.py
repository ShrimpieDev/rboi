#!/usr/bin/env python3
"""Fetch Reya market definitions, export OI caps to CSV, and serve a small web table."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from flask import Flask, Response, render_template_string, request
import requests

API_URL = "https://api.reya.xyz/v2/marketDefinitions"
OUTPUT_CSV = Path("reya_oi_caps.csv")

HTML_TEMPLATE = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Reya OI caps</title>
    <style>
      body { font-family: Arial, sans-serif; margin: 2rem; color: #1f2937; }
      h1 { margin-bottom: 0.25rem; }
      .meta { margin: 0.25rem 0 1rem; color: #4b5563; }
      table { border-collapse: collapse; width: 100%; max-width: 900px; }
      th, td { border: 1px solid #d1d5db; padding: 0.5rem 0.75rem; text-align: left; }
      th { background: #f3f4f6; }
      .actions { margin: 1rem 0; }
      .error { color: #b91c1c; margin-top: 0.5rem; }
      code { background: #f3f4f6; padding: 0.1rem 0.3rem; border-radius: 0.25rem; }
    </style>
  </head>
  <body>
    <h1>Reya OI caps</h1>
    <p class="meta">Sorted ascending by <code>oiCap</code>. Total markets: {{ rows|length }}.</p>
    <div class="actions">
      <a href="/?refresh=1">Refresh data</a>
      {% if fetched_at_utc %}<span> · fetched_at_utc: <code>{{ fetched_at_utc }}</code></span>{% endif %}
      {% if source %}<span> · source: <code>{{ source }}</code></span>{% endif %}
    </div>
    {% if error %}<p class="error">{{ error }}</p>{% endif %}
    <table>
      <thead>
        <tr>
          <th>#</th>
          <th>Market</th>
          <th>oiCap</th>
          <th>fetched_at_utc</th>
        </tr>
      </thead>
      <tbody>
        {% for row in rows %}
        <tr>
          <td>{{ loop.index }}</td>
          <td>{{ row.market }}</td>
          <td>{{ row.oiCap }}</td>
          <td>{{ row.fetched_at_utc }}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </body>
</html>
"""


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
        rows.append({"market": market_name(market, idx), "oiCap": format(oi_cap, "f")})

    rows.sort(key=lambda row: Decimal(row["oiCap"]))
    fetched_at_utc = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return ExportResult(rows=rows, fetched_at_utc=fetched_at_utc)


def write_csv(rows: list[dict[str, str]], fetched_at_utc: str, output_csv: Path = OUTPUT_CSV) -> None:
    with output_csv.open("w", newline="", encoding="utf-8") as csv_file:
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


def read_csv_rows(output_csv: Path = OUTPUT_CSV) -> ExportResult:
    with output_csv.open("r", newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        rows = [
            {"market": row.get("market", ""), "oiCap": row.get("oiCap", ""), "fetched_at_utc": row.get("fetched_at_utc", "")}
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
        print(f"- {row['market']}: {row['oiCap']}")
    return result


def build_app() -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def index() -> str:
        refresh = request.args.get("refresh") == "1"
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

        return render_template_string(
            HTML_TEMPLATE,
            rows=result.rows,
            fetched_at_utc=result.fetched_at_utc,
            source=source,
            error=error,
        )

    @app.get("/healthz")
    def healthz() -> Response:
        return Response("ok\n", mimetype="text/plain")

    return app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Reya oiCap values and optionally serve a web table")
    parser.add_argument("--serve", action="store_true", help="Run a local web server with a table of OI caps")
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
