# Tier 4 tests for the AEGIS Decision Intelligence Platform running on the Gemini Enterprise Agent Platform.
import pytest
import asyncio

@pytest.mark.tier4
async def test_scenario_1_cascading_failure(client, auth_headers):
    """Scenario 1: Multi-domain cascading failure (storm + utility outage in Sector 7) on the Gemini Enterprise Agent Platform."""
    # 1. Reset database
    await client.post("/api/v1/test/reset", headers=auth_headers)

    # 2. Inject heavy storm (severity 0.90) and utility failure in Sector 7
    await client.post("/api/v1/test/inject/weather", json={
        "event_id": "sc1_storm",
        "sector_id": "sector_7",
        "ts": "2026-07-05T13:00:00Z",
        "event_type": "STORM",
        "severity": 0.90
    }, headers=auth_headers)

    await client.post("/api/v1/test/inject/utility", json={
        "status_id": "sc1_power",
        "sector_id": "sector_7",
        "ts": "2026-07-05T13:05:00Z",
        "utility_type": "POWER",
        "status": "FAILED"
    }, headers=auth_headers)

    # 3. Query Sector 7 and assert the risk is highly elevated and includes proper recommendations
    response = await client.post("/api/v1/query", json={
        "session_id": "sc1_session",
        "question": "What is the status of Sector 7?"
    }, headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    # Base 20 + weather (0.9 * 40 = 36) + utility (25) + transit (15) + feedback (2 * 4 = 8) = 104 -> capped at 100
    assert data["risk_score"] >= 0.80
    assert "Dispatch secondary repair teams" in data["recommendation"]
    assert "Issue alert warning citizens" in data["recommendation"]

@pytest.mark.tier4
async def test_scenario_2_risk_escalation(client, auth_headers):
    """Scenario 2: Active disaster simulation & What-If risk escalation on the Gemini Enterprise Agent Platform."""
    # 1. Reset database
    await client.post("/api/v1/test/reset", headers=auth_headers)

    # 2. Initial query
    resp = await client.post("/api/v1/query", json={
        "session_id": "sc2_session",
        "question": "Assess Sector 3."
    }, headers=auth_headers)
    assert resp.status_code == 200
    brief_id = resp.json()["brief_id"]
    initial_risk = resp.json()["risk_score"]

    # 3. Simulate What-If with extreme rainfall increase (+50%)
    whatif_resp = await client.post("/api/v1/whatif", json={
        "brief_id": brief_id,
        "adjustment": {
            "rainfall_intensity_pct": 50.0
        }
    }, headers=auth_headers)
    assert whatif_resp.status_code == 200
    adjusted_data = whatif_resp.json()
    assert adjusted_data["adjusted_risk_score"] > initial_risk
    assert adjusted_data["delta"] == 20.0  # 50.0 * 0.4

@pytest.mark.tier4
async def test_scenario_3_complaint_and_transit_correlation(client, auth_headers):
    """Scenario 3: Citizen complaint spike & transit delay correlation on the Gemini Enterprise Agent Platform."""
    # 1. Reset database
    await client.post("/api/v1/test/reset", headers=auth_headers)

    # 2. Sector 7 has transit delayed (already seeded)
    # 3. Query Sector 7
    response = await client.post("/api/v1/query", json={
        "session_id": "sc3_session",
        "question": "Verify Sector 7 transit delay correlation."
    }, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "Reroute public transit lines" in data["recommendation"]

@pytest.mark.tier4
async def test_scenario_4_outage_resolution(client, auth_headers):
    """Scenario 4: Outage resolution & risk normalization on the Gemini Enterprise Agent Platform."""
    # 1. Reset database
    await client.post("/api/v1/test/reset", headers=auth_headers)

    # 2. Get initial brief risk
    resp_init = await client.post("/api/v1/query", json={
        "session_id": "sc4_session",
        "question": "Sector 7"
    }, headers=auth_headers)
    assert resp_init.status_code == 200
    risk_init = resp_init.json()["risk_score"]

    # 3. Resolve power outage in Sector 7
    await client.post("/api/v1/test/inject/utility", json={
        "status_id": "sc4_power_resolved",
        "sector_id": "sector_7",
        "ts": "2026-07-05T14:00:00Z",
        "utility_type": "POWER",
        "status": "OPERATIONAL"
    }, headers=auth_headers)

    # 4. Query Sector 7 again and assert risk score decreased
    resp_after = await client.post("/api/v1/query", json={
        "session_id": "sc4_session",
        "question": "Sector 7"
    }, headers=auth_headers)
    assert resp_after.status_code == 200
    risk_after = resp_after.json()["risk_score"]
    assert risk_after < risk_init

@pytest.mark.tier4
async def test_scenario_5_concurrent_operator_actions(client, auth_headers):
    """Scenario 5: Multi-session concurrent operator actions on the Gemini Enterprise Agent Platform."""
    # 1. Reset database
    await client.post("/api/v1/test/reset", headers=auth_headers)

    # 2. Run concurrent requests
    async def query_sector(session_id, question):
        return await client.post("/api/v1/query", json={
            "session_id": session_id,
            "question": question
        }, headers=auth_headers)

    tasks = [
        query_sector("session_op1", "Sector 3 status"),
        query_sector("session_op2", "Sector 1 status")
    ]
    results = await asyncio.gather(*tasks)

    for r in results:
        assert r.status_code == 200
        assert "brief_id" in r.json()
