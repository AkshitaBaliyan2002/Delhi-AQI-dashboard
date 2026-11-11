-- insights.sql
-- Run against data/aqi.db (table: readings)
-- Maps directly to resume bullets: station-wise heatmaps, seasonal AQI
-- trends, AQI category distribution, winter smog, Diwali / stubble-burning
-- spikes, most polluted zones (peak vs off-peak).

-- 1. Station-wise pollution heatmap (avg PM2.5 by station x month)
SELECT station, month, month_name, ROUND(AVG("PM2.5"), 1) AS avg_pm25
FROM readings
GROUP BY station, month
ORDER BY station, month;

-- 2. Seasonal AQI trend (monthly avg AQI, all stations combined)
SELECT year, month, month_name, ROUND(AVG(AQI), 1) AS avg_aqi
FROM readings
GROUP BY year, month
ORDER BY year, month;

-- 3. AQI category distribution (overall, and by station)
SELECT AQI_category, COUNT(*) AS hours, ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM readings), 2) AS pct
FROM readings
GROUP BY AQI_category
ORDER BY hours DESC;

SELECT station, AQI_category, COUNT(*) AS hours
FROM readings
GROUP BY station, AQI_category
ORDER BY station, hours DESC;

-- 4. Winter smog buildup (Nov-Jan avg AQI vs rest-of-year)
SELECT
  CASE WHEN month IN (11, 12, 1) THEN 'Winter (Nov-Jan)' ELSE 'Rest of Year' END AS period,
  ROUND(AVG(AQI), 1) AS avg_aqi,
  ROUND(AVG("PM2.5"), 1) AS avg_pm25
FROM readings
GROUP BY period;

-- 5. Diwali-period spike (± 2 days around known Diwali dates vs monthly baseline)
SELECT date, ROUND(AVG(AQI), 1) AS avg_aqi, ROUND(AVG("PM2.5"), 1) AS avg_pm25
FROM readings
WHERE date BETWEEN '2023-11-10' AND '2023-11-14'   -- Diwali 2023 window, adjust per year
GROUP BY date
ORDER BY date;

-- 6. Stubble-burning window spike (mid-Oct to mid-Nov) vs rest of October-November
SELECT
  CASE WHEN (month = 10 AND CAST(strftime('%d', date) AS INTEGER) >= 15)
         OR (month = 11 AND CAST(strftime('%d', date) AS INTEGER) <= 16)
       THEN 'Stubble-burning window' ELSE 'Other Oct-Nov days' END AS period,
  ROUND(AVG("PM2.5"), 1) AS avg_pm25,
  ROUND(AVG(AQI), 1) AS avg_aqi
FROM readings
WHERE month IN (10, 11)
GROUP BY period;

-- 7. Most polluted zones, peak hours (8-10am, 6-9pm) vs off-peak
SELECT
  station,
  CASE WHEN hour IN (8,9,10,18,19,20,21) THEN 'Peak' ELSE 'Off-Peak' END AS traffic_period,
  ROUND(AVG(AQI), 1) AS avg_aqi
FROM readings
GROUP BY station, traffic_period
ORDER BY avg_aqi DESC;

-- 8. Top 5 most polluted stations overall (by avg AQI)
SELECT station, ROUND(AVG(AQI), 1) AS avg_aqi, ROUND(AVG("PM2.5"), 1) AS avg_pm25
FROM readings
GROUP BY station
ORDER BY avg_aqi DESC
LIMIT 5;
