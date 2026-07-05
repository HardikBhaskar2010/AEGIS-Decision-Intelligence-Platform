# tests/unit/data/test_seeding.py
import datetime
import pytest
from unittest.mock import MagicMock, patch
import pandas as pd
import os


from backend.data.seeding.seed_sectors import seed_sectors
from backend.data.seeding.seed_weather import fetch_open_meteo_data, seed_weather
from backend.data.seeding.seed_generators import generate_llm_complaints_with_gemini, seed_generators, FALLBACK_ANOMALY_COMPLAINTS

@patch("google.cloud.bigquery.Client")
def test_seed_sectors(mock_bq_client):
    """
    Verifies that seed_sectors reads configuration data and sends it to BigQuery.
    """
    mock_instance = MagicMock()
    mock_instance.project = "test-project"
    mock_bq_client.return_value = mock_instance
    
    seed_sectors()
    
    # Assert that load_table_from_dataframe was called twice (once for raw, once for core)
    assert mock_instance.load_table_from_dataframe.call_count == 2
    
    # Get dataframe passed in first call
    args, kwargs = mock_instance.load_table_from_dataframe.call_args_list[0]
    df_passed = args[0]
    table_id_passed = args[1]
    
    assert isinstance(df_passed, pd.DataFrame)
    assert "sector_id" in df_passed.columns
    assert "lat" in df_passed.columns
    assert "aegis_raw.sectors" in table_id_passed

@patch("requests.get")
def test_fetch_open_meteo_data_success(mock_get):
    """
    Tests successful weather retrieval from Open-Meteo.
    """
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "hourly": {
            "time": ["2026-07-05T12:00", "2026-07-05T13:00"],
            "temperature_2m": [28.5, 27.2],
            "relative_humidity_2m": [82, 85],
            "precipitation": [0.0, 2.5],
            "wind_speed_10m": [12.0, 15.0]
        }
    }
    mock_get.return_value = mock_response
    
    df, source = fetch_open_meteo_data(1.2903, 103.8520)
    
    assert source == "open_meteo_api"
    assert len(df) == 2
    assert df.iloc[0]["temperature_c"] == 28.5
    assert df.iloc[1]["precipitation_mm"] == 2.5

@patch("requests.get")
def test_fetch_open_meteo_data_failure_fallback(mock_get):
    """
    Tests fallback behavior when Open-Meteo API fails or is offline.
    """
    mock_get.side_effect = Exception("Connection Timeout")
    
    df, source = fetch_open_meteo_data(1.2903, 103.8520)
    
    assert source == "synthetic_fallback"
    assert len(df) == 192 # 8 days of hourly records
    assert "temperature_c" in df.columns
    assert "precipitation_mm" in df.columns

@patch("google.cloud.bigquery.Client")
@patch("backend.data.seeding.seed_weather.fetch_open_meteo_data")
def test_seed_weather_blends_anomaly(mock_fetch, mock_bq_client):
    """
    Verifies that seed_weather overrides Sector 7 records during the anomaly storm window.
    """
    mock_instance = MagicMock()
    mock_instance.project = "test-project"
    mock_bq_client.return_value = mock_instance
    
    # Mock weather fetch to return standard clear weather
    times = [
        datetime.datetime(2026, 7, 5, 11, 0, tzinfo=datetime.timezone.utc),
        datetime.datetime(2026, 7, 5, 13, 0, tzinfo=datetime.timezone.utc), # inside anomaly hour
        datetime.datetime(2026, 7, 5, 19, 0, tzinfo=datetime.timezone.utc)
    ]
    df_weather = pd.DataFrame({
        "ts": pd.to_datetime(times),
        "temperature_c": [28.0, 28.0, 28.0],
        "humidity_pct": [80, 80, 80],
        "precipitation_mm": [0.0, 0.0, 0.0],
        "wind_speed_kmh": [10.0, 10.0, 10.0]
    })
    mock_fetch.return_value = (df_weather, "open_meteo_api")
    
    seed_weather()
    
    # Get dataframe passed in raw load call
    args, kwargs = mock_instance.load_table_from_dataframe.call_args_list[0]
    df_raw = args[0]
    
    # Filter Sector 7
    s7_weather = df_raw[df_raw["sector_id"] == "sector_7"]
    
    # The 13:00 hour should be overwritten as anomaly STORM
    anomaly_row = s7_weather[s7_weather["ts"] == "2026-07-05T13:00:00+00:00"]
    assert len(anomaly_row) == 1
    assert anomaly_row.iloc[0]["event_type"] == "STORM"
    assert anomaly_row.iloc[0]["precipitation_mm"] == 55.0
    assert bool(anomaly_row.iloc[0]["is_synthetic"]) is True
    assert anomaly_row.iloc[0]["source"] == "synthetic_anomaly"

    # The 11:00 hour should remain CLEAR
    normal_row = s7_weather[s7_weather["ts"] == "2026-07-05T11:00:00+00:00"]
    assert len(normal_row) == 1
    assert normal_row.iloc[0]["event_type"] == "CLEAR"
    assert normal_row.iloc[0]["precipitation_mm"] == 0.0
    assert bool(normal_row.iloc[0]["is_synthetic"]) is False

@patch("google.genai.Client")
@patch.dict(os.environ, {"GEMINI_API_KEY": "fake-api-key"})
def test_generate_llm_complaints_with_gemini_success(mock_genai_class):
    """
    Tests that generate_llm_complaints_with_gemini successfully calls Gemini API.
    """
    mock_client = MagicMock()
    mock_genai_class.return_value = mock_client
    
    # Mock Gemini response returning a JSON array of strings
    mock_response = MagicMock()
    mock_response.text = '["Flooding is bad in Sector 7", "Red line MRT delayed"]'
    mock_client.models.generate_content.return_value = mock_response
    
    complaints = generate_llm_complaints_with_gemini("sector_7", 2, is_anomaly=True)
    
    assert len(complaints) == 2
    assert "Flooding is bad" in complaints[0]
    mock_client.models.generate_content.assert_called_once()

def test_generate_llm_complaints_fallback():
    """
    Tests that generator falls back gracefully if Gemini key is missing or calls fail.
    """
    with patch.dict(os.environ, {}, clear=True):
        complaints = generate_llm_complaints_with_gemini("sector_7", 3, is_anomaly=True)
        assert len(complaints) == 3
        # Assert they are drawn from the fallback list
        assert complaints[0] in FALLBACK_ANOMALY_COMPLAINTS

@patch("google.cloud.bigquery.Client")
@patch("backend.data.seeding.seed_generators.generate_llm_complaints_with_gemini")
def test_seed_generators_all_synthetic(mock_gen, mock_bq_client):
    """
    Verifies that seed_generators configures status fields and labels all records as synthetic.
    """
    mock_instance = MagicMock()
    mock_instance.project = "test-project"
    mock_bq_client.return_value = mock_instance
    
    mock_gen.return_value = ["Mocked complaint text"]
    
    seed_generators()
    
    # Get dataframe passed in transit load call
    transit_call = mock_instance.load_table_from_dataframe.call_args_list[0]
    transit_df = transit_call[0][0]
    assert all(transit_df["is_synthetic"])
    
    # Get dataframe passed in utility load call
    utility_call = mock_instance.load_table_from_dataframe.call_args_list[1]
    utility_df = utility_call[0][0]
    assert all(utility_df["is_synthetic"])

    # Get dataframe passed in feedback load call
    feedback_call = mock_instance.load_table_from_dataframe.call_args_list[2]
    feedback_df = feedback_call[0][0]
    assert all(feedback_df["is_synthetic"])
