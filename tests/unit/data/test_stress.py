# tests/unit/data/test_stress.py
import pytest
import pandas as pd
import datetime
from backend.data.pipeline.summarize import calculate_z_scores_pandas

def test_stress_zero_std_deviation():
    """
    Edge Case: The preceding 24 hours have completely constant feedback counts.
    Thus, standard deviation is 0.
    Verify that calculate_z_scores_pandas handles division-by-zero gracefully
    and returns 0.0 z-score (no anomaly).
    """
    times = [datetime.datetime(2026, 7, 5, 0, 0) + datetime.timedelta(hours=h) for h in range(25)]
    feedback_counts = [0] * 24 + [1]  # Constant 0 for 24 hours, then a single complaint
    
    df = pd.DataFrame({
        "ts": times,
        "sector_id": ["sector_1"] * 25,
        "feedback_count": feedback_counts
    })
    
    df_result = calculate_z_scores_pandas(df, window=24)
    spike_row = df_result.iloc[24]
    
    # Preceding 24 hours all had count 0 -> stddev = 0.
    # The anomaly_score should fall back to 0.0 rather than raising division by zero or NaN.
    assert spike_row["rolling_std"] == 0.0
    assert spike_row["anomaly_score"] == 0.0
    assert bool(spike_row["anomaly_flag"]) is False

def test_stress_huge_spike():
    """
    Edge Case: Extremely large volume spikes (e.g., 10,000 complaints).
    Verify that z-score calculations remain stable and flag the anomaly.
    """
    times = [datetime.datetime(2026, 7, 5, 0, 0) + datetime.timedelta(hours=h) for h in range(25)]
    # Baseline alternating between 1 and 2, then massive spike
    feedback_counts = [1, 2] * 12 + [10000]
    
    df = pd.DataFrame({
        "ts": times,
        "sector_id": ["sector_1"] * 25,
        "feedback_count": feedback_counts
    })
    
    df_result = calculate_z_scores_pandas(df, window=24)
    spike_row = df_result.iloc[24]
    
    assert spike_row["feedback_count"] == 10000
    assert spike_row["anomaly_score"] > 10000.0  # (10000 - 1.5) / 0.5175 = ~19320.0
    assert bool(spike_row["anomaly_flag"]) is True

def test_stress_multiple_sectors():
    """
    Verify that the groupby partitions calculations correctly across multiple sectors,
    ensuring that a spike in Sector A does not leak or affect calculations in Sector B.
    """
    times = [datetime.datetime(2026, 7, 5, 0, 0) + datetime.timedelta(hours=h) for h in range(25)]
    
    # Sector A: low baseline with a spike at hour 25
    feedback_a = [1, 2] * 12 + [100]
    # Sector B: high baseline with no spike at hour 25
    feedback_b = [50, 60] * 12 + [55]
    
    df_a = pd.DataFrame({
        "ts": times,
        "sector_id": ["sector_A"] * 25,
        "feedback_count": feedback_a
    })
    
    df_b = pd.DataFrame({
        "ts": times,
        "sector_id": ["sector_B"] * 25,
        "feedback_count": feedback_b
    })
    
    df = pd.concat([df_a, df_b]).reset_index(drop=True)
    
    df_result = calculate_z_scores_pandas(df, window=24)
    
    # Filter back
    res_a = df_result[df_result["sector_id"] == "sector_A"].sort_values("ts")
    res_b = df_result[df_result["sector_id"] == "sector_B"].sort_values("ts")
    
    spike_a = res_a.iloc[24]
    normal_b = res_b.iloc[24]
    
    assert bool(spike_a["anomaly_flag"]) is True
    assert spike_a["anomaly_score"] > 2.0
    
    assert bool(normal_b["anomaly_flag"]) is False
    assert normal_b["anomaly_score"] <= 0.0  # 55 is exactly the mean of 50 and 60, so z-score is 0
