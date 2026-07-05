# backend/data/pipeline/enrich_classify.py
import json
import os
import datetime
from google.cloud import bigquery
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from backend.data.config import PROJECT_ID, RAW_DATASET, CORE_DATASET

class FeedbackClassification(BaseModel):
    category: str = Field(description="Classification: 'transit', 'utility', 'infrastructure', 'safety', 'health', or 'other'")
    sentiment: str = Field(description="Sentiment: 'positive', 'neutral', 'negative', or 'critical'")
    sentiment_score: float = Field(description="Float sentiment rating between -1.0 and 1.0")
    rationale: str = Field(description="A brief 1-sentence reasoning for the sentiment tag")

def fallback_classify_feedback(text: str) -> dict:
    """
    Determines basic category and sentiment using keyword heuristics if Gemini API fails.
    """
    text_lower = text.lower()
    
    # 1. Determine category
    if any(w in text_lower for w in ["bus", "mrt", "train", "transit", "commute", "station", "delay", "line"]):
        category = "transit"
    elif any(w in text_lower for w in ["flood", "waterlogging", "rain", "drain", "sewer", "road", "pavement", "sidewalk", "street", "underwater"]):
        category = "infrastructure"
    elif any(w in text_lower for w in ["power", "outage", "blackout", "utility", "electricity", "grid", "substation", "light", "water", "gas", "telecom"]):
        category = "utility"

    elif any(w in text_lower for w in ["fire", "hazard", "wire", "danger", "safe", "crime", "thief"]):
        category = "safety"
    elif any(w in text_lower for w in ["smell", "garbage", "trash", "toxic", "disease", "health", "fume"]):
        category = "health"
    else:
        category = "other"
        
    # 2. Determine sentiment
    if any(w in text_lower for w in ["critical", "emergency", "unsafe", "hazard", "dangerous", "crisis", "blackout", "flooded"]):
        sentiment = "critical"
        sentiment_score = -0.9
    elif any(w in text_lower for w in ["late", "fail", "bad", "broken", "annoyed", "outage", "delay", "stuck"]):
        sentiment = "negative"
        sentiment_score = -0.6
    elif any(w in text_lower for w in ["good", "great", "nice", "operational", "smooth", "happy", "fine"]):
        sentiment = "positive"
        sentiment_score = 0.8
    else:
        sentiment = "neutral"
        sentiment_score = 0.0
        
    return {
        "category": category,
        "sentiment": sentiment,
        "sentiment_score": sentiment_score,
        "rationale": "Fallback keyword classification"
    }

def classify_feedback_with_gemini(text: str) -> dict:
    """
    Calls Gemini 3 Flash (gemini-2.5-flash) to classify a feedback text.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return fallback_classify_feedback(text)
        
    try:
        client = genai.Client(api_key=api_key)
        prompt = f"Analyze this citizen report: \"{text}\""
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=(
                    "You are an AI classifier for the Gemini Enterprise Agent Platform. "
                    "Classify the text into one of the allowed categories: transit, utility, infrastructure, safety, health, other. "
                    "Classify the sentiment into one of the allowed sentiments: positive, neutral, negative, critical."
                ),
                response_mime_type="application/json",
                response_schema=FeedbackClassification,
                temperature=0.0
            ),
        )
        parsed = json.loads(response.text.strip())
        return parsed
    except Exception as e:
        print(f"Gemini classification call failed: {e}. Executing fallback parser.")
        return fallback_classify_feedback(text)

def run_enrich_classify_pipeline():
    """
    Retrieves un-enriched citizen feedback from raw dataset, runs Gemini enrichment,
    and loads results into core.citizen_feedback.
    """
    bq_client = bigquery.Client()
    
    raw_table = f"{bq_client.project}.{RAW_DATASET}.citizen_feedback" if PROJECT_ID else f"{RAW_DATASET}.citizen_feedback"
    core_table = f"{bq_client.project}.{CORE_DATASET}.citizen_feedback" if PROJECT_ID else f"{CORE_DATASET}.citizen_feedback"
    
    # Differential Query: get rows in raw that are not in core yet
    query = f"""
        SELECT feedback_id, sector_id, ts, raw_text, is_synthetic
        FROM `{raw_table}`
        WHERE feedback_id NOT IN (SELECT feedback_id FROM `{core_table}`)
    """
    
    print("Running differential query...")
    try:
        query_job = bq_client.query(query)
        rows = list(query_job.result())
    except Exception as e:
        print(f"Error querying differential feedback: {e}. Assuming first-run or core table empty.")
        # Fallback to query raw directly
        query_fallback = f"""
            SELECT feedback_id, sector_id, ts, raw_text, is_synthetic
            FROM `{raw_table}`
        """
        query_job = bq_client.query(query_fallback)
        rows = list(query_job.result())
        
    if not rows:
        print("No new feedback records to enrich.")
        return
        
    print(f"Found {len(rows)} new records to enrich. Running classification...")
    
    enriched_records = []
    for row in rows:
        classification = classify_feedback_with_gemini(row.raw_text)
        
        # Ensure timestamp is formatted as ISO string
        ts_val = row.ts
        if isinstance(ts_val, datetime.datetime):
            ts_str = ts_val.isoformat()
        else:
            ts_str = str(ts_val)
            
        enriched_records.append({
            "feedback_id": row.feedback_id,
            "sector_id": row.sector_id,
            "ts": ts_str,
            "category": classification.get("category", "other").lower(),
            "sentiment": classification.get("sentiment", "neutral").lower(),
            "raw_text": row.raw_text
        })
        
    # Batch load into core.citizen_feedback
    print(f"Loading {len(enriched_records)} enriched records into core dataset...")
    
    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND
    )
    
    load_job = bq_client.load_table_from_json(
        enriched_records,
        core_table,
        job_config=job_config
    )
    load_job.result()
    print(f"Successfully enriched and loaded {len(enriched_records)} records into {core_table}")

if __name__ == "__main__":
    run_enrich_classify_pipeline()
