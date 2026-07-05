# tests/unit/data/test_pipeline.py
import pytest
import datetime
from unittest.mock import MagicMock, patch
import pandas as pd
import json
import os


from backend.data.pipeline.ingest import upload_to_gcs, load_gcs_to_bigquery_raw, run_ingestion_for_file
from backend.data.pipeline.enrich_classify import fallback_classify_feedback, classify_feedback_with_gemini, run_enrich_classify_pipeline
from backend.data.pipeline.summarize import calculate_z_scores_pandas, run_hourly_rollup

@patch("google.cloud.storage.Client")
def test_upload_to_gcs(mock_storage_client):
    """
    Tests GCS file upload mapping.
    """
    mock_instance = MagicMock()
    mock_storage_client.return_value = mock_instance
    mock_bucket = MagicMock()
    mock_instance.bucket.return_value = mock_bucket
    mock_blob = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    
    # We mock local file path
    with patch("os.path.basename", return_value="sectors.csv"):
        uri = upload_to_gcs("dummy/path/sectors.csv", "landing/sectors.csv")
        
    assert uri == "gs://aegis-data-landing/landing/sectors.csv"
    mock_blob.upload_from_filename.assert_called_once_with("dummy/path/sectors.csv")

@patch("google.cloud.bigquery.Client")
def test_load_gcs_to_bigquery_raw(mock_bq_client):
    """
    Tests BigQuery load job trigger.
    """
    mock_instance = MagicMock()
    mock_bq_client.return_value = mock_instance
    
    load_gcs_to_bigquery_raw("gs://aegis-data-landing/landing/sectors.csv", "sectors", source_format="CSV")
    
    mock_instance.load_table_from_uri.assert_called_once()
    args, kwargs = mock_instance.load_table_from_uri.call_args
    assert args[0] == "gs://aegis-data-landing/landing/sectors.csv"
    assert "sectors" in args[1]
    assert kwargs["job_config"].source_format == "CSV"

def test_fallback_classify_feedback():
    """
    Tests keyword-based classification fallback logic.
    """
    # 1. Test critical infrastructure flood report
    res_1 = fallback_classify_feedback("Downtown area is completely flooded and underwater!")
    assert res_1["category"] == "infrastructure"
    assert res_1["sentiment"] == "critical"
    assert res_1["sentiment_score"] == -0.9

    # 2. Test negative transit delay report
    res_2 = fallback_classify_feedback("Bus 42 is late again, been waiting 20 minutes")
    assert res_2["category"] == "transit"
    assert res_2["sentiment"] == "negative"
    assert res_2["sentiment_score"] == -0.6

    # 3. Test utility outage report
    res_3 = fallback_classify_feedback("Power is out on my block. Complete blackout.")
    assert res_3["category"] == "utility"
    assert res_3["sentiment"] == "critical" # "blackout" triggers critical
    
    # 4. Test positive report
    res_4 = fallback_classify_feedback("The park is nice and clean, MRT ran smooth today.")
    assert res_4["category"] == "transit" # "mrt" triggers transit
    assert res_4["sentiment"] == "positive"
    assert res_4["sentiment_score"] == 0.8

@patch("google.genai.Client")
@patch.dict(os.environ, {"GEMINI_API_KEY": "fake-key"})
def test_classify_feedback_with_gemini_success(mock_genai_class):
    """
    Verifies that classify_feedback_with_gemini queries Gemini and parses response.
    """
    mock_client = MagicMock()
    mock_genai_class.return_value = mock_client
    mock_response = MagicMock()
    mock_response.text = '{"category": "safety", "sentiment": "critical", "sentiment_score": -0.95, "rationale": "Exposed wires reported."}'
    mock_client.models.generate_content.return_value = mock_response
    
    res = classify_feedback_with_gemini("Warning: live wires hanging on Main St!")
    
    assert res["category"] == "safety"
    assert res["sentiment"] == "critical"
    assert res["sentiment_score"] == -0.95

@patch("google.cloud.bigquery.Client")
@patch("backend.data.pipeline.enrich_classify.classify_feedback_with_gemini")
def test_run_enrich_classify_pipeline(mock_classify, mock_bq_client):
    """
    Verifies that the enrichment pipeline queries raw, runs enrichment, and loads to core.
    """
    mock_instance = MagicMock()
    mock_bq_client.return_value = mock_instance
    
    # Mock differential query results
    mock_row_1 = MagicMock()
    mock_row_1.feedback_id = "CF_1"
    mock_row_1.sector_id = "sector_7"
    mock_row_1.ts = datetime.datetime(2026, 7, 5, 14, 0, 0, tzinfo=datetime.timezone.utc)
    mock_row_1.raw_text = "Flooding on track"
    mock_row_1.is_synthetic = True
    
    mock_job = MagicMock()
    mock_job.result.return_value = [mock_row_1]
    mock_instance.query.return_value = mock_job
    
    # Mock classification
    mock_classify.return_value = {
        "category": "infrastructure",
        "sentiment": "critical",
        "sentiment_score": -0.9
    }
    
    run_enrich_classify_pipeline()
    
    mock_instance.load_table_from_json.assert_called_once()
    args, kwargs = mock_instance.load_table_from_json.call_args
    records_loaded = args[0]
    
    assert len(records_loaded) == 1
    assert records_loaded[0]["feedback_id"] == "CF_1"
    assert records_loaded[0]["category"] == "infrastructure"
    assert records_loaded[0]["sentiment"] == "critical"

def test_calculate_z_scores_pandas():
    """
    Tests the mathematical implementation of the rolling z-score formula.
    """
    # Create time series data for 25 hours
    times = [datetime.datetime(2026, 7, 5, 0, 0) + datetime.timedelta(hours=h) for h in range(25)]
    
    # 24 hours of low baseline (alternating 1 and 2 complaints)
    # mean: 1.5, standard deviation: 0.5175
    feedback_counts = [1, 2] * 12 + [15] # 24 baseline, 25th hour spike
    
    df = pd.DataFrame({
        "ts": times,
        "sector_id": ["sector_7"] * 25,
        "feedback_count": feedback_counts
      })
      
    df_result = calculate_z_scores_pandas(df, window=24)
    
    # Check 25th row (index 24)
    spike_row = df_result.iloc[24]
    
    assert spike_row["feedback_count"] == 15
    assert spike_row["rolling_mean"] == pytest.approx(1.5, 0.05)
    # rolling standard deviation should be non-zero
    assert spike_row["rolling_std"] > 0.4
    
    # z-score should be: (15 - 1.5) / stddev = 13.5 / ~0.5 = ~26
    assert spike_row["anomaly_score"] > 2.0
    assert bool(spike_row["anomaly_flag"]) is True

    
    # Check baseline row (e.g. index 10)
    baseline_row = df_result.iloc[10]
    assert bool(baseline_row["anomaly_flag"]) is False

