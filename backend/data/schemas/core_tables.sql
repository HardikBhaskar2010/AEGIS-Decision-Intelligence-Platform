-- backend/data/schemas/core_tables.sql
-- Core analytical tables for the aegis_core dataset.
-- Partitioned by ts (where applicable) and clustered by sector_id.

-- 1. SECTORS reference table
CREATE OR REPLACE TABLE aegis_core.sectors (
  sector_id STRING NOT NULL,
  name STRING NOT NULL,
  lat FLOAT64 NOT NULL,
  lng FLOAT64 NOT NULL,
  population INT64 NOT NULL
)
CLUSTER BY sector_id;

-- 2. CITIZEN_FEEDBACK table
CREATE OR REPLACE TABLE aegis_core.citizen_feedback (
  feedback_id STRING NOT NULL,
  sector_id STRING NOT NULL,
  ts TIMESTAMP NOT NULL,
  category STRING,
  sentiment STRING,
  raw_text STRING NOT NULL
)
PARTITION BY DATE(ts)
CLUSTER BY sector_id;

-- 3. WEATHER_EVENTS table
CREATE OR REPLACE TABLE aegis_core.weather_events (
  event_id STRING NOT NULL,
  sector_id STRING NOT NULL,
  ts TIMESTAMP NOT NULL,
  event_type STRING NOT NULL,
  severity FLOAT64 NOT NULL
)
PARTITION BY DATE(ts)
CLUSTER BY sector_id;

-- 4. UTILITY_STATUS table
CREATE OR REPLACE TABLE aegis_core.utility_status (
  status_id STRING NOT NULL,
  sector_id STRING NOT NULL,
  ts TIMESTAMP NOT NULL,
  utility_type STRING NOT NULL,
  status STRING NOT NULL
)
PARTITION BY DATE(ts)
CLUSTER BY sector_id;

-- 5. TRANSIT_STATUS table
CREATE OR REPLACE TABLE aegis_core.transit_status (
  status_id STRING NOT NULL,
  sector_id STRING NOT NULL,
  ts TIMESTAMP NOT NULL,
  line_id STRING NOT NULL,
  status STRING NOT NULL
)
PARTITION BY DATE(ts)
CLUSTER BY sector_id;

-- 6. SITUATION_BRIEFS table
CREATE OR REPLACE TABLE aegis_core.situation_briefs (
  brief_id STRING NOT NULL,
  sector_id STRING NOT NULL,
  ts TIMESTAMP NOT NULL,
  risk_score FLOAT64 NOT NULL,
  confidence FLOAT64 NOT NULL,
  recommendation STRING NOT NULL,
  narrative STRING NOT NULL
)
PARTITION BY DATE(ts)
CLUSTER BY sector_id;

-- 7. SUMMARY_ROLLUP table
CREATE OR REPLACE TABLE aegis_core.summary_rollup (
  ts TIMESTAMP NOT NULL,
  sector_id STRING NOT NULL,
  feedback_count INT64 NOT NULL,
  avg_sentiment_score FLOAT64 NOT NULL,
  negative_feedback_count INT64 NOT NULL,
  critical_feedback_count INT64 NOT NULL,
  active_utility_outages INT64 NOT NULL,
  transit_delay_minutes INT64 NOT NULL,
  max_weather_severity FLOAT64 NOT NULL,
  anomaly_score FLOAT64 NOT NULL,
  anomaly_flag BOOLEAN NOT NULL
)
PARTITION BY DATE(ts)
CLUSTER BY sector_id;
