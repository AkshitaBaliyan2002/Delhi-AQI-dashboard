# Delhi Air Quality (AQI) Dashboard

Interactive Delhi AQI dashboard built on Apache Superset. Simulates CPCB-style
hourly monitoring data (2022–2024) across 12 Delhi stations, cleans it with
Python/SQL, computes CPCB AQI, and surfaces the insights as Superset charts.

## Stack
Apache Superset · Python · SQL (SQLite) · Pandas · NumPy

## What's inside
```
delhi-aqi-dashboard/
├── scripts/
│   ├── generate_data.py      # synthetic CPCB-style raw data (12 stations, hourly, 2022-2024)
│   └── clean_and_load.py     # missing-value interpolation, IQR outlier capping, AQI calc, load to SQLite
├── sql/
│   └── insights.sql          # the 9 analysis queries behind the dashboard charts
├── data/
│   ├── aqi_raw.csv           # raw simulated data (generated)
│   └── aqi.db                # cleaned SQLite DB Superset connects to (generated)
├── docker-compose.yml         # one-command Superset instance
└── README.md
```

## 1. Generate and clean the data
```bash
pip install -r requirements.txt
python scripts/generate_data.py      # -> data/aqi_raw.csv  (~315k rows, 12 stations)
python scripts/clean_and_load.py     # -> data/aqi.db (table: readings)
```

`readings` schema: `station, datetime, date, year, month, month_name, hour,
PM2.5, PM10, NO2, SO2, CO, O3, AQI, dominant_pollutant, AQI_category`

## 2. Spin up Superset
```bash
docker compose up -d
```
Visit `http://localhost:8088` → login `admin` / `admin`.

## 3. Connect the database
Settings → Database Connections → + Database → SQLite
```
sqlite:////app/data/aqi.db
```
(`/app/data` is the mounted path inside the container — see docker-compose volume.)

## 4. Build charts (Data → Datasets → + Dataset → table: `readings`)
Recommended charts, each backed by a query in `sql/insights.sql`:

| Chart | Type | Query ref |
|---|---|---|
| Station-wise pollution heatmap | Heatmap (station × month, avg PM2.5) | #1 |
| Seasonal AQI trend | Line chart (month over 2022-2024) | #2 |
| AQI category distribution | Pie / Bar | #3 |
| Winter smog buildup | Bar (Winter vs Rest of Year) | #4 |
| Diwali spike | Line chart, daily AQI around Diwali dates | #5 |
| Stubble-burning spike | Bar (window vs rest of Oct-Nov) | #6 |
| Most polluted zones, peak vs off-peak | Bar, station × traffic period | #7 |
| Top polluted stations | Bar, ranked by avg AQI | #8 |

Combine into one Superset **Dashboard**: "Delhi AQI Dashboard".

## Key insights this surfaces
- **Winter smog**: avg AQI roughly 30–40% higher Nov–Jan than the rest of the year
- **Diwali**: 2–3 day AQI spike immediately after Diwali night (firecracker SO2/PM2.5)
- **Stubble-burning window** (mid-Oct–mid-Nov): PM2.5 nearly 2x the rest of Oct/Nov
- **Peak-hour pollution**: Anand Vihar, ITO consistently the most polluted zones at traffic hours

## Notes on the data
CPCB's real historical station data needs manual scraping/downloads
(CPCB CCR, data.gov.in) per station per month — slow and inconsistent for a
from-scratch project. This generator encodes the real seasonal physics
(winter inversion, monsoon washout, stubble-burning window, Diwali, traffic
cycle) so every insight above is genuinely present in the data, not just
asserted. Swap `data/aqi_raw.csv` for real CPCB exports later — schema is
identical, so `clean_and_load.py` and all queries keep working unchanged.

## Push to GitHub
```bash
git init
git add .
git commit -m "Delhi AQI dashboard: data pipeline + Superset insights"
git branch -M main
git remote add origin https://github.com/<your-username>/delhi-aqi-dashboard.git
git push -u origin main
```
Add a `.gitignore` (included) so you don't commit `data/aqi.db` / raw CSV if
you'd rather keep the repo light — put a note in README that running
`generate_data.py` + `clean_and_load.py` regenerates them.
