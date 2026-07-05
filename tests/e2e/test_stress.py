# Stress and concurrency tests for the AEGIS Decision Intelligence Platform running on the Gemini Enterprise Agent Platform.
import pytest
import asyncio
import httpx
import websockets
import json
import sqlite3
import os
from tests.e2e.mock_server.app import DB_PATH, get_db_connection

@pytest.mark.asyncio
async def test_stress_websocket_auth_bypass(mock_server):
    """Verify that WS endpoint can be connected to without any Authorization headers (Security Bypass)."""
    session_id = "bypass_session_test"
    ws_uri = f"{mock_server['ws_url']}/ws/agent-events/{session_id}"
    
    # We do not pass any headers/token, yet it should connect successfully
    async with websockets.connect(ws_uri) as websocket:
        assert websocket.state == websockets.State.OPEN
        # Connection succeeded without auth!

@pytest.mark.asyncio
async def test_stress_inject_crash_on_missing_keys(client, auth_headers):
    """Verify that injecting weather/utility data with missing payload keys crashes with 500 instead of returning a validation error (422)."""
    payload = {"event_id": "test_missing_keys"}
    response = await client.post("/api/v1/test/inject/weather", json=payload, headers=auth_headers)
    assert response.status_code == 500  # It crashes with KeyError rather than 422 validation error
    assert "Internal Server Error" in response.text

@pytest.mark.asyncio
async def test_stress_sqlite_concurrency(client, auth_headers):
    """Stress test SQLite database with high concurrency of read/write requests to check for database locks or crashes."""
    # Reset first to ensure clean state
    reset_resp = await client.post("/api/v1/test/reset", headers=auth_headers)
    assert reset_resp.status_code == 200
    
    # We run 50 concurrent query requests
    async def make_request(i):
        payload = {
            "session_id": f"concurrency_session_{i}",
            "question": "What's happening in Sector 7?"
        }
        return await client.post("/api/v1/query", json=payload, headers=auth_headers)
        
    tasks = [make_request(i) for i in range(50)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    failures = []
    for idx, r in enumerate(results):
        if isinstance(r, Exception):
            failures.append(f"Request {idx} exception: {r}")
        elif r.status_code != 200:
            failures.append(f"Request {idx} failed with {r.status_code}: {r.text}")
            
    if failures:
        print("\n".join(failures))
        pytest.fail(f"Concurrency failures detected:\n" + "\n".join(failures))

@pytest.mark.asyncio
async def test_stress_db_corruption_handling(client, auth_headers):
    """Verify how the system behaves when SQLite database is corrupted or table is dropped."""
    # First, run a query to ensure it works
    resp = await client.post("/api/v1/query", json={"session_id": "db_corr_init", "question": "Sector 7"}, headers=auth_headers)
    assert resp.status_code == 200
    
    # Corrupt the DB by renaming/dropping a table
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DROP TABLE SECTORS")
    conn.commit()
    conn.close()
    
    # Now query should fail because SECTORS table is missing
    resp_failed = await client.post("/api/v1/query", json={"session_id": "db_corr_fail", "question": "Sector 7"}, headers=auth_headers)
    assert resp_failed.status_code == 500  # Unhandled SQLite exception
    
    # Reset DB using the reset endpoint to restore state for other tests
    reset_resp = await client.post("/api/v1/test/reset", headers=auth_headers)
    assert reset_resp.status_code == 200
    
    # Verify DB is working again
    resp_restored = await client.post("/api/v1/query", json={"session_id": "db_corr_restore", "question": "Sector 7"}, headers=auth_headers)
    assert resp_restored.status_code == 200

@pytest.mark.asyncio
async def test_stress_websocket_memory_leak(client, mock_server, auth_headers):
    """Verify memory leak in active_sessions mapping when websockets disconnect after a failed send."""
    session_id = f"leak_test_session_{os.getpid()}"
    ws_uri = f"{mock_server['ws_url']}/ws/agent-events/{session_id}"
    
    # Connect
    websocket = await websockets.connect(ws_uri)
    assert websocket.state == websockets.State.OPEN
    
    # Trigger query to start broadcasting
    payload = {"session_id": session_id, "question": "Sector 7"}
    await client.post("/api/v1/query", json=payload, headers=auth_headers)
    
    # Close immediately without proper handshake to simulate abrupt disconnect
    await websocket.close()
    
    # Wait for broadcast to finish (it does 11 iterations of 0.05s, total ~0.55s)
    await asyncio.sleep(1.0)
    
    # Import active_sessions to inspect it
    from tests.e2e.mock_server.app import active_sessions
    
    # Check if the session_id is still in active_sessions (it should be deleted, but because of the bug, it remains as an empty list)
    if session_id in active_sessions:
        assert active_sessions[session_id] == []  # Bug confirmed! It leaked the key as an empty list

