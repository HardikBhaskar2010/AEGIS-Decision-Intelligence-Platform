# Tier 3 tests for the AEGIS Decision Intelligence Platform running on the Gemini Enterprise Agent Platform.
import pytest
import asyncio
import websockets
import json

@pytest.mark.tier3
async def test_tier3_rest_websocket_sync(client, mock_server, auth_headers):
    """Test 1: REST-WebSocket Sync - verifying that a query triggers events on the WebSocket on the Gemini Enterprise Agent Platform."""
    session_id = "session_sync_test"
    ws_uri = f"{mock_server['ws_url']}/ws/agent-events/{session_id}"
    
    async with websockets.connect(ws_uri) as websocket:
        # Trigger query via HTTP
        payload = {
            "session_id": session_id,
            "question": "Status of Sector 7?"
        }
        resp = await client.post("/api/v1/query", json=payload, headers=auth_headers)
        assert resp.status_code == 200
        brief_id = resp.json()["brief_id"]
        
        # Read the WS events
        events = []
        for _ in range(11):
            try:
                msg = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                events.append(json.loads(msg))
            except asyncio.TimeoutError:
                break
                
        assert len(events) == 11
        assert events[-1]["type"] == "final_brief"
        assert events[-1]["detail"] == brief_id

@pytest.mark.tier3
async def test_tier3_history_mutation_persistence(client, auth_headers):
    """Test 2: History Mutation Persistence - queries populate history on the Gemini Enterprise Agent Platform."""
    session_id = "session_persistence_test"
    
    # Query 1
    resp1 = await client.post("/api/v1/query", json={"session_id": session_id, "question": "Sector 7"}, headers=auth_headers)
    assert resp1.status_code == 200
    brief_id_1 = resp1.json()["brief_id"]
    
    # Query 2
    resp2 = await client.post("/api/v1/query", json={"session_id": session_id, "question": "Sector 3"}, headers=auth_headers)
    assert resp2.status_code == 200
    brief_id_2 = resp2.json()["brief_id"]
    
    # Fetch history
    history_resp = await client.get(f"/api/v1/history/{session_id}", headers=auth_headers)
    assert history_resp.status_code == 200
    history = history_resp.json()
    assert len(history) == 2
    assert history[0]["brief_id"] == brief_id_2
    assert history[1]["brief_id"] == brief_id_1

@pytest.mark.tier3
async def test_tier3_whatif_mutation_linkage(client, auth_headers):
    """Test 3: What-If Mutation Linkage - What-If adjustments update the active brief on the Gemini Enterprise Agent Platform."""
    # Run query to get a brief
    query_resp = await client.post("/api/v1/query", json={"session_id": "session_whatif_link", "question": "Sector 1"}, headers=auth_headers)
    assert query_resp.status_code == 200
    brief_data = query_resp.json()
    brief_id = brief_data["brief_id"]
    sector_id = brief_data["sector_id"]
    
    # Check sector brief before adjustment
    brief_resp_before = await client.get(f"/api/v1/briefs/{sector_id}", headers=auth_headers)
    assert brief_resp_before.status_code == 200
    assert brief_resp_before.json()["brief_id"] == brief_id
    
    # Run What-If adjustment
    whatif_resp = await client.post("/api/v1/whatif", json={"brief_id": brief_id, "adjustment": {"rainfall_intensity_pct": 50.0}}, headers=auth_headers)
    assert whatif_resp.status_code == 200
    adjusted_risk = whatif_resp.json()["adjusted_risk_score"]
    
    # Check sector brief after adjustment (should reflect updated risk score)
    brief_resp_after = await client.get(f"/api/v1/briefs/{sector_id}", headers=auth_headers)
    assert brief_resp_after.status_code == 200
    assert brief_resp_after.json()["risk_score"] == adjusted_risk
    assert "[What-If Adjusted:" in brief_resp_after.json()["narrative"]

@pytest.mark.tier3
async def test_tier3_session_isolation(client, mock_server, auth_headers):
    """Test 4: Session Isolation - events from session A do not leak to session B on the Gemini Enterprise Agent Platform."""
    session_a = "session_a"
    session_b = "session_b"
    
    ws_uri_a = f"{mock_server['ws_url']}/ws/agent-events/{session_a}"
    ws_uri_b = f"{mock_server['ws_url']}/ws/agent-events/{session_b}"
    
    async with websockets.connect(ws_uri_a) as ws_a, websockets.connect(ws_uri_b) as ws_b:
        # Trigger query for session A
        await client.post("/api/v1/query", json={"session_id": session_a, "question": "Sector 7"}, headers=auth_headers)
        
        # We expect ws_a to receive events, and ws_b to receive nothing.
        events_a = []
        for _ in range(11):
            try:
                msg = await asyncio.wait_for(ws_a.recv(), timeout=0.5)
                events_a.append(json.loads(msg))
            except asyncio.TimeoutError:
                break
                
        # Check ws_b
        events_b = []
        try:
            msg = await asyncio.wait_for(ws_b.recv(), timeout=0.5)
            events_b.append(json.loads(msg))
        except asyncio.TimeoutError:
            pass
            
        assert len(events_a) == 11
        assert len(events_b) == 0

@pytest.mark.tier3
async def test_tier3_database_propagation(client, auth_headers):
    """Test 5: Database Propagation - new weather event injection updates query risk score on the Gemini Enterprise Agent Platform."""
    # Reset DB to default state
    await client.post("/api/v1/test/reset", headers=auth_headers)
    
    # Query Sector 3 initial risk
    resp_init = await client.post("/api/v1/query", json={"session_id": "session_prop", "question": "Sector 3"}, headers=auth_headers)
    assert resp_init.status_code == 200
    risk_init = resp_init.json()["risk_score"]
    
    # Inject a severe storm in Sector 3 (severity 0.95)
    inject_payload = {
        "event_id": "weather_injected_1",
        "sector_id": "sector_3",
        "ts": "2026-07-05T13:00:00Z",
        "event_type": "STORM",
        "severity": 0.95
    }
    inj_resp = await client.post("/api/v1/test/inject/weather", json=inject_payload, headers=auth_headers)
    assert inj_resp.status_code == 200
    
    # Query Sector 3 again
    resp_after = await client.post("/api/v1/query", json={"session_id": "session_prop", "question": "Sector 3"}, headers=auth_headers)
    assert resp_after.status_code == 200
    risk_after = resp_after.json()["risk_score"]
    
    # The risk score should have increased significantly due to the storm
    assert risk_after > risk_init
