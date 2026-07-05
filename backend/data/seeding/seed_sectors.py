# backend/data/seeding/seed_sectors.py
import pandas as pd
from google.cloud import bigquery
from backend.data.config import PROJECT_ID, RAW_DATASET, CORE_DATASET, SECTORS_DATA

def seed_sectors():
    """
    Seeds sector reference data into raw and core BigQuery datasets.
    """
    client = bigquery.Client()
    df = pd.DataFrame(SECTORS_DATA)
    
    # 1. Load into RAW sectors
    raw_table_id = f"{client.project}.{RAW_DATASET}.sectors" if PROJECT_ID else f"{RAW_DATASET}.sectors"
    job_config = bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE")
    job = client.load_table_from_dataframe(df, raw_table_id, job_config=job_config)
    job.result()
    print(f"Successfully seeded raw table: {raw_table_id}")

    # 2. Load into CORE sectors
    core_table_id = f"{client.project}.{CORE_DATASET}.sectors" if PROJECT_ID else f"{CORE_DATASET}.sectors"
    df_core = df.copy()
    if "created_at" in df_core.columns:
        df_core = df_core.drop(columns=["created_at"])
    
    job_config_core = bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE")
    job_core = client.load_table_from_dataframe(df_core, core_table_id, job_config=job_config_core)
    job_core.result()
    print(f"Successfully seeded core table: {core_table_id}")

if __name__ == "__main__":
    seed_sectors()
