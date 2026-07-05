# Tier 1 tests for the AEGIS Decision Intelligence Platform running on the Gemini Enterprise Agent Platform.
import pytest
import asyncio
import websockets
import json
import uuid
import sqlite3
import os

# ==============================================================================
# Feature 1: NL Query Engine (POST /api/v1/query)
# ==============================================================================

@pytest.mark.tier1
async def test_tier1_query_engine_sector_7(client, auth_headers):
    """Test Feature 1.1: POST /api/v1/query returns a dynamic brief for Sector 7 on the Gemini Enterprise Agent Platform."""
    payload = {
        "session_id": "session_f1_sector_7",
        "question": "What is the status of Sector 7?"
    }
    response = await client.post("/api/v1/query", json=payload, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "brief_id" in data
    assert data["sector_id"] == "sector_7"
    assert "risk_score" in data
    assert "confidence" in data
    assert "recommendation" in data
    assert "narrative" in data
    assert "sources" in data
    assert "active citizen complaints" in data["narrative"]

@pytest.mark.tier1
async def test_tier1_query_engine_sector_3(client, auth_headers):
    """Test Feature 1.2: POST /api/v1/query returns a brief for Sector 3 on the Gemini Enterprise Agent Platform."""
    payload = {
        "session_id": "session_f1_sector_3",
        "question": "Show me Sector 3 details."
    }
    response = await client.post("/api/v1/query", json=payload, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["sector_id"] == "sector_3"
    assert "risk_score" in data
    assert "confidence" in data

@pytest.mark.tier1
async def test_tier1_query_engine_sector_1(client, auth_headers):
    """Test Feature 1.3: POST /api/v1/query returns a brief for Sector 1 on the Gemini Enterprise Agent Platform."""
    payload = {
        "session_id": "session_f1_sector_1",
        "question": "What is the current risk status of Sector 1?"
    }
    response = await client.post("/api/v1/query", json=payload, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["sector_id"] == "sector_1"

@pytest.mark.tier1
async def test_tier1_query_engine_custom_session(client, auth_headers):
    """Test Feature 1.4: POST /api/v1/query works with a custom session ID on the Gemini Enterprise Agent Platform."""
    custom_session_id = "custom_session_999_xyz"
    payload = {
        "session_id": custom_session_id,
        "question": "What is the status of Sector 7?"
    }
    response = await client.post("/api/v1/query", json=payload, headers=auth_headers)
    assert response.status_code == 200
    
    # Retrieve history for this custom session to verify it mapped correctly
    history_resp = await client.get(f"/api/v1/history/{custom_session_id}", headers=auth_headers)
    assert history_resp.status_code == 200
    history_data = history_resp.json()
    assert len(history_data) == 1
    assert history_data[0]["session_id"] == custom_session_id

@pytest.mark.tier1
async def test_tier1_query_engine_unique_brief_id(client, auth_headers):
    """Test Feature 1.5: POST /api/v1/query generates unique brief IDs for subsequent queries on the Gemini Enterprise Agent Platform."""
    payload1 = {
        "session_id": "session_f1_unique",
        "question": "What is the status of Sector 7?"
    }
    payload2 = {
        "session_id": "session_f1_unique",
        "question": "What is the status of Sector 7?"
    }
    resp1 = await client.post("/api/v1/query", json=payload1, headers=auth_headers)
    resp2 = await client.post("/api/v1/query", json=payload2, headers=auth_headers)
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    data1 = resp1.json()
    data2 = resp2.json()
    assert data1["brief_id"] != data2["brief_id"]

@pytest.mark.tier1
async def test_tier1_query_engine_schema(client, auth_headers):
    """Test Feature 1.6: POST /api/v1/query response payload schema matches specification on the Gemini Enterprise Agent Platform."""
    payload = {
        "session_id": "session_f1_schema",
        "question": "Show status of Sector 7."
    }
    response = await client.post("/api/v1/query", json=payload, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    
    # Check fields and their types
    assert isinstance(data["brief_id"], str)
    assert isinstance(data["sector_id"], str)
    assert isinstance(data["risk_score"], (int, float))
    assert isinstance(data["confidence"], float)
    assert isinstance(data["recommendation"], str)
    assert isinstance(data["narrative"], str)
    assert isinstance(data["sources"], dict)
    assert isinstance(data["generated_at"], str)
    
    # Validate inner structures
    assert "sql" in data["sources"]
    assert "signals_used" in data["sources"]
    assert isinstance(data["sources"]["sql"], str)
    assert isinstance(data["sources"]["signals_used"], list)

# ==============================================================================
# Feature 2: WebSocket Live Event Stream (WS /ws/agent-events/{session_id})
# ==============================================================================

@pytest.mark.tier1
async def test_tier1_websocket_single_client(client, mock_server, auth_headers):
    """Test Feature 2.1: WS streams agent execution events to a single client on the Gemini Enterprise Agent Platform."""
    session_id = "session_f2_single"
    ws_uri = f"{mock_server['ws_url']}/ws/agent-events/{session_id}"
    
    async with websockets.connect(ws_uri) as websocket:
        payload = {
            "session_id": session_id,
            "question": "Show me Sector 3 details."
        }
        response = await client.post("/api/v1/query", json=payload, headers=auth_headers)
        assert response.status_code == 200
        
        received_events = []
        for _ in range(11):
            try:
                msg = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                event = json.loads(msg)
                received_events.append(event)
            except asyncio.TimeoutError:
                break
                
        assert len(received_events) == 11
        event_types = [e["type"] for e in received_events]
        assert "agent_start" in event_types
        assert "agent_result" in event_types
        assert "final_brief" in event_types

@pytest.mark.tier1
async def test_tier1_websocket_multiple_concurrent_clients(client, mock_server, auth_headers):
    """Test Feature 2.2: WS streams the exact same events to multiple concurrent clients on the Gemini Enterprise Agent Platform."""
    session_id = "session_f2_multi"
    ws_uri = f"{mock_server['ws_url']}/ws/agent-events/{session_id}"
    
    async with websockets.connect(ws_uri) as ws1, websockets.connect(ws_uri) as ws2:
        payload = {
            "session_id": session_id,
            "question": "What's up in Sector 7?"
        }
        response = await client.post("/api/v1/query", json=payload, headers=auth_headers)
        assert response.status_code == 200
        brief_id = response.json()["brief_id"]
        
        events_ws1 = []
        events_ws2 = []
        for _ in range(11):
            try:
                msg1 = await asyncio.wait_for(ws1.recv(), timeout=2.0)
                events_ws1.append(json.loads(msg1))
            except asyncio.TimeoutError:
                break
                
        for _ in range(11):
            try:
                msg2 = await asyncio.wait_for(ws2.recv(), timeout=2.0)
                events_ws2.append(json.loads(msg2))
            except asyncio.TimeoutError:
                break
                
        assert len(events_ws1) == 11
        assert len(events_ws2) == 11
        
        # Verify both received the same final brief ID
        final_event_ws1 = next(e for e in events_ws1 if e["type"] == "final_brief")
        final_event_ws2 = next(e for e in events_ws2 if e["type"] == "final_brief")
        assert final_event_ws1["detail"] == brief_id
        assert final_event_ws2["detail"] == brief_id

@pytest.mark.tier1
async def test_tier1_websocket_event_field_schema(client, mock_server, auth_headers):
    """Test Feature 2.3: WS streamed events match the expected field schema on the Gemini Enterprise Agent Platform."""
    session_id = "session_f2_schema"
    ws_uri = f"{mock_server['ws_url']}/ws/agent-events/{session_id}"
    
    async with websockets.connect(ws_uri) as websocket:
        payload = {
            "session_id": session_id,
            "question": "Status of Sector 1"
        }
        await client.post("/api/v1/query", json=payload, headers=auth_headers)
        
        msg = await asyncio.wait_for(websocket.recv(), timeout=2.0)
        event = json.loads(msg)
        
        # Assert required fields in the event
        assert "type" in event
        assert "agent" in event
        assert "ts" in event
        assert isinstance(event["type"], str)
        assert isinstance(event["agent"], str)
        assert isinstance(event["ts"], str)

@pytest.mark.tier1
async def test_tier1_websocket_chronological_ordering(client, mock_server, auth_headers):
    """Test Feature 2.4: WS streamed events are in strict chronological and logical order on the Gemini Enterprise Agent Platform."""
    session_id = "session_f2_chrono"
    ws_uri = f"{mock_server['ws_url']}/ws/agent-events/{session_id}"
    
    async with websockets.connect(ws_uri) as websocket:
        payload = {
            "session_id": session_id,
            "question": "Status of Sector 7"
        }
        await client.post("/api/v1/query", json=payload, headers=auth_headers)
        
        received_events = []
        for _ in range(11):
            msg = await asyncio.wait_for(websocket.recv(), timeout=2.0)
            received_events.append(json.loads(msg))
            
        assert len(received_events) == 11
        
        # Verify logical ordering of agent types
        assert received_events[0]["type"] == "agent_start"
        assert received_events[0]["agent"] == "Orchestrator"
        assert received_events[-1]["type"] == "final_brief"
        assert received_events[-1]["agent"] == "Orchestrator"
        
        # Verify timestamps are monotonically non-decreasing
        timestamps = [e["ts"] for e in received_events]
        for i in range(len(timestamps) - 1):
            assert timestamps[i] <= timestamps[i+1]

@pytest.mark.tier1
async def test_tier1_websocket_client_disconnection(client, mock_server, auth_headers):
    """Test Feature 2.5: WS client disconnection does not affect other clients or server on the Gemini Enterprise Agent Platform."""
    session_id = "session_f2_disconnect"
    ws_uri = f"{mock_server['ws_url']}/ws/agent-events/{session_id}"
    
    ws1 = await websockets.connect(ws_uri)
    ws2 = await websockets.connect(ws_uri)
    
    # Close ws1 client connection immediately to simulate disconnection
    await ws1.close()
    
    # Trigger query and verify ws2 still receives events successfully
    payload = {
        "session_id": session_id,
        "question": "What is going on in Sector 3?"
    }
    response = await client.post("/api/v1/query", json=payload, headers=auth_headers)
    assert response.status_code == 200
    
    received_events = []
    for _ in range(11):
        try:
            msg = await asyncio.wait_for(ws2.recv(), timeout=2.0)
            received_events.append(json.loads(msg))
        except asyncio.TimeoutError:
            break
            
    assert len(received_events) == 11
    await ws2.close()

# ==============================================================================
# Feature 3: What-If Simulation (POST /api/v1/whatif)
# ==============================================================================

@pytest.mark.tier1
async def test_tier1_whatif_simulation_positive_delta(client, auth_headers):
    """Test Feature 3.1: POST /api/v1/whatif with positive delta increases risk score on the Gemini Enterprise Agent Platform."""
    query_payload = {
        "session_id": "session_f3_pos",
        "question": "What's the status of Sector 1?"
    }
    query_resp = await client.post("/api/v1/query", json=query_payload, headers=auth_headers)
    assert query_resp.status_code == 200
    brief_id = query_resp.json()["brief_id"]
    original_risk = query_resp.json()["risk_score"]

    whatif_payload = {
        "brief_id": brief_id,
        "adjustment": {
            "rainfall_intensity_pct": 10.0
        }
    }
    response = await client.post("/api/v1/whatif", json=whatif_payload, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["brief_id"] == brief_id
    expected_risk = min(100.0, max(0.0, original_risk + (10.0 * 0.4)))
    assert data["adjusted_risk_score"] == expected_risk
    assert data["delta"] == expected_risk - original_risk
    assert "narrative_delta" in data

@pytest.mark.tier1
async def test_tier1_whatif_simulation_negative_delta(client, auth_headers):
    """Test Feature 3.2: POST /api/v1/whatif with negative delta decreases risk score on the Gemini Enterprise Agent Platform."""
    query_payload = {
        "session_id": "session_f3_neg",
        "question": "What's the status of Sector 1?"
    }
    query_resp = await client.post("/api/v1/query", json=query_payload, headers=auth_headers)
    assert query_resp.status_code == 200
    brief_id = query_resp.json()["brief_id"]
    original_risk = query_resp.json()["risk_score"]

    whatif_payload = {
        "brief_id": brief_id,
        "adjustment": {
            "rainfall_intensity_pct": -15.0
        }
    }
    response = await client.post("/api/v1/whatif", json=whatif_payload, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["brief_id"] == brief_id
    expected_risk = min(100.0, max(0.0, original_risk + (-15.0 * 0.4)))
    assert data["adjusted_risk_score"] == expected_risk
    assert data["delta"] == expected_risk - original_risk

@pytest.mark.tier1
async def test_tier1_whatif_simulation_zero_delta(client, auth_headers):
    """Test Feature 3.3: POST /api/v1/whatif with zero delta leaves risk score unchanged on the Gemini Enterprise Agent Platform."""
    query_payload = {
        "session_id": "session_f3_zero",
        "question": "What's the status of Sector 1?"
    }
    query_resp = await client.post("/api/v1/query", json=query_payload, headers=auth_headers)
    assert query_resp.status_code == 200
    brief_id = query_resp.json()["brief_id"]
    original_risk = query_resp.json()["risk_score"]

    whatif_payload = {
        "brief_id": brief_id,
        "adjustment": {
            "rainfall_intensity_pct": 0.0
        }
    }
    response = await client.post("/api/v1/whatif", json=whatif_payload, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["adjusted_risk_score"] == original_risk
    assert data["delta"] == 0.0

@pytest.mark.tier1
async def test_tier1_whatif_simulation_db_persistence(client, auth_headers):
    """Test Feature 3.4: POST /api/v1/whatif persists updated simulation state to the database on the Gemini Enterprise Agent Platform."""
    query_payload = {
        "session_id": "session_f3_persist",
        "question": "What's the status of Sector 7?"
    }
    query_resp = await client.post("/api/v1/query", json=query_payload, headers=auth_headers)
    assert query_resp.status_code == 200
    brief_id = query_resp.json()["brief_id"]

    whatif_payload = {
        "brief_id": brief_id,
        "adjustment": {
            "rainfall_intensity_pct": 20.0
        }
    }
    whatif_resp = await client.post("/api/v1/whatif", json=whatif_payload, headers=auth_headers)
    assert whatif_resp.status_code == 200
    adjusted_risk = whatif_resp.json()["adjusted_risk_score"]

    # Retrieve brief details to verify persistence
    get_brief_resp = await client.get(f"/api/v1/briefs/sector_7", headers=auth_headers)
    assert get_brief_resp.status_code == 200
    db_brief = get_brief_resp.json()
    assert db_brief["brief_id"] == brief_id
    assert db_brief["risk_score"] == adjusted_risk
    assert "[What-If Adjusted:" in db_brief["narrative"]

@pytest.mark.tier1
async def test_tier1_whatif_simulation_extreme_deltas(client, auth_headers):
    """Test Feature 3.5: POST /api/v1/whatif caps adjusted risk scores at [0.0, 100.0] boundaries on the Gemini Enterprise Agent Platform."""
    query_payload = {
        "session_id": "session_f3_extreme",
        "question": "What's the status of Sector 1?"
    }
    query_resp = await client.post("/api/v1/query", json=query_payload, headers=auth_headers)
    assert query_resp.status_code == 200
    brief_id = query_resp.json()["brief_id"]

    # Extreme positive delta (+300.0%)
    payload_pos = {"brief_id": brief_id, "adjustment": {"rainfall_intensity_pct": 300.0}}
    resp_pos = await client.post("/api/v1/whatif", json=payload_pos, headers=auth_headers)
    assert resp_pos.status_code == 200
    assert resp_pos.json()["adjusted_risk_score"] == 100.0

    # Extreme negative delta (-300.0%)
    payload_neg = {"brief_id": brief_id, "adjustment": {"rainfall_intensity_pct": -300.0}}
    resp_neg = await client.post("/api/v1/whatif", json=payload_neg, headers=auth_headers)
    assert resp_neg.status_code == 200
    assert resp_neg.json()["adjusted_risk_score"] == 0.0

# ==============================================================================
# Feature 4: Sector Status & Map API (GET /api/v1/sectors & GET /api/v1/briefs/{sector_id})
# ==============================================================================

@pytest.mark.tier1
async def test_tier1_sectors_list_retrieve(client, auth_headers):
    """Test Feature 4.1: GET /api/v1/sectors retrieves all active sectors successfully on the Gemini Enterprise Agent Platform."""
    response = await client.get("/api/v1/sectors", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    sectors = {s["sector_id"] for s in data}
    assert "sector_7" in sectors
    assert "sector_3" in sectors

@pytest.mark.tier1
async def test_tier1_sectors_coordinate_schema(client, auth_headers):
    """Test Feature 4.2: GET /api/v1/sectors returns geographic coordinates conforming to schema on the Gemini Enterprise Agent Platform."""
    # The coordinate data and associated location records represent synthetic citizen and location parameters.
    response = await client.get("/api/v1/sectors", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    for sector in data:
        assert "lat" in sector
        assert "lng" in sector
        assert isinstance(sector["lat"], float)
        assert isinstance(sector["lng"], float)
        assert -90.0 <= sector["lat"] <= 90.0
        assert -180.0 <= sector["lng"] <= 180.0

@pytest.mark.tier1
async def test_tier1_sectors_get_brief_sector_7(client, auth_headers):
    """Test Feature 4.3: GET /api/v1/briefs/{sector_id} retrieves brief for Sector 7 on the Gemini Enterprise Agent Platform."""
    query_payload = {
        "session_id": "session_f4_sector_7",
        "question": "What is the status of Sector 7?"
    }
    query_resp = await client.post("/api/v1/query", json=query_payload, headers=auth_headers)
    assert query_resp.status_code == 200
    brief_id = query_resp.json()["brief_id"]

    response = await client.get("/api/v1/briefs/sector_7", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["sector_id"] == "sector_7"
    assert data["brief_id"] == brief_id
    assert "risk_score" in data
    assert "narrative" in data

@pytest.mark.tier1
async def test_tier1_sectors_get_brief_sector_3(client, auth_headers):
    """Test Feature 4.4: GET /api/v1/briefs/{sector_id} retrieves brief for Sector 3 on the Gemini Enterprise Agent Platform."""
    query_payload = {
        "session_id": "session_f4_sector_3",
        "question": "Show me Sector 3 details."
    }
    query_resp = await client.post("/api/v1/query", json=query_payload, headers=auth_headers)
    assert query_resp.status_code == 200
    brief_id = query_resp.json()["brief_id"]

    response = await client.get("/api/v1/briefs/sector_3", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["sector_id"] == "sector_3"
    assert data["brief_id"] == brief_id

@pytest.mark.tier1
async def test_tier1_sectors_population_check(client, auth_headers):
    """Test Feature 4.5: GET /api/v1/sectors population data satisfies synthetic population check constraints on the Gemini Enterprise Agent Platform."""
    # The population counts represent synthetic citizen feedback data scaling indicators.
    response = await client.get("/api/v1/sectors", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    for sector in data:
        assert "population" in sector
        assert isinstance(sector["population"], int)
        assert sector["population"] > 0

@pytest.mark.tier1
async def test_tier1_citizen_feedback_is_synthetic():
    """Test Feature 4.6: Verify that all citizen feedback data in the database is explicitly labeled with the [SYNTHETIC] prefix on the Gemini Enterprise Agent Platform."""
    # Ensure all citizen feedback data used or asserted in tests is explicitly labeled as synthetic matching the [SYNTHETIC] prefix.
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "mock_server", "mock_db.sqlite")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT raw_text FROM CITIZEN_FEEDBACK")
    rows = cursor.fetchall()
    conn.close()
    
    assert len(rows) > 0
    for row in rows:
        feedback_text = row[0]
        assert feedback_text.startswith("[SYNTHETIC]")

# ==============================================================================
# Feature 5: Session History (GET /api/v1/history/{session_id})
# ==============================================================================

@pytest.mark.tier1
async def test_tier1_history_retrieval(client, auth_headers):
    """Test Feature 5.1: GET /api/v1/history/{session_id} retrieves list of historical briefs on the Gemini Enterprise Agent Platform."""
    session_id = "session_f5_retrieval"
    query_payload = {
        "session_id": session_id,
        "question": "Is Sector 7 safe?"
    }
    query_resp = await client.post("/api/v1/query", json=query_payload, headers=auth_headers)
    assert query_resp.status_code == 200
    brief_id = query_resp.json()["brief_id"]

    response = await client.get(f"/api/v1/history/{session_id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert data[0]["brief_id"] == brief_id

@pytest.mark.tier1
async def test_tier1_history_reverse_chronological_ordering(client, auth_headers):
    """Test Feature 5.2: GET /api/v1/history/{session_id} returns briefs in reverse chronological order on the Gemini Enterprise Agent Platform."""
    session_id = "session_f5_chrono"
    
    payloads = [
        {"session_id": session_id, "question": "What's the status of Sector 1?"},
        {"session_id": session_id, "question": "What's the status of Sector 3?"},
        {"session_id": session_id, "question": "What's the status of Sector 7?"}
    ]
    brief_ids = []
    for p in payloads:
        resp = await client.post("/api/v1/query", json=p, headers=auth_headers)
        assert resp.status_code == 200
        brief_ids.append(resp.json()["brief_id"])
        await asyncio.sleep(0.01)
        
    response = await client.get(f"/api/v1/history/{session_id}", headers=auth_headers)
    assert response.status_code == 200
    history = response.json()
    assert len(history) >= 3
    
    assert history[0]["brief_id"] == brief_ids[2]
    assert history[1]["brief_id"] == brief_ids[1]
    assert history[2]["brief_id"] == brief_ids[0]
    
    timestamps = [item["ts"] for item in history]
    for i in range(len(timestamps) - 1):
        assert timestamps[i] >= timestamps[i+1]

@pytest.mark.tier1
async def test_tier1_history_empty_check(client, auth_headers):
    """Test Feature 5.3: GET /api/v1/history/{session_id} returns an empty list for unused session IDs on the Gemini Enterprise Agent Platform."""
    unused_session_id = "session_unused_" + str(uuid.uuid4().hex[:8])
    response = await client.get(f"/api/v1/history/{unused_session_id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0

@pytest.mark.tier1
async def test_tier1_history_size_check(client, auth_headers):
    """Test Feature 5.4: GET /api/v1/history/{session_id} history list size matches exact count of generated queries on the Gemini Enterprise Agent Platform."""
    session_id = "session_f5_size"
    
    for _ in range(4):
        resp = await client.post("/api/v1/query", json={"session_id": session_id, "question": "Sector 7 info"}, headers=auth_headers)
        assert resp.status_code == 200
        
    response = await client.get(f"/api/v1/history/{session_id}", headers=auth_headers)
    assert response.status_code == 200
    history = response.json()
    assert len(history) == 4

@pytest.mark.tier1
async def test_tier1_history_payload_structure_comparison(client, auth_headers):
    """Test Feature 5.5: GET /api/v1/history/{session_id} returns briefs matching schema structure of generated briefs on the Gemini Enterprise Agent Platform."""
    # The historical responses verify synthetic citizen complains counting mechanisms.
    session_id = "session_f5_payload"
    query_payload = {
        "session_id": session_id,
        "question": "What is the status of Sector 7?"
    }
    query_resp = await client.post("/api/v1/query", json=query_payload, headers=auth_headers)
    assert query_resp.status_code == 200
    original_brief = query_resp.json()

    response = await client.get(f"/api/v1/history/{session_id}", headers=auth_headers)
    assert response.status_code == 200
    history = response.json()
    assert len(history) > 0
    historical_brief = history[0]

    assert historical_brief["brief_id"] == original_brief["brief_id"]
    assert historical_brief["sector_id"] == original_brief["sector_id"]
    assert historical_brief["risk_score"] == original_brief["risk_score"]
    assert historical_brief["confidence"] == original_brief["confidence"]
    assert historical_brief["recommendation"] == original_brief["recommendation"]
    assert historical_brief["narrative"] == original_brief["narrative"]
    assert historical_brief["session_id"] == session_id
    assert "rainfall_intensity_pct" in historical_brief

