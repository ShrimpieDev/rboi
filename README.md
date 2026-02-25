# rboi

## Export Reya OI caps

This repository includes a Python 3.10+ script that fetches Reya market definitions and exports sorted `oiCap` values per market.

### Requirements

Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

### Generate CSV from API

```bash
python3 reya_oi_cap_to_csv.py
```

This writes `reya_oi_caps.csv` with the columns:

- `market`
- `current_oi`
- `oiCap`
- `fetched_at_utc`

The script also prints the 10 markets with the lowest `oiCap` values, including `current_oi` for each pair.

> `current_oi` is extracted from available market fields (for example `currentOi`, `openInterest`, or `longOi + shortOi`) to stay compatible with Reya API shape changes.

## Website view (table)

Run the built-in web app to view the pulled data in an HTML table:

```bash
python3 reya_oi_cap_to_csv.py --serve --host 0.0.0.0 --port 8000
```

Then open `http://localhost:8000`.

- The page reads from `reya_oi_caps.csv` when available.
- Use `http://localhost:8000/?refresh=1` to fetch fresh data from the API and rewrite the CSV.
- The table includes both `current_oi` and `oiCap` for each market.

## Reference

- Reya developers docs: <https://docs.reya.xyz/developers>
