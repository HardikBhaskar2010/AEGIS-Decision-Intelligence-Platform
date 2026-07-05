# backend/data/schemas/db_setup.py
import os
from google.cloud import bigquery
from backend.data.config import RAW_DATASET, CORE_DATASET

def setup_bigquery():
    """
    Creates aegis_raw and aegis_core datasets, then runs the raw and core DDL files.
    """
    client = bigquery.Client()
    
    # 1. Create aegis_raw dataset if it doesn't exist
    raw_dataset_id = f"{client.project}.{RAW_DATASET}"
    raw_dataset = bigquery.Dataset(raw_dataset_id)
    raw_dataset.location = "asia-southeast1" # Default matching Singapore coordinates
    try:
        client.get_dataset(raw_dataset_id)
        print(f"Dataset {RAW_DATASET} already exists.")
    except Exception:
        client.create_dataset(raw_dataset, timeout=30)
        print(f"Created dataset {RAW_DATASET}.")
        
    # 2. Create aegis_core dataset if it doesn't exist
    core_dataset_id = f"{client.project}.{CORE_DATASET}"
    core_dataset = bigquery.Dataset(core_dataset_id)
    core_dataset.location = "asia-southeast1"
    try:
        client.get_dataset(core_dataset_id)
        print(f"Dataset {CORE_DATASET} already exists.")
    except Exception:
        client.create_dataset(core_dataset, timeout=30)
        print(f"Created dataset {CORE_DATASET}.")
        
    # 3. Read and run raw DDL SQL
    base_dir = os.path.dirname(__file__)
    raw_sql_path = os.path.join(base_dir, "raw_tables.sql")
    print(f"Executing DDL: {raw_sql_path}")
    with open(raw_sql_path, "r") as f:
        raw_sql = f.read()
        
    # Execute query
    query_job = client.query(raw_sql)
    query_job.result()
    print("Successfully ran raw tables DDL.")
    
    # 4. Read and run core DDL SQL
    core_sql_path = os.path.join(base_dir, "core_tables.sql")
    print(f"Executing DDL: {core_sql_path}")
    with open(core_sql_path, "r") as f:
        core_sql = f.read()
        
    # Execute query
    query_job_core = client.query(core_sql)
    query_job_core.result()
    print("Successfully ran core tables DDL.")

if __name__ == "__main__":
    setup_bigquery()
