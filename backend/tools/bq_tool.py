# backend/tools/bq_tool.py
import re
import json
from google.cloud import bigquery
from backend.data.config import PROJECT_ID, CORE_DATASET

def validate_query(query: str) -> None:
    """
    Validates that a SQL query is read-only and does not mutate any data.
    Raises PermissionError if a mutation is attempted.
    """
    # Remove SQL comments to prevent keyword hiding
    clean_query = re.sub(r"--.*?\n", " ", query)
    clean_query = re.sub(r"/\*.*?\*/", " ", clean_query, flags=re.DOTALL)
    
    # Check for mutating SQL keywords
    mutating_keywords = ["insert", "delete", "update", "drop", "create", "alter", "merge", "truncate"]
    words = re.findall(r"\b\w+\b", clean_query.lower())
    
    for kw in mutating_keywords:
        if kw in words:
            raise PermissionError(f"Mutating query blocked: '{kw.upper()}' operation is rejected on the read-only connector.")
            
    # Check that SELECT is the primary action
    if "select" not in words:
        raise PermissionError("Invalid query: Only SELECT queries are permitted on the read-only connector.")

def execute_sql_readonly(query: str) -> str:
    """
    Executes a read-only SQL query on the BigQuery database and returns the result as a JSON string.
    Only SELECT queries on the core or raw datasets are permitted.
    
    Args:
        query: The SQL query string to run on BigQuery.
        
    Returns:
        A JSON string containing the list of matching rows.
    """
    validate_query(query)
    
    client = bigquery.Client()
    query_job = client.query(query)
    rows = query_job.result()
    
    results = [dict(row) for row in rows]
    # Serialize datetime values to ISO format strings
    return json.dumps(results, default=str)
