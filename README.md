# rboi

## Reya OI website + CSV export

This project includes a Python 3.10+ tool that can:

1. fetch Reya market data and export `reya_oi_caps.csv`
2. run a local website that shows OI data in a table

## Requirements

```bash
python3 -m pip install -r requirements.txt
```

## Run as a website (recommended)

```bash
python3 reya_oi_cap_to_csv.py --serve --host 0.0.0.0 --port 8000
```

Open <http://localhost:8000>.

- Click **Refresh from API** (or use `/?refresh=1`) to pull fresh data.
- The UI shows each market with `current_oi`, `oiCap`, and `fetched_at_utc`.
- If live refresh fails, the app falls back to cached `reya_oi_caps.csv` if present.

### JSON API for the website

```text
GET /api/markets
GET /api/markets?refresh=1
```

## Run as CSV exporter only

```bash
python3 reya_oi_cap_to_csv.py
```

This writes `reya_oi_caps.csv` with columns:

- `market`
- `current_oi`
- `oiCap`
- `fetched_at_utc`

The CLI prints the 10 markets with the lowest `oiCap`.

## Reference

- Reya developers docs: <https://docs.reya.xyz/developers>
