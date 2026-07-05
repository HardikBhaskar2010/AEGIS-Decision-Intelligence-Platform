# Tier 2 tests for the AEGIS Decision Intelligence Platform running on the Gemini Enterprise Agent Platform.
import pytest
import asyncio
import websockets
import json
import uuid
import sqlite3
import os
from unittest.mock import patch

# ==============================================================================
# Feature 1: NL Query Engine (POST /api/v1/query)
# ==============================================================================

@pytest.mark.tier2
async def test_tier2_non_existent_sector(client, auth_headers):
    """Test Feature 1: Querying a non-existent sector via query API on the Gemini Enterprise Agent Platform returns 404."""
    payload = {
        "session_id": "test_session_t2_nonexistent",
        "question": "What's happening in Sector 99?"
    }
    response = await client.post("/api/v1/query", json=payload, headers=auth_headers)
    assert response.status_code == 404
    assert "Sector not found" in response.text


@pytest.mark.tier2
async def test_tier2_query_empty_body(client, auth_headers):
    """Test Feature 1: Query with empty request body returns 422 on the Gemini Enterprise Agent Platform."""
    response = await client.post("/api/v1/query", json={}, headers=auth_headers)
    assert response.status_code == 422


@pytest.mark.tier2
async def test_tier2_query_whitespace_only(client, auth_headers):
    """Test Feature 1: Query with whitespace-only question defaults to Sector 7 on the Gemini Enterprise Agent Platform."""
    payload = {
        "session_id": "session_t2_whitespace",
        "question": "   \n\t   "
    }
    response = await client.post("/api/v1/query", json=payload, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["sector_id"] == "sector_7"


@pytest.mark.tier2
async def test_tier2_query_extremely_long_query(client, auth_headers):
    """Test Feature 1: Query with extremely long question is handled safely on the Gemini Enterprise Agent Platform."""
    long_question = "What is the status of Sector 3? " + ("A" * 5000)
    payload = {
        "session_id": "session_t2_long_query",
        "question": long_question
    }
    response = await client.post("/api/v1/query", json=payload, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["sector_id"] == "sector_3"


@pytest.mark.tier2
async def test_tier2_query_sql_injection(client, auth_headers):
    """Test Feature 1: Query and session ID containing SQL injection keywords are handled safely without DB corruption on the Gemini Enterprise Agent Platform."""
    sqli_session = "'; DROP TABLE SITUATION_BRIEFS; --"
    sqli_question = "Sector 3' UNION SELECT * FROM SECTORS; --"
    payload = {
        "session_id": sqli_session,
        "question": sqli_question
    }
    response = await client.post("/api/v1/query", json=payload, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["sector_id"] == "sector_3"
    
    # Verify the session ID is preserved literally in session history safely
    history_resp = await client.get(f"/api/v1/history/{sqli_session}", headers=auth_headers)
    assert history_resp.status_code == 200
    history_data = history_resp.json()
    assert len(history_data) > 0
    assert history_data[0]["session_id"] == sqli_session


@pytest.mark.tier2
async def test_tier2_query_backend_failure_simulation(client, auth_headers):
    """Test Feature 1: Backend database connection failure causes 500 internal server error on the Gemini Enterprise Agent Platform."""
    def raise_operational_error():
        raise sqlite3.OperationalError("Mock database connection failure")
        
    with patch("tests.e2e.mock_server.app.get_db_connection", side_effect=raise_operational_error):
        payload = {
            "session_id": "session_t2_failure",
            "question": "What is the status of Sector 7?"
        }
        response = await client.post("/api/v1/query", json=payload, headers=auth_headers)
        assert response.status_code == 500


# ==============================================================================
# Feature 2: WebSocket Live Event Stream (WS /ws/agent-events/{session_id})
# ==============================================================================

@pytest.mark.tier2
async def test_tier2_websocket_malformed_session_id(mock_server):
    """Test Feature 2: Connecting with a malformed/special-character session ID is handled gracefully on the Gemini Enterprise Agent Platform."""
    import urllib.parse
    malformed_session = "ws_session_!@#$ %^&*()_+ 🚀"
    encoded_session = urllib.parse.quote(malformed_session)
    ws_uri = f"{mock_server['ws_url']}/ws/agent-events/{encoded_session}"
    
    async with websockets.connect(ws_uri) as websocket:
        assert websocket is not None


@pytest.mark.tier2
async def test_tier2_websocket_rapid_connection_churn(mock_server):
    """Test Feature 2: Rapid connect and disconnect churn of WebSocket clients is handled safely on the Gemini Enterprise Agent Platform."""
    session_id = "ws_session_churn_t2"
    ws_uri = f"{mock_server['ws_url']}/ws/agent-events/{session_id}"
    
    for _ in range(5):
        async with websockets.connect(ws_uri) as websocket:
            assert websocket is not None



@pytest.mark.tier2
async def test_tier2_websocket_send_data_read_only(client, mock_server, auth_headers):
    """Test Feature 2: Sending data to the read-only WebSocket event stream does not crash the server on the Gemini Enterprise Agent Platform."""
    session_id = "ws_session_readonly_t2"
    ws_uri = f"{mock_server['ws_url']}/ws/agent-events/{session_id}"
    
    async with websockets.connect(ws_uri) as websocket:
        await websocket.send("Hello server, I am sending read-only input.")
        
        payload = {
            "session_id": session_id,
            "question": "What is the status of Sector 7?"
        }
        response = await client.post("/api/v1/query", json=payload, headers=auth_headers)
        assert response.status_code == 200
        
        msg = await asyncio.wait_for(websocket.recv(), timeout=2.0)
        event = json.loads(msg)
        assert "type" in event


@pytest.mark.tier2
async def test_tier2_websocket_stale_event_broadcast(client, mock_server, auth_headers):
    """Test Feature 2: Stale disconnected client removal during multi-agent event broadcast is handled gracefully on the Gemini Enterprise Agent Platform."""
    session_id = "ws_session_stale_t2"
    ws_uri = f"{mock_server['ws_url']}/ws/agent-events/{session_id}"
    
    ws1 = await websockets.connect(ws_uri)
    ws2 = await websockets.connect(ws_uri)
    
    payload = {
        "session_id": session_id,
        "question": "What is the status of Sector 7?"
    }
    response = await client.post("/api/v1/query", json=payload, headers=auth_headers)
    assert response.status_code == 200
    
    # Read a message on ws1, then disconnect ws1 abruptly
    msg_1a = await asyncio.wait_for(ws1.recv(), timeout=2.0)
    assert msg_1a is not None
    await ws1.close()
    
    # Verify ws2 (active client) still gets all 11 events
    received_ws2 = []
    for _ in range(11):
        try:
            msg = await asyncio.wait_for(ws2.recv(), timeout=2.0)
            received_ws2.append(json.loads(msg))
        except asyncio.TimeoutError:
            break
            
    assert len(received_ws2) == 11
    await ws2.close()


@pytest.mark.tier2
async def test_tier2_websocket_multiple_concurrent_tracking(client, mock_server, auth_headers):
    """Test Feature 2: Multiple concurrent WebSocket clients tracking the same session ID receive identical event streams on the Gemini Enterprise Agent Platform."""
    session_id = "ws_session_concurrent_t2"
    ws_uri = f"{mock_server['ws_url']}/ws/agent-events/{session_id}"
    
    clients = [await websockets.connect(ws_uri) for _ in range(3)]
    
    payload = {
        "session_id": session_id,
        "question": "What is the status of Sector 7?"
    }
    response = await client.post("/api/v1/query", json=payload, headers=auth_headers)
    assert response.status_code == 200
    brief_id = response.json()["brief_id"]
    
    # Verify all three clients receive the same final brief event
    for ws in clients:
        events = []
        for _ in range(11):
            msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
            events.append(json.loads(msg))
        
        final_event = next(e for e in events if e["type"] == "final_brief")
        assert final_event["detail"] == brief_id
        await ws.close()


# ==============================================================================
# Feature 3: What-If Simulation (POST /api/v1/whatif)
# ==============================================================================

@pytest.mark.tier2
async def test_tier2_invalid_brief_whatif(client, auth_headers):
    """Test Feature 3: Running What-If on a non-existent brief ID returns 404 on the Gemini Enterprise Agent Platform."""
    payload = {
        "brief_id": "brief_nonexistent_12345",
        "adjustment": {
            "rainfall_intensity_pct": 10.0
        }
    }
    response = await client.post("/api/v1/whatif", json=payload, headers=auth_headers)
    assert response.status_code == 404
    assert "Brief not found" in response.text


@pytest.mark.tier2
async def test_tier2_whatif_negative_adjustments(client, auth_headers):
    """Test Feature 3: What-If simulation with large negative adjustments caps risk score at 0.0 on the Gemini Enterprise Agent Platform."""
    query_payload = {
        "session_id": "session_t2_whatif_neg",
        "question": "What is the status of Sector 7?"
    }
    query_resp = await client.post("/api/v1/query", json=query_payload, headers=auth_headers)
    assert query_resp.status_code == 200
    brief_id = query_resp.json()["brief_id"]
    
    whatif_payload = {
        "brief_id": brief_id,
        "adjustment": {
            "rainfall_intensity_pct": -1000.0
        }
    }
    response = await client.post("/api/v1/whatif", json=whatif_payload, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["adjusted_risk_score"] == 0.0


@pytest.mark.tier2
async def test_tier2_whatif_extreme_positive_adjustments(client, auth_headers):
    """Test Feature 3: What-If simulation with large positive adjustments caps risk score at 100.0 on the Gemini Enterprise Agent Platform."""
    query_payload = {
        "session_id": "session_t2_whatif_pos",
        "question": "What is the status of Sector 7?"
    }
    query_resp = await client.post("/api/v1/query", json=query_payload, headers=auth_headers)
    assert query_resp.status_code == 200
    brief_id = query_resp.json()["brief_id"]
    
    whatif_payload = {
        "brief_id": brief_id,
        "adjustment": {
            "rainfall_intensity_pct": 1000.0
        }
    }
    response = await client.post("/api/v1/whatif", json=whatif_payload, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["adjusted_risk_score"] == 100.0


@pytest.mark.tier2
async def test_tier2_whatif_missing_fields(client, auth_headers):
    """Test Feature 3: What-If simulation request with missing payload fields returns 422 on the Gemini Enterprise Agent Platform."""
    response1 = await client.post("/api/v1/whatif", json={"brief_id": "some_brief"}, headers=auth_headers)
    assert response1.status_code == 422
    
    response2 = await client.post("/api/v1/whatif", json={"brief_id": "some_brief", "adjustment": {}}, headers=auth_headers)
    assert response2.status_code == 422


@pytest.mark.tier2
async def test_tier2_whatif_invalid_data_types(client, auth_headers):
    """Test Feature 3: What-If simulation request with invalid data types returns 422 on the Gemini Enterprise Agent Platform."""
    whatif_payload = {
        "brief_id": "some_brief",
        "adjustment": {
            "rainfall_intensity_pct": "heavy"
        }
    }
    response = await client.post("/api/v1/whatif", json=whatif_payload, headers=auth_headers)
    assert response.status_code == 422


# ==============================================================================
# Feature 4: Sector Status & Map API (GET /api/v1/sectors & GET /api/v1/briefs/{sector_id})
# ==============================================================================

@pytest.mark.tier2
async def test_tier2_unauthorized_access(client):
    """Test Feature 4: Check 401 is returned when Authorization header is missing on the Gemini Enterprise Agent Platform."""
    response = await client.get("/api/v1/sectors")
    assert response.status_code == 401
    assert "Authorization header missing" in response.text


@pytest.mark.tier2
async def test_tier2_invalid_token(client):
    """Test Feature 4: Check 401 is returned when an invalid token is provided on the Gemini Enterprise Agent Platform."""
    response = await client.get("/api/v1/sectors", headers={"Authorization": "Bearer invalid-token"})
    assert response.status_code == 401
    assert "Invalid token" in response.text


@pytest.mark.tier2
async def test_tier2_brief_non_existent_sector(client, auth_headers):
    """Test Feature 4: Requesting a brief for a non-existent sector returns 404 on the Gemini Enterprise Agent Platform."""
    response = await client.get("/api/v1/briefs/sector_99", headers=auth_headers)
    assert response.status_code == 404
    assert "Brief for sector not found" in response.text


@pytest.mark.tier2
async def test_tier2_brief_malformed_sector_id(client, auth_headers):
    """Test Feature 4: Requesting a brief with a malformed sector ID handles request safely and returns 404 on the Gemini Enterprise Agent Platform."""
    malformed_id = "sector_'; SELECT * FROM SECTORS; --"
    response = await client.get(f"/api/v1/briefs/{malformed_id}", headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.tier2
async def test_tier2_sectors_empty_database(client, auth_headers):
    """Test Feature 4: When SECTORS table is empty, GET /api/v1/sectors returns an empty list on the Gemini Enterprise Agent Platform."""
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "mock_server", "mock_db.sqlite")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM SECTORS")
    conn.commit()
    conn.close()
    
    try:
        response = await client.get("/api/v1/sectors", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []
    finally:
        # Reset database state
        reset_response = await client.post("/api/v1/test/reset", headers=auth_headers)
        assert reset_response.status_code == 200


@pytest.mark.tier2
async def test_tier2_briefs_unauthorized_endpoints_check(client):
    """Test Feature 4: Check 401 is returned when fetching briefs without valid authorization on the Gemini Enterprise Agent Platform."""
    response1 = await client.get("/api/v1/briefs/sector_7")
    assert response1.status_code == 401
    
    response2 = await client.get("/api/v1/briefs/sector_7", headers={"Authorization": "Bearer invalid-token"})
    assert response2.status_code == 401


@pytest.mark.tier2
async def test_tier2_citizen_feedback_synthetic_prefix_validation(client, auth_headers):
    """Test Feature 4: Verify citizen feedback retrieved via database has the synthetic label [SYNTHETIC] on the Gemini Enterprise Agent Platform."""
    # Ensure database is in clean state
    reset_response = await client.post("/api/v1/test/reset", headers=auth_headers)
    assert reset_response.status_code == 200
    
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "mock_server", "mock_db.sqlite")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT raw_text FROM CITIZEN_FEEDBACK WHERE sector_id = 'sector_7'")
    rows = cursor.fetchall()
    conn.close()
    
    assert len(rows) > 0
    for row in rows:
        feedback_text = row[0]
        # Label all citizen feedback data used or asserted in tests as synthetic matching the [SYNTHETIC] prefix
        assert feedback_text.startswith("[SYNTHETIC]")


# ==============================================================================
# Feature 5: Session History (GET /api/v1/history/{session_id})
# ==============================================================================

@pytest.mark.tier2
async def test_tier2_empty_session_history(client, auth_headers):
    """Test Feature 5: Retrieving history for a fresh session returns an empty list on the Gemini Enterprise Agent Platform."""
    response = await client.get("/api/v1/history/new_empty_session_id_xyz", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0


@pytest.mark.tier2
async def test_tier2_history_extremely_long_session_id(client, auth_headers):
    """Test Feature 5: Retrieving history with an extremely long session ID returns empty list on the Gemini Enterprise Agent Platform."""
    long_session_id = "session_" + ("x" * 5000)
    response = await client.get(f"/api/v1/history/{long_session_id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0


@pytest.mark.tier2
async def test_tier2_history_malformed_session_id(client, auth_headers):
    """Test Feature 5: Retrieving history with a malformed session ID containing special characters/SQL injection returns empty list safely on the Gemini Enterprise Agent Platform."""
    malformed_session_id = "session_'; DROP TABLE SITUATION_BRIEFS; --"
    response = await client.get(f"/api/v1/history/{malformed_session_id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0


@pytest.mark.tier2
async def test_tier2_history_cleanup_after_reset(client, auth_headers):
    """Test Feature 5: Session history is cleared after database reset on the Gemini Enterprise Agent Platform."""
    session_id = "session_t2_cleanup_reset"
    
    query_payload = {
        "session_id": session_id,
        "question": "What is the status of Sector 7?"
    }
    query_resp = await client.post("/api/v1/query", json=query_payload, headers=auth_headers)
    assert query_resp.status_code == 200
    
    history_resp1 = await client.get(f"/api/v1/history/{session_id}", headers=auth_headers)
    assert len(history_resp1.json()) == 1
    
    reset_resp = await client.post("/api/v1/test/reset", headers=auth_headers)
    assert reset_resp.status_code == 200
    
    history_resp2 = await client.get(f"/api/v1/history/{session_id}", headers=auth_headers)
    assert len(history_resp2.json()) == 0


@pytest.mark.tier2
async def test_tier2_history_concurrent_write_retrieval(client, auth_headers):
    """Test Feature 5: Concurrent writes (queries) and reads (history retrieval) do not cause deadlocks on the Gemini Enterprise Agent Platform."""
    session_id = "session_t2_concurrent"
    
    async def make_query():
        payload = {
            "session_id": session_id,
            "question": "Status of Sector 7"
        }
        resp = await client.post("/api/v1/query", json=payload, headers=auth_headers)
        return resp.status_code
        
    async def get_history():
        resp = await client.get(f"/api/v1/history/{session_id}", headers=auth_headers)
        return resp.status_code
        
    tasks = []
    for _ in range(5):
        tasks.append(make_query())
        tasks.append(get_history())
        
    results = await asyncio.gather(*tasks)
    for status in results:
        assert status == 200
        
    history_resp = await client.get(f"/api/v1/history/{session_id}", headers=auth_headers)
    assert history_resp.status_code == 200
    assert len(history_resp.json()) == 5

