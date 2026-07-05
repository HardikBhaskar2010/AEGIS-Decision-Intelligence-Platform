# backend/data/config.py
import os

PROJECT_ID = os.getenv("GCP_PROJECT", "")
RAW_DATASET = os.getenv("BQ_RAW_DATASET", "aegis_raw")
CORE_DATASET = os.getenv("BQ_CORE_DATASET", "aegis_core")
GCS_LANDING_BUCKET = os.getenv("AEGIS_LANDING_BUCKET", "aegis-data-landing")

# Target Sector for the demo multi-domain anomaly
ANOMALY_SECTOR_ID = "sector_7"

# Standard Sector list based on Singapore/Metropolitan coordinate reference
SECTORS_DATA = [
    {"sector_id": "sector_1", "name": "Changi Logistics Hub", "lat": 1.3644, "lng": 103.9915, "population": 120000},
    {"sector_id": "sector_2", "name": "Marina Bay Financial", "lat": 1.2829, "lng": 103.8586, "population": 35000},
    {"sector_id": "sector_3", "name": "Jurong Industrial", "lat": 1.3263, "lng": 103.7384, "population": 95000},
    {"sector_id": "sector_4", "name": "Woodlands Crossing", "lat": 1.4369, "lng": 103.7865, "population": 240000},
    {"sector_id": "sector_5", "name": "Ang Mo Kio Heartland", "lat": 1.3698, "lng": 103.8496, "population": 165000},
    {"sector_id": "sector_6", "name": "Bedok Waterfront", "lat": 1.3240, "lng": 103.9293, "population": 280000},
    {"sector_id": "sector_7", "name": "Downtown / Civic Center", "lat": 1.2903, "lng": 103.8520, "population": 85000},
    {"sector_id": "sector_8", "name": "Tampines East", "lat": 1.3530, "lng": 103.9452, "population": 220000},
    {"sector_id": "sector_9", "name": "Queenstown Residential", "lat": 1.2942, "lng": 103.8059, "population": 98000},
    {"sector_id": "sector_10", "name": "Sentosa Resort Coast", "lat": 1.2494, "lng": 103.8303, "population": 8000}
]
