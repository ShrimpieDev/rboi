# rboi

## Reya OI website + CSV export

This project includes a Python 3.10+ tool that can:

1. fetch **all Reya market pairs** and export `reya_oi_caps.csv`
2. run a local website that shows all rows with filter controls

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
- Filter by:
  - market substring (`market`)
  - min/max `oiCap` (`min_oi_cap`, `max_oi_cap`)
  - min/max `current_oi` (`min_current_oi`, `max_current_oi`)
- If live refresh fails, the app falls back to cached `reya_oi_caps.csv` if present.

### JSON API for the website

```text
GET /api/markets
GET /api/markets?refresh=1
GET /api/markets?market=BTC&min_oi_cap=1000&max_oi_cap=5000000
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

The CLI fetches and saves all pairs.

## Reference

- Reya developers docs: <https://docs.reya.xyz/developers>
