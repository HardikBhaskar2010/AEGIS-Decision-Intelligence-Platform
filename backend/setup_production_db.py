import os
import json
from google.cloud import bigquery
from google.cloud.exceptions import NotFound

def setup():
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "heartbyte-7f626")
    client = bigquery.Client(project=project_id)
    dataset_id = f"{project_id}.aegis_core"

    # 1. Create Dataset
    dataset = bigquery.Dataset(dataset_id)
    dataset.location = "US"
    try:
        client.get_dataset(dataset_id)
        print(f"Dataset {dataset_id} already exists")
    except NotFound:
        dataset = client.create_dataset(dataset, timeout=30)
        print(f"Created dataset {dataset.project}.{dataset.dataset_id}")

    # 2. Define Table Schemas
    schemas = {
        "sectors": [
            bigquery.SchemaField("sector_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("lat", "FLOAT", mode="REQUIRED"),
            bigquery.SchemaField("lng", "FLOAT", mode="REQUIRED"),
            bigquery.SchemaField("population", "INTEGER", mode="REQUIRED"),
        ],
        "citizen_feedback": [
            bigquery.SchemaField("feedback_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("sector_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("ts", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("category", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("sentiment", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("raw_text", "STRING", mode="REQUIRED"),
        ],
        "weather_events": [
            bigquery.SchemaField("event_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("sector_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("ts", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("event_type", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("severity", "FLOAT", mode="REQUIRED"),
        ],
        "utility_status": [
            bigquery.SchemaField("status_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("sector_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("ts", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("utility_type", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("status", "STRING", mode="REQUIRED"),
        ],
        "transit_status": [
            bigquery.SchemaField("status_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("sector_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("ts", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("line_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("status", "STRING", mode="REQUIRED"),
        ]
    }

    # 3. Create Tables and Insert Seed Data
    base_dir = os.path.join(os.path.dirname(__file__), "..", "tests", "e2e", "mock_server", "datasets")
    
    file_mapping = {
        "sectors": "sectors.json",
        "citizen_feedback": "feedback.json",
        "weather_events": "weather.json",
        "utility_status": "utility.json",
        "transit_status": "transit.json"
    }

    for table_name, schema in schemas.items():
        table_id = f"{dataset_id}.{table_name}"
        table = bigquery.Table(table_id, schema=schema)
        try:
            client.get_table(table_id)
            print(f"Table {table_id} already exists. Deleting it to start fresh...")
            client.delete_table(table_id)
            table = client.create_table(table)
            print(f"Re-created table {table_id}")
        except NotFound:
            table = client.create_table(table)
            print(f"Created table {table_id}")

        # Load data
        file_path = os.path.join(base_dir, file_mapping[table_name])
        with open(file_path, "r") as f:
            data = json.load(f)
            
        if data:
            job_config = bigquery.LoadJobConfig(
                source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
                schema=schema
            )
            # BigQuery load_table_from_json expects a list of dictionaries which data already is.
            load_job = client.load_table_from_json(data, table, job_config=job_config)
            load_job.result()  # Waits for the job to complete.
            print(f"Inserted {len(data)} rows into {table_name}")

if __name__ == "__main__":
    setup()
