# backend/data/seeding/seed_generators.py
import uuid
import datetime
import random
import json
import os
import pandas as pd
from google.cloud import bigquery
from google import genai
from google.genai import types
from backend.data.config import PROJECT_ID, RAW_DATASET, CORE_DATASET, SECTORS_DATA, ANOMALY_SECTOR_ID

# Heuristic fallback lists for offline/missing key runs
FALLBACK_ANOMALY_COMPLAINTS = [
    "Cross St is completely waterlogged! Downtown MRT exit flooded. Need support immediately.",
    "Major blackout here in Sector 7 civic area. Street lights are out and traffic is locked. Extreme hazard!",
    "Water is rising, basement parking in Downtown office block is flooding and power has gone off. Civic emergency.",
    "Power went out in Sector 7! The whole block is pitch black. This is unsafe.",
    "Red Line is suspended, the traffic lights are out, and I am stuck in the dark in Sector 7.",
    "Severe flooding on the main avenue. Drains are bubbling up. Power is dead.",
    "Low pressure on municipal water, utility lines must be damaged from this storm.",
    "Sector 7 Main Substation flooded. We need emergency crews here.",
    "Stuck at the MRT station, track is completely flooded. No shuttle buses in sight.",
    "Total dark in the downtown area. Grid is down."
]

FALLBACK_NORMAL_COMPLAINTS = [
    "Bus 42 is running late today. Comfy commute otherwise.",
    "Flickering streetlight on the corner of 5th street.",
    "Pothole spotted in the right lane of Orchard road.",
    "Litter bins are overflowing near the community center.",
    "Water pressure is a bit low this morning, but manageable.",
    "MRT commute was smooth. Clean train.",
    "A bit of congestion at the main intersection, normal weekday.",
    "Nice weather today. Parks are clean.",
    "Telecom signal is weak near the high rises.",
    "Sidewalk tiles are loose near the bus stop."
]

