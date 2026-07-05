# backend/data/pipeline/ingest.py
import os
from google.cloud import storage, bigquery
from backend.data.config import PROJECT_ID, RAW_DATASET, GCS_LANDING_BUCKET

def upload_to_gcs(local_file_path, destination_blob_name):
    """
    Uploads a local file to Google Cloud Storage.
    """
    storage_client = storage.Client()
    bucket = storage_client.bucket(GCS_LANDING_BUCKET)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_filename(local_file_path)
    print(f"Uploaded {local_file_path} to gs://{GCS_LANDING_BUCKET}/{destination_blob_name}")
    return f"gs://{GCS_LANDING_BUCKET}/{destination_blob_name}"

def load_gcs_to_bigquery_raw(gcs_uri, table_name, source_format="CSV"):
    """
    Loads a file from GCS into a BigQuery raw table.
    """
    bq_client = bigquery.Client()
    
    # Fully qualified table id
    table_id = f"{bq_client.project}.{RAW_DATASET}.{table_name}" if PROJECT_ID else f"{RAW_DATASET}.{table_name}"
    
    if source_format.upper() == "JSON":
        fmt = bigquery.SourceFormat.NEWLINE_DELIMITED_JSON
    else:
        fmt = bigquery.SourceFormat.CSV

    job_config = bigquery.LoadJobConfig(
        source_format=fmt,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        autodetect=True
    )
    
    load_job = bq_client.load_table_from_uri(gcs_uri, table_id, job_config=job_config)
    load_job.result() # Wait for job to complete
    print(f"Loaded {gcs_uri} into raw table {table_id}")
    return load_job

def run_ingestion_for_file(local_file_path, table_name):
    """
    Full ingest pipeline step: upload to GCS landing and load to BigQuery raw.
    """
    _, ext = os.path.splitext(local_file_path)
    source_format = "JSON" if ext.lower() in [".json", ".jsonl"] else "CSV"
    
    dest_blob = f"landing/{table_name}{ext}"
    gcs_uri = upload_to_gcs(local_file_path, dest_blob)
    load_gcs_to_bigquery_raw(gcs_uri, table_name, source_format=source_format)
