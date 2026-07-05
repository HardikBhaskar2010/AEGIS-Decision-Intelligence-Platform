# tests/unit/tools/test_bq_tool.py
import pytest
from unittest.mock import MagicMock, patch
from backend.tools.bq_tool import validate_query, execute_sql_readonly

def test_validate_query_happy_path():
    """Verify that normal read-only SELECT queries pass validation."""
    validate_query("SELECT * FROM aegis_core.sectors WHERE sector_id = 'sector_7'")
    validate_query("SELECT COUNT(*), category FROM aegis_core.citizen_feedback GROUP BY category")

def test_validate_query_mutating_blocked():
    """Verify that queries containing mutating keywords raise PermissionError."""
    with pytest.raises(PermissionError) as excinfo:
        validate_query("INSERT INTO aegis_core.sectors (sector_id) VALUES ('sector_99')")
    assert "Mutating query blocked" in str(excinfo.value)
    
    with pytest.raises(PermissionError) as excinfo:
        validate_query("DELETE FROM aegis_core.sectors WHERE sector_id = 'sector_7'")
    assert "Mutating query blocked" in str(excinfo.value)
    
    with pytest.raises(PermissionError) as excinfo:
        validate_query("UPDATE aegis_core.sectors SET population = 100")
    assert "Mutating query blocked" in str(excinfo.value)
    
    with pytest.raises(PermissionError) as excinfo:
        validate_query("DROP TABLE aegis_core.sectors")
    assert "Mutating query blocked" in str(excinfo.value)

def test_validate_query_comments_handling():
    """Verify that comments containing mutating words are ignored and clean query is validated."""
    # This should be allowed because '-- delete all' is in a comment and stripped
    validate_query("-- delete all\nSELECT * FROM aegis_core.sectors")
    
    # This should be allowed because '/* insert comments */' is in a block comment
    validate_query("SELECT * FROM aegis_core.sectors /* insert comments */")

def test_validate_query_no_select():
    """Verify that a query without SELECT keyword is blocked."""
    with pytest.raises(PermissionError) as excinfo:
        validate_query("SHOW TABLES")
    assert "Only SELECT queries are permitted" in str(excinfo.value)

@patch("google.cloud.bigquery.Client")
def test_execute_sql_readonly(mock_bq_client):
    """Verify that execute_sql_readonly queries BigQuery and returns JSON string."""
    mock_instance = MagicMock()
    mock_bq_client.return_value = mock_instance
    
    mock_row = MagicMock()
    mock_row.keys.return_value = ["sector_id", "population"]
    mock_row.__getitem__.side_effect = lambda key: {"sector_id": "sector_7", "population": 85000}[key]
    mock_row.items.return_value = [("sector_id", "sector_7"), ("population", 85000)]
    
    mock_job = MagicMock()
    mock_job.result.return_value = [mock_row]
    mock_instance.query.return_value = mock_job
    
    result_str = execute_sql_readonly("SELECT sector_id, population FROM aegis_core.sectors")
    
    assert "sector_7" in result_str
    assert "85000" in result_str
    mock_instance.query.assert_called_once()
