# backend/data/pipeline/summarize.py
import pandas as pd
from google.cloud import bigquery
from backend.data.config import PROJECT_ID, CORE_DATASET, RAW_DATASET

def calculate_z_scores_pandas(df, window=24):
    """
    Calculates rolling z-scores on a dataframe sorted by ts.
    df must have columns: 'ts', 'sector_id', 'feedback_count'.
    It shifts by 1 to exclude the current hour from the baseline mean/std.
    """
    df = df.sort_values(["sector_id", "ts"]).copy()
    
    # Calculate rolling mean and std of feedback_count
    # Using raw window values, then shifting to exclude current row
    grouped = df.groupby("sector_id")["feedback_count"]
    
    # Resetting index level to align properly with sorted df
    rolling_mean = grouped.rolling(window=window, min_periods=1).mean().reset_index(level=0, drop=True)
    rolling_std = grouped.rolling(window=window, min_periods=1).std().reset_index(level=0, drop=True)
    
    # Shift within groups to exclude current row
    df["rolling_mean"] = rolling_mean.groupby(df["sector_id"]).shift(1).fillna(0.0)
    df["rolling_std"] = rolling_std.groupby(df["sector_id"]).shift(1).fillna(0.0)
    
    # Calculate z-score
    def calc_z(row):
        mean = row["rolling_mean"]
        std = row["rolling_std"]
        count = row["feedback_count"]
        if std == 0 or pd.isna(std):
            return 0.0
        return (count - mean) / std
        
    df["anomaly_score"] = df.apply(calc_z, axis=1)
    df["anomaly_flag"] = df["anomaly_score"] > 2.0
    return df

def run_hourly_rollup():
    """
    Executes a BigQuery query to aggregate hourly metrics across transit, utility,
    weather and citizen feedback, calculates a rolling 24-hour z-score for feedback
    volume, and writes/overwrites the aegis_core.summary_rollup table.
    """
    bq_client = bigquery.Client()
    
    sectors_table = f"{bq_client.project}.{CORE_DATASET}.sectors" if PROJECT_ID else f"{CORE_DATASET}.sectors"
    feedback_table = f"{bq_client.project}.{CORE_DATASET}.citizen_feedback" if PROJECT_ID else f"{CORE_DATASET}.citizen_feedback"
    utility_table = f"{bq_client.project}.{CORE_DATASET}.utility_status" if PROJECT_ID else f"{CORE_DATASET}.utility_status"
    transit_table = f"{bq_client.project}.{RAW_DATASET}.transit_status" if PROJECT_ID else f"{RAW_DATASET}.transit_status"
    weather_table = f"{bq_client.project}.{CORE_DATASET}.weather_events" if PROJECT_ID else f"{CORE_DATASET}.weather_events"
    rollup_table = f"{bq_client.project}.{CORE_DATASET}.summary_rollup" if PROJECT_ID else f"{CORE_DATASET}.summary_rollup"
    
    query = f"""
    WITH hours AS (
      SELECT DISTINCT TIMESTAMP_TRUNC(ts, HOUR) as hour_ts 
      FROM `{transit_table}`
    ),
    sector_grid AS (
      SELECT s.sector_id, h.hour_ts
      FROM `{sectors_table}` s
      CROSS JOIN hours h
    ),
    hourly_metrics AS (
      SELECT 
        g.hour_ts,
        g.sector_id,
        COALESCE(f.feedback_count, 0) as feedback_count,
        COALESCE(f.avg_sentiment_score, 0.0) as avg_sentiment_score,
        COALESCE(f.negative_feedback_count, 0) as negative_feedback_count,
        COALESCE(f.critical_feedback_count, 0) as critical_feedback_count,
        COALESCE(u.active_utility_outages, 0) as active_utility_outages,
        COALESCE(t.transit_delay_minutes, 0) as transit_delay_minutes,
        COALESCE(w.max_weather_severity, 0.0) as max_weather_severity
      FROM sector_grid g
      LEFT JOIN (
        SELECT 
          TIMESTAMP_TRUNC(ts, HOUR) as hour_ts,
          sector_id,
          COUNT(feedback_id) as feedback_count,
          AVG(CASE WHEN sentiment = 'positive' THEN 1.0 WHEN sentiment = 'neutral' THEN 0.0 WHEN sentiment = 'negative' THEN -0.6 WHEN sentiment = 'critical' THEN -0.9 ELSE 0.0 END) as avg_sentiment_score,
          COUNTIF(sentiment = 'negative') as negative_feedback_count,
          COUNTIF(sentiment = 'critical') as critical_feedback_count
        FROM `{feedback_table}`
        GROUP BY hour_ts, sector_id
      ) f ON g.sector_id = f.sector_id AND g.hour_ts = f.hour_ts
      LEFT JOIN (
        SELECT 
          TIMESTAMP_TRUNC(ts, HOUR) as hour_ts,
          sector_id,
          COUNTIF(status = 'OUTAGE') as active_utility_outages
        FROM `{utility_table}`
        GROUP BY hour_ts, sector_id
      ) u ON g.sector_id = u.sector_id AND g.hour_ts = u.hour_ts
      LEFT JOIN (
        SELECT 
          TIMESTAMP_TRUNC(ts, HOUR) as hour_ts,
          sector_id,
          SUM(delay_minutes) as transit_delay_minutes
        FROM `{transit_table}`
        GROUP BY hour_ts, sector_id
      ) t ON g.sector_id = t.sector_id AND g.hour_ts = t.hour_ts
      LEFT JOIN (
        SELECT 
          TIMESTAMP_TRUNC(ts, HOUR) as hour_ts,
          sector_id,
          MAX(severity) as max_weather_severity
        FROM `{weather_table}`
        GROUP BY hour_ts, sector_id
      ) w ON g.sector_id = w.sector_id AND g.hour_ts = w.hour_ts
    ),
    rolling_stats AS (
      SELECT 
        hour_ts,
        sector_id,
        feedback_count,
        avg_sentiment_score,
        negative_feedback_count,
        critical_feedback_count,
        active_utility_outages,
        transit_delay_minutes,
        max_weather_severity,
        AVG(feedback_count) OVER (
          PARTITION BY sector_id 
          ORDER BY hour_ts 
          ROWS BETWEEN 24 PRECEDING AND 1 PRECEDING
        ) as rolling_mean,
        STDDEV(feedback_count) OVER (
          PARTITION BY sector_id 
          ORDER BY hour_ts 
          ROWS BETWEEN 24 PRECEDING AND 1 PRECEDING
        ) as rolling_std
      FROM hourly_metrics
    )
    SELECT 
      hour_ts as ts,
      sector_id,
      feedback_count,
      avg_sentiment_score,
      negative_feedback_count,
      critical_feedback_count,
      active_utility_outages,
      transit_delay_minutes,
      max_weather_severity,
      CASE 
        WHEN rolling_std IS NULL OR rolling_std = 0 THEN 0.0
        ELSE (feedback_count - rolling_mean) / rolling_std
      END as anomaly_score,
      CASE 
        WHEN rolling_std IS NOT NULL AND rolling_std > 0 AND (feedback_count - rolling_mean) / rolling_std > 2.0 THEN TRUE
        ELSE FALSE
      END as anomaly_flag
    FROM rolling_stats
    """
    
    print(f"Rebuilding hourly rollup table {rollup_table}...")
    job_config = bigquery.QueryJobConfig(
        destination=rollup_table,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE
    )
    
    query_job = bq_client.query(query, job_config=job_config)
    query_job.result()
    print("Successfully updated hourly rollup and anomaly z-scores.")

if __name__ == "__main__":
    run_hourly_rollup()
