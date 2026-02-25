# rboi

## Export Reya OI caps

This repository includes a script that fetches Reya market definitions and exports sorted `oiCap` values per market.

### Requirements

- Python 3.10+
- Dependencies from `requirements.txt`

### Run

```bash
python3 -m pip install -r requirements.txt
python3 reya_oi_cap_to_csv.py
```

The script writes `reya_oi_caps.csv` and prints the 10 markets with the lowest `oiCap` values.