def generate_llm_complaints_with_gemini(sector_id, num_complaints, is_anomaly=False):
    """
    Calls Gemini 3 Flash (gemini-2.5-flash) using google-genai to generate citizen feedback raw text.
    Uses fallback heuristic lists if API key is not present or calls fail.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY not set. Using offline fallback citizen complaints.")
        source_list = FALLBACK_ANOMALY_COMPLAINTS if is_anomaly else FALLBACK_NORMAL_COMPLAINTS
        return [random.choice(source_list) for _ in range(num_complaints)]

    try:
        client = genai.Client(api_key=api_key)
        
        prompt = (
            f"Generate {num_complaints} realistic, short, casual citizen complaints or municipal reports "
            f"(each under 160 characters) written by citizens in {sector_id}. "
        )
        if is_anomaly:
            prompt += (
                "The complaints must report severe flooding, heavy storm rain, MRT train suspension, "
                "or a major electrical blackout. The tone should be urgent and worried."
            )
        else:
            prompt += (
                "The reports should cover minor daily issues like a pothole, flickering streetlight, "
                "minor bus delay, or overflowing trash bin. Keep the tone casual."
            )
            
        prompt += "\nReturn ONLY a JSON array of strings. Do not include markdown code block formatting."

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.7,
                response_mime_type="application/json"
            )
        )
        
        text_content = response.text.strip()
        # Strip markdown tags if LLM output still includes them
        if text_content.startswith("```"):
            lines = text_content.splitlines()
            if lines[0].startswith("```json") or lines[0].startswith("```"):
                text_content = "\n".join(lines[1:-1])
                
        complaints = json.loads(text_content)
        if isinstance(complaints, list) and all(isinstance(x, str) for x in complaints):
            return complaints[:num_complaints]
        else:
            raise ValueError("LLM did not return a list of strings")
            
    except Exception as e:
        print(f"Gemini API generation failed: {e}. Executing fallback complaints.")
        source_list = FALLBACK_ANOMALY_COMPLAINTS if is_anomaly else FALLBACK_NORMAL_COMPLAINTS
        return [random.choice(source_list) for _ in range(num_complaints)]

def seed_generators():
    """
    Generates synthetic historical transit, utility and feedback data, then seeds to BQ.
    """
    client = bigquery.Client()
    
    # 7 days of simulated logs
    target_date = datetime.date(2026, 7, 5)
    start_time = datetime.datetime(2026, 6, 29, 0, 0, 0, tzinfo=datetime.timezone.utc)
    end_time = datetime.datetime(2026, 7, 6, 0, 0, 0, tzinfo=datetime.timezone.utc)
    
    transit_records = []
    utility_records = []
    feedback_records = []
    
    current_time = start_time
    delta_hour = datetime.timedelta(hours=1)
    
    print("Generating synthetic datasets...")
    
    while current_time < end_time:
        is_anomaly_day = (current_time.date() == target_date)
        is_anomaly_hour = (12 <= current_time.hour <= 18)
        
        for sector in SECTORS_DATA:
            sec_id = sector["sector_id"]
            
            # Default normal parameters
            t_status = "OPERATIONAL"
            t_delay = 0
            t_details = "Normal operation"
            
            u_status = "OPERATIONAL"
            u_affected = 0
            u_details = "Grid stable"
            
            # Target anomaly overlay for Sector 7
            if sec_id == ANOMALY_SECTOR_ID and is_anomaly_day and is_anomaly_hour:
                # 13:15:00 Grid Substation Failure
                # 13:30:00 Water Treatment degraded
                # 13:45:00 Metro Red Line Suspended
                if current_time.hour == 13:
                    u_status = "OUTAGE"
                    u_affected = 18500
                    u_details = "Sector 7 Main Substation flooded"
                    
                    t_status = "SUSPENDED"
                    t_delay = 120
                    t_details = "Flooding on tracks at Sector 7 Station"
                elif current_time.hour in [14, 15, 16]:
                    u_status = "OUTAGE"
                    u_affected = 18500
                    u_details = "Sector 7 Main Substation flooded"
                    
                    t_status = "SUSPENDED"
                    t_delay = 120
                    t_details = "Flooding on tracks at Sector 7 Station"
                elif current_time.hour in [17, 18]:
                    u_status = "DEGRADED"
                    u_affected = 8000
                    u_details = "Subsystem water pumps degraded due to main station power failure"
                    
                    t_status = "DELAYED"
                    t_delay = 60
                    t_details = "Single track operations after water clearance"
            else:
                # Standard random minor variations
                # Transit minor delays
                if random.random() < 0.03:
                    t_status = "DELAYED"
                    t_delay = random.randint(5, 25)
                    t_details = "Minor signal fault"
                # Utility minor outage
                if random.random() < 0.01:
                    u_status = "DEGRADED"
                    u_affected = random.randint(100, 800)
                    u_details = "Scheduled grid maintenance"
                    
            # Add transit record
            transit_records.append({
                "status_id": f"TR_{uuid.uuid4()}",
                "sector_id": sec_id,
                "ts": current_time.isoformat(),
                "line_id": "Metro-Red-Line" if sec_id == ANOMALY_SECTOR_ID else f"Bus-Route-{sec_id[-1]}",
                "status": t_status,
                "delay_minutes": int(t_delay),
                "raw_details": t_details,
                "is_synthetic": True
            })
            
            # Add utility record
            utility_records.append({
                "status_id": f"UT_{uuid.uuid4()}",
                "sector_id": sec_id,
                "ts": current_time.isoformat(),
                "utility_type": "POWER" if sec_id == ANOMALY_SECTOR_ID else "POWER",
                "status": u_status,
                "customers_affected": int(u_affected),
                "raw_details": u_details,
                "is_synthetic": True
            })
            
            # Generate citizen feedback volume
            # Base feedback count
            num_feedback = random.choice([0, 0, 0, 1])
            is_anomaly_here = False
            
            # Sector 7 anomaly spike
            if sec_id == ANOMALY_SECTOR_ID and is_anomaly_day and is_anomaly_hour:
                num_feedback = random.randint(15, 25)
                is_anomaly_here = True
                
            if num_feedback > 0:
                complaints_text = generate_llm_complaints_with_gemini(sec_id, num_feedback, is_anomaly_here)
                for text in complaints_text:
                    # Randomize feedback timestamp within the hour
                    offset_mins = random.randint(0, 59)
                    feedback_ts = current_time + datetime.timedelta(minutes=offset_mins)
                    
                    feedback_records.append({
                        "feedback_id": f"CF_{uuid.uuid4()}",
                        "sector_id": sec_id,
                        "ts": feedback_ts.isoformat(),
                        "raw_text": text,
                        "is_synthetic": True
                    })
                    
        current_time += delta_hour
        
    print(f"Generated {len(transit_records)} transit records.")
    print(f"Generated {len(utility_records)} utility records.")
    print(f"Generated {len(feedback_records)} feedback records.")
    
    # Load into BigQuery Raw tables
    transit_df = pd.DataFrame(transit_records)
    utility_df = pd.DataFrame(utility_records)
    feedback_df = pd.DataFrame(feedback_records)
    
    # Cast ts back to datetime
    transit_df["ts"] = pd.to_datetime(transit_df["ts"])
    utility_df["ts"] = pd.to_datetime(utility_df["ts"])
    feedback_df["ts"] = pd.to_datetime(feedback_df["ts"])
    
    # Raw tables write disposition is WRITE_TRUNCATE
    job_config = bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE")
    
    raw_transit_table = f"{client.project}.{RAW_DATASET}.transit_status" if PROJECT_ID else f"{RAW_DATASET}.transit_status"
    client.load_table_from_dataframe(transit_df, raw_transit_table, job_config=job_config).result()
    print(f"Successfully seeded raw transit: {raw_transit_table}")
    
    raw_utility_table = f"{client.project}.{RAW_DATASET}.utility_status" if PROJECT_ID else f"{RAW_DATASET}.utility_status"
    client.load_table_from_dataframe(utility_df, raw_utility_table, job_config=job_config).result()
    print(f"Successfully seeded raw utility: {raw_utility_table}")
    
    raw_feedback_table = f"{client.project}.{RAW_DATASET}.citizen_feedback" if PROJECT_ID else f"{RAW_DATASET}.citizen_feedback"
    client.load_table_from_dataframe(feedback_df, raw_feedback_table, job_config=job_config).result()
    print(f"Successfully seeded raw feedback: {raw_feedback_table}")

    # Transit status core
    core_transit_table = f"{client.project}.{CORE_DATASET}.transit_status" if PROJECT_ID else f"{CORE_DATASET}.transit_status"
    core_transit_df = transit_df[['status_id', 'sector_id', 'ts', 'line_id', 'status']].copy()
    client.load_table_from_dataframe(core_transit_df, core_transit_table, job_config=job_config).result()
    print(f"Successfully seeded core transit: {core_transit_table}")

    # Utility status core
    core_utility_table = f"{client.project}.{CORE_DATASET}.utility_status" if PROJECT_ID else f"{CORE_DATASET}.utility_status"
    core_utility_df = utility_df[['status_id', 'sector_id', 'ts', 'utility_type', 'status']].copy()
    client.load_table_from_dataframe(core_utility_df, core_utility_table, job_config=job_config).result()
    print(f"Successfully seeded core utility: {core_utility_table}")

if __name__ == "__main__":
    seed_generators()
