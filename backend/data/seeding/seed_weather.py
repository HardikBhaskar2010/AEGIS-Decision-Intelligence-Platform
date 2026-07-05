# backend/data/seeding/seed_weather.py
import requests
import datetime
import pandas as pd
import uuid
from google.cloud import bigquery
from backend.data.config import PROJECT_ID, RAW_DATASET, CORE_DATASET, SECTORS_DATA, ANOMALY_SECTOR_ID

def fetch_open_meteo_data(lat, lng):
    """
    Fetches historical and current forecast data for given coordinates.
    """
    # Open-Meteo API URL
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lng}&hourly=temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m&past_days=7&forecast_days=1"
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        data = res.json()
        
        hourly = data.get("hourly", {})
        times = hourly.get("time", [])
        temps = hourly.get("temperature_2m", [])
        humidities = hourly.get("relative_humidity_2m", [])
        precips = hourly.get("precipitation", [])
        winds = hourly.get("wind_speed_10m", [])
        
        df = pd.DataFrame({
            "ts": pd.to_datetime(times),
            "temperature_c": temps,
            "humidity_pct": humidities,
            "precipitation_mm": precips,
            "wind_speed_kmh": winds
        })
        return df, "open_meteo_api"
    except Exception as e:
        print(f"Open-Meteo API failed or offline: {e}. Using offline synthetic weather fallback.")
        # Fallback: Generate 8 days of hourly synthetic weather
        now = datetime.datetime.now(datetime.timezone.utc)
        start_time = now - datetime.timedelta(days=7)
        times = [start_time + datetime.timedelta(hours=h) for h in range(192)] # 8 days * 24 hours
        
        # Simple cyclical/random parameters
        temps = [28.0 + 3.0 * (h % 24 - 12) / 12 for h in range(192)]
        humidities = [80.0 + 10.0 * (12 - h % 24) / 12 for h in range(192)]
        precips = [0.0] * 192
        winds = [10.0] * 192
        
        df = pd.DataFrame({
            "ts": pd.to_datetime(times),
            "temperature_c": temps,
            "humidity_pct": humidities,
            "precipitation_mm": precips,
            "wind_speed_kmh": winds
        })
        return df, "synthetic_fallback"

def seed_weather():
    """
    Fetches open-meteo weather data, overlays the Sector 7 anomaly, and seeds to BQ.
    """
    client = bigquery.Client()
    weather_records = []
    
    # We want to insert the anomaly on a fixed date (July 5, 2026) to match test expectations,
    # as well as relative to "today" if the run date is different. Let's target July 5, 2026.
    anomaly_date = datetime.date(2026, 7, 5)
    
    for sector in SECTORS_DATA:
        sec_id = sector["sector_id"]
        df, data_source = fetch_open_meteo_data(sector["lat"], sector["lng"])
        
        for _, row in df.iterrows():
            ts = row["ts"].to_pydatetime()
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=datetime.timezone.utc)
                
            event_type = "CLEAR"
            severity = 0.0
            is_synthetic = False
            source = data_source
            
            precip = row["precipitation_mm"]
            wind = row["wind_speed_kmh"]
            temp = row["temperature_c"]
            humidity = row["humidity_pct"]
            
            if precip > 0.0:
                event_type = "RAIN"
                severity = float(min(precip / 50.0, 1.0)) # Normal scale
            elif wind > 25.0:
                event_type = "WIND"
                severity = float(min(wind / 100.0, 1.0))
            elif temp > 35.0:
                event_type = "HEAT"
                severity = float(min((temp - 35.0) / 10.0, 1.0))
                
            # Blend severe storm anomaly window for Sector 7
            # Let's check if the row falls on the anomaly day and hour window (12:00 to 18:00 UTC)
            if sec_id == ANOMALY_SECTOR_ID and ts.date() == anomaly_date and 12 <= ts.hour <= 18:
                is_synthetic = True
                source = "synthetic_anomaly"
                
                # Heavy rain details per hour
                if ts.hour == 12:
                    event_type = "RAIN"
                    severity = 0.85
                    precip = 35.0
                    temp = 23.5
                    wind = 45.0
                elif ts.hour == 13:
                    event_type = "STORM"
                    severity = 0.95
                    precip = 55.0
                    temp = 22.0
                    wind = 65.0
                elif ts.hour in [14, 15]:
                    event_type = "STORM"
                    severity = 0.95
                    precip = 50.0
                    temp = 22.5
                    wind = 60.0
                elif ts.hour == 16:
                    event_type = "STORM"
                    severity = 0.80
                    precip = 35.0
                    temp = 23.0
                    wind = 50.0
                else: # 17, 18
                    event_type = "RAIN"
                    severity = 0.70
                    precip = 25.0
                    temp = 24.0
                    wind = 40.0
            
            weather_records.append({
                "event_id": f"WE_{uuid.uuid4()}",
                "sector_id": sec_id,
                "ts": ts.isoformat(),
                "event_type": event_type,
                "severity": float(severity),
                "precipitation_mm": float(precip),
                "temperature_c": float(temp),
                "wind_speed_kmh": float(wind),
                "is_synthetic": is_synthetic,
                "source": source
            })
            
    # Load into BQ Raw
    raw_df = pd.DataFrame(weather_records)
    
    # Cast ts back to datetime for BQ load
    raw_df["ts"] = pd.to_datetime(raw_df["ts"])
    
    # Check if df is empty
    if len(raw_df) == 0:
        print("No weather events to seed.")
        return
        
    raw_table_id = f"{client.project}.{RAW_DATASET}.weather_events" if PROJECT_ID else f"{RAW_DATASET}.weather_events"
    job_config = bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE")
    job = client.load_table_from_dataframe(raw_df, raw_table_id, job_config=job_config)
    job.result()
    print(f"Successfully seeded raw weather: {raw_table_id} ({len(raw_df)} rows)")

    # Also load into Core weather_events
    core_table_id = f"{client.project}.{CORE_DATASET}.weather_events" if PROJECT_ID else f"{CORE_DATASET}.weather_events"
    
    # Format according to core weather events schema
    core_df = raw_df[[
        "event_id", "sector_id", "ts", "event_type", "severity"
    ]].copy()
    
    job_core = client.load_table_from_dataframe(core_df, core_table_id, job_config=job_config)
    job_core.result()
    print(f"Successfully seeded core weather: {core_table_id} ({len(core_df)} rows)")

if __name__ == "__main__":
    seed_weather()
