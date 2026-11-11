"""
generate_data.py
-----------------
Creates a synthetic but realistic CPCB-style hourly air quality dataset
for Delhi monitoring stations, 2022-01-01 to 2024-12-31.

Pollutants: PM2.5, PM10, NO2, SO2, CO, O3  (µg/m3, CO in mg/m3)

Why synthetic: CPCB's real historical data requires scraping CPCB CCR /
data.gov.in with manual downloads per station/month. For an interview
project, simulating data with realistic seasonal + event patterns is
faster and fully reproducible, and you can swap in the real CSVs later
without changing any downstream code (same schema).

Patterns baked in (so your "insights" in the dashboard are genuine,
not invented):
  - Winter (Nov-Jan) smog: PM2.5/PM10 baseline rises sharply
  - Diwali week: 3-4 day spike in PM2.5, PM10, SO2 (firecrackers)
  - Stubble-burning window (mid Oct - mid Nov): PM2.5/PM10 spike
  - Daily cycle: traffic-hour (8-10am, 6-9pm) NO2/CO bump
  - Monsoon (Jul-Sep): pollutant levels drop (washout effect)
  - Station-level offset: traffic-heavy stations (Anand Vihar, ITO,
    Punjabi Bagh) run higher baseline than residential/green stations
  - ~3% missing sensor readings, ~1% sensor-fault outliers
"""

import numpy as np
import pandas as pd
from datetime import datetime

np.random.seed(42)

STATIONS = {
    "Anand Vihar":      1.35,   # traffic/industrial hotspot
    "ITO":              1.30,
    "Punjabi Bagh":     1.20,
    "Wazirpur":         1.25,
    "Jahangirpuri":     1.15,
    "Mandir Marg":      1.00,
    "R K Puram":        1.05,
    "Dwarka Sector 8":  0.90,
    "Okhla Phase 2":    1.10,
    "Narela":           1.00,
    "Rohini":           0.95,
    "Aya Nagar":        0.80,   # relatively green/low-traffic
}

START = datetime(2022, 1, 1)
END = datetime(2024, 12, 31, 23, 0, 0)

def seasonal_factor(ts):
    doy = ts.dayofyear
    # smooth winter-peak seasonal curve, peak ~ day 15 (mid Jan) and day 350 (mid Dec)
    winter = 1.8 * np.exp(-((doy - 15) % 365) ** 2 / (2 * 35 ** 2))
    winter += 1.8 * np.exp(-((doy - 350) % 365) ** 2 / (2 * 35 ** 2))
    monsoon_dip = -0.55 * np.exp(-((doy - 225) % 365) ** 2 / (2 * 40 ** 2))  # mid Aug
    return 1.0 + winter + monsoon_dip

def stubble_burning_factor(ts):
    # mid-Oct to mid-Nov spike, peaks ~ Nov 1-7
    doy = ts.dayofyear
    if 288 <= doy <= 320:  # ~Oct 15 - Nov 16
        peak = 305
        return 1.0 + 1.4 * np.exp(-((doy - peak) ** 2) / (2 * 6 ** 2))
    return 1.0

def diwali_factor(ts):
    # Approx Diwali dates (varies by year, using known dates)
    diwali_dates = {2022: "2022-10-24", 2023: "2023-11-12", 2024: "2024-11-01"}
    d = pd.Timestamp(diwali_dates[ts.year])
    days_from = (ts.normalize() - d).days
    if -1 <= days_from <= 2:
        return 2.2 if days_from in (0, 1) else 1.5
    return 1.0

def daily_traffic_factor(hour):
    morning = np.exp(-((hour - 9) ** 2) / (2 * 1.5 ** 2))
    evening = np.exp(-((hour - 20) ** 2) / (2 * 2.0 ** 2))
    night_low = np.where((hour >= 2) & (hour <= 5), 0.6, 1.0)
    return (1.0 + 0.6 * morning + 0.7 * evening) * night_low

def gen_series(ts_index, station_mult):
    n = len(ts_index)
    hours = ts_index.hour.values
    seas = np.array([seasonal_factor(t) for t in ts_index])
    stubble = np.array([stubble_burning_factor(t) for t in ts_index])
    diwali = np.array([diwali_factor(t) for t in ts_index])
    traffic = daily_traffic_factor(hours)

    pm25_base = 70 * seas * stubble * diwali * traffic * station_mult
    pm25 = np.clip(pm25_base * np.random.lognormal(0, 0.18, n), 5, 999)

    pm10 = np.clip(pm25 * np.random.uniform(1.4, 1.9, n), 10, 999)

    no2_base = 35 * traffic * station_mult * (0.8 + 0.4 * (seas - 1).clip(min=0))
    no2 = np.clip(no2_base * np.random.lognormal(0, 0.20, n), 2, 400)

    so2_base = 12 * diwali * station_mult
    so2 = np.clip(so2_base * np.random.lognormal(0, 0.25, n), 1, 200)

    co_base = 1.1 * traffic * station_mult
    co = np.clip(co_base * np.random.lognormal(0, 0.22, n), 0.1, 15)

    # O3 is inversely related to traffic/NOx at night, peaks midday, lower in winter
    o3_base = 40 * (1.3 - 0.3 * (seas - 1)) * np.exp(-((hours - 14) ** 2) / (2 * 4 ** 2))
    o3 = np.clip(o3_base * np.random.lognormal(0, 0.25, n) + 8, 2, 250)

    return pm25, pm10, no2, so2, co, o3

def inject_missing_and_outliers(df, missing_rate=0.03, outlier_rate=0.01):
    pollutants = ["PM2.5", "PM10", "NO2", "SO2", "CO", "O3"]
    n = len(df)
    rng = np.random.default_rng(7)
    for col in pollutants:
        miss_idx = rng.choice(n, size=int(n * missing_rate), replace=False)
        df.loc[miss_idx, col] = np.nan
        out_idx = rng.choice(n, size=int(n * outlier_rate), replace=False)
        # sensor-fault style outliers: either near-zero or absurd spike
        spike = rng.choice([0.02, 8.0], size=len(out_idx))
        df.loc[out_idx, col] = df.loc[out_idx, col].fillna(df[col].median()) * spike
    return df

def main():
    ts_index = pd.date_range(START, END, freq="h")
    frames = []
    for station, mult in STATIONS.items():
        pm25, pm10, no2, so2, co, o3 = gen_series(ts_index, mult)
        frames.append(pd.DataFrame({
            "station": station,
            "datetime": ts_index,
            "PM2.5": pm25.round(1),
            "PM10": pm10.round(1),
            "NO2": no2.round(1),
            "SO2": so2.round(1),
            "CO": co.round(2),
            "O3": o3.round(1),
        }))
    df = pd.concat(frames, ignore_index=True)
    df = inject_missing_and_outliers(df)
    df = df.sort_values(["station", "datetime"]).reset_index(drop=True)
    import os
    out_path = os.path.join(os.path.dirname(__file__), "..", "data", "aqi_raw.csv")
    df.to_csv(out_path, index=False)
    print(f"wrote {len(df):,} rows across {len(STATIONS)} stations -> {out_path}")

if __name__ == "__main__":
    main()
