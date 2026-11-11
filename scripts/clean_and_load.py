"""
clean_and_load.py
------------------
1. Loads raw CPCB-style hourly readings
2. Cleans: per-station time interpolation for missing values, IQR-based
   outlier capping per station+pollutant
3. Computes sub-indices and overall AQI per the CPCB formula (simplified
   breakpoint table for PM2.5, PM10, NO2, SO2, CO, O3) + AQI category
4. Loads cleaned, AQI-tagged data into SQLite (data/aqi.db), table: readings
"""

import numpy as np
import pandas as pd
import sqlite3

import os
_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
RAW_PATH = os.path.join(_DATA_DIR, "aqi_raw.csv")
DB_PATH = os.path.join(_DATA_DIR, "aqi.db")

POLLUTANTS = ["PM2.5", "PM10", "NO2", "SO2", "CO", "O3"]

# CPCB breakpoints: (C_low, C_high, I_low, I_high) per pollutant
# Units: PM2.5/PM10/NO2/SO2/O3 in µg/m3 (24h avg conventions simplified for hourly use), CO in mg/m3
BREAKPOINTS = {
    "PM2.5": [(0,30,0,50),(31,60,51,100),(61,90,101,200),(91,120,201,300),(121,250,301,400),(251,500,401,500)],
    "PM10":  [(0,50,0,50),(51,100,51,100),(101,250,101,200),(251,350,201,300),(351,430,301,400),(431,600,401,500)],
    "NO2":   [(0,40,0,50),(41,80,51,100),(81,180,101,200),(181,280,201,300),(281,400,301,400),(401,600,401,500)],
    "SO2":   [(0,40,0,50),(41,80,51,100),(81,380,101,200),(381,800,201,300),(801,1600,301,400),(1601,2500,401,500)],
    "CO":    [(0,1.0,0,50),(1.1,2.0,51,100),(2.1,10,101,200),(10.1,17,201,300),(17.1,34,301,400),(34.1,50,401,500)],
    "O3":    [(0,50,0,50),(51,100,51,100),(101,168,101,200),(169,208,201,300),(209,748,301,400),(749,1000,401,500)],
}

CATEGORY_BINS = [
    (0, 50, "Good"), (51, 100, "Satisfactory"), (101, 200, "Moderate"),
    (201, 300, "Poor"), (301, 400, "Very Poor"), (401, 10_000, "Severe"),
]

def sub_index(value, pollutant):
    if pd.isna(value):
        return np.nan
    for c_lo, c_hi, i_lo, i_hi in BREAKPOINTS[pollutant]:
        if c_lo <= value <= c_hi:
            return i_lo + (i_hi - i_lo) * (value - c_lo) / (c_hi - c_lo)
    # above top bracket -> cap at top index, extrapolate lightly
    c_lo, c_hi, i_lo, i_hi = BREAKPOINTS[pollutant][-1]
    return i_hi + (value - c_hi) * 0.2

def categorize(aqi):
    if pd.isna(aqi):
        return None
    for lo, hi, label in CATEGORY_BINS:
        if lo <= aqi <= hi:
            return label
    return "Severe"

def cap_outliers_iqr(group, col, k=1.5):
    q1, q3 = group[col].quantile([0.25, 0.75])
    iqr = q3 - q1
    lo, hi = q1 - k * iqr, q3 + k * iqr
    return group[col].clip(lower=max(lo, 0), upper=hi)

def main():
    df = pd.read_csv(RAW_PATH, parse_dates=["datetime"])
    print(f"loaded {len(df):,} raw rows")

    # --- outlier capping per station+pollutant (IQR) ---
    for col in POLLUTANTS:
        df[col] = df.groupby("station", group_keys=False).apply(
            lambda g: cap_outliers_iqr(g, col)
        )

    # --- missing value interpolation per station, time-ordered ---
    df = df.sort_values(["station", "datetime"])
    for col in POLLUTANTS:
        df[col] = df.groupby("station")[col].transform(
            lambda s: s.interpolate(method="linear", limit_direction="both")
        )

    # --- AQI: max of sub-indices (CPCB convention), + dominant pollutant ---
    sub_cols = []
    for p in POLLUTANTS:
        col = f"SI_{p}"
        df[col] = df[p].apply(lambda v, pol=p: sub_index(v, pol))
        sub_cols.append(col)

    df["AQI"] = df[sub_cols].max(axis=1).round(0)
    df["dominant_pollutant"] = df[sub_cols].idxmax(axis=1).str.replace("SI_", "", regex=False)
    df["AQI_category"] = df["AQI"].apply(categorize)

    # time helpers for dashboard convenience
    df["date"] = df["datetime"].dt.date.astype(str)
    df["year"] = df["datetime"].dt.year
    df["month"] = df["datetime"].dt.month
    df["hour"] = df["datetime"].dt.hour
    df["month_name"] = df["datetime"].dt.strftime("%b")

    keep_cols = ["station", "datetime", "date", "year", "month", "month_name", "hour"] + \
                POLLUTANTS + ["AQI", "dominant_pollutant", "AQI_category"]
    df_final = df[keep_cols].reset_index(drop=True)

    conn = sqlite3.connect(DB_PATH)
    df_final.to_sql("readings", conn, if_exists="replace", index=False)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_station_date ON readings(station, date);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_year_month ON readings(year, month);")
    conn.commit()
    conn.close()

    print(f"wrote {len(df_final):,} cleaned rows -> {DB_PATH} (table: readings)")
    print(df_final["AQI_category"].value_counts())

if __name__ == "__main__":
    main()
