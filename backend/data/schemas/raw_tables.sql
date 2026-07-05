-- backend/data/schemas/raw_tables.sql
-- Raw landing tables for the aegis_raw dataset.
-- No partition/clustering, permissive schemas to ensure landing never fails.

CREATE OR REPLACE TABLE aegis_raw.sectors (
  sector_id STRING,
  name STRING,
  lat FLOAT64,
  lng FLOAT64,
  population INT64
);

CREATE OR REPLACE TABLE aegis_raw.citizen_feedback (
  feedback_id STRING,
  sector_id STRING,
  ts TIMESTAMP,
  raw_text STRING,
  is_synthetic BOOLEAN
);

CREATE OR REPLACE TABLE aegis_raw.weather_events (
  event_id STRING,
  sector_id STRING,
  ts TIMESTAMP,
  event_type STRING,
  severity FLOAT64,
  precipitation_mm FLOAT64,
  temperature_c FLOAT64,
  wind_speed_kmh FLOAT64,
  is_synthetic BOOLEAN,
  source STRING
);

CREATE OR REPLACE TABLE aegis_raw.utility_status (
  status_id STRING,
  sector_id STRING,
  ts TIMESTAMP,
  utility_type STRING,
  status STRING,
  customers_affected INT64,
  raw_details STRING,
  is_synthetic BOOLEAN
);

CREATE OR REPLACE TABLE aegis_raw.transit_status (
  status_id STRING,
  sector_id STRING,
  ts TIMESTAMP,
  line_id STRING,
  status STRING,
  delay_minutes INT64,
  raw_details STRING,
  is_synthetic BOOLEAN
);
