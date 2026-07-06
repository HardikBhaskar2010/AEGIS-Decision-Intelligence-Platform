# AEGIS Mock Server - simulating services deployed on the Gemini Enterprise Agent Platform.
import os
import sqlite3
import json
import uuid
import asyncio
from datetime import datetime
from typing import Dict, List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Header, Body
from pydantic import BaseModel

app = FastAPI(title="AEGIS Mock Server", version="1.0.0")

# Session WebSockets storage
active_sessions: Dict[str, List[WebSocket]] = {}

# DB Path
DB_PATH = os.path.join(os.path.dirname(__file__), "mock_db.sqlite")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Drop existing tables to ensure a clean state
    cursor.execute("DROP TABLE IF EXISTS SECTORS")
    cursor.execute("DROP TABLE IF EXISTS CITIZEN_FEEDBACK")
    cursor.execute("DROP TABLE IF EXISTS WEATHER_EVENTS")
    cursor.execute("DROP TABLE IF EXISTS UTILITY_STATUS")
    cursor.execute("DROP TABLE IF EXISTS TRANSIT_STATUS")
    cursor.execute("DROP TABLE IF EXISTS SITUATION_BRIEFS")

    # Create tables
    cursor.execute("""
        CREATE TABLE SECTORS (
            sector_id TEXT PRIMARY KEY,
            name TEXT,
            lat REAL,
            lng REAL,
            population INTEGER
        )
    """)
    cursor.execute("""
        CREATE TABLE CITIZEN_FEEDBACK (
            feedback_id TEXT PRIMARY KEY,
            sector_id TEXT,
            ts TEXT,
            category TEXT,
            sentiment TEXT,
            raw_text TEXT,
            FOREIGN KEY(sector_id) REFERENCES SECTORS(sector_id)
        )
    """)
    cursor.execute("""
        CREATE TABLE WEATHER_EVENTS (
            event_id TEXT PRIMARY KEY,
            sector_id TEXT,
            ts TEXT,
            event_type TEXT,
            severity REAL,
            FOREIGN KEY(sector_id) REFERENCES SECTORS(sector_id)
        )
    """)
    cursor.execute("""
        CREATE TABLE UTILITY_STATUS (
            status_id TEXT PRIMARY KEY,
            sector_id TEXT,
            ts TEXT,
            utility_type TEXT,
            status TEXT,
            FOREIGN KEY(sector_id) REFERENCES SECTORS(sector_id)
        )
    """)
    cursor.execute("""
        CREATE TABLE TRANSIT_STATUS (
            status_id TEXT PRIMARY KEY,
            sector_id TEXT,
            ts TEXT,
            line_id TEXT,
            status TEXT,
            FOREIGN KEY(sector_id) REFERENCES SECTORS(sector_id)
        )
    """)
    cursor.execute("""
        CREATE TABLE SITUATION_BRIEFS (
            brief_id TEXT PRIMARY KEY,
            sector_id TEXT,
            ts TEXT,
            risk_score REAL,
            confidence REAL,
            recommendation TEXT,
            narrative TEXT,
            session_id TEXT,
            rainfall_intensity_pct REAL DEFAULT 0.0,
            FOREIGN KEY(sector_id) REFERENCES SECTORS(sector_id)
        )
    """)

    # Seed data from JSON datasets
    datasets_dir = os.path.join(os.path.dirname(__file__), "datasets")
    
    # Helper to load JSON
    def load_json(filename):
        path = os.path.join(datasets_dir, filename)
        if os.path.exists(path):
            with open(path, "r") as f:
                return json.load(f)
        return []

    # Insert Sectors
    sectors = load_json("sectors.json")
    for s in sectors:
        cursor.execute(
            "INSERT INTO SECTORS (sector_id, name, lat, lng, population) VALUES (?, ?, ?, ?, ?)",
            (s["sector_id"], s["name"], s["lat"], s["lng"], s["population"])
        )

    # Insert Weather Events
    weather = load_json("weather.json")
    for w in weather:
        cursor.execute(
            "INSERT INTO WEATHER_EVENTS (event_id, sector_id, ts, event_type, severity) VALUES (?, ?, ?, ?, ?)",
            (w["event_id"], w["sector_id"], w["ts"], w["event_type"], w["severity"])
        )

    # Insert Utilities
    utilities = load_json("utility.json")
    for u in utilities:
        cursor.execute(
            "INSERT INTO UTILITY_STATUS (status_id, sector_id, ts, utility_type, status) VALUES (?, ?, ?, ?, ?)",
            (u["status_id"], u["sector_id"], u["ts"], u["utility_type"], u["status"])
        )

    # Insert Transit
    transit = load_json("transit.json")
    for t in transit:
        cursor.execute(
            "INSERT INTO TRANSIT_STATUS (status_id, sector_id, ts, line_id, status) VALUES (?, ?, ?, ?, ?)",
            (t["status_id"], t["sector_id"], t["ts"], t["line_id"], t["status"])
        )

    # Insert Citizen Feedback
    feedback = load_json("feedback.json")
    for f in feedback:
        cursor.execute(
            "INSERT INTO CITIZEN_FEEDBACK (feedback_id, sector_id, ts, category, sentiment, raw_text) VALUES (?, ?, ?, ?, ?, ?)",
            (f["feedback_id"], f["sector_id"], f["ts"], f["category"], f["sentiment"], f["raw_text"])
        )

    conn.commit()
    conn.close()

# Initialize DB on import/startup
init_db()

# Pydantic schemas
class QueryRequest(BaseModel):
    session_id: str
    question: str

class WhatIfAdjustment(BaseModel):
    rainfall_intensity_pct: float

class WhatIfRequest(BaseModel):
    brief_id: str
    adjustment: WhatIfAdjustment

def verify_token(authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization scheme")
    token = authorization.split(" ")[1]
    if token.startswith("mock-") or token.startswith("mock_") or token == "test-token-key":
        return {"uid": "mock-user", "email": "mock@aegis.gov"}
    raise HTTPException(status_code=401, detail="Invalid token")

async def broadcast_ws_events(session_id: str, sector_id: str, brief_id: str):
    """Simulate ADK 2.0 multi-agent event stream."""
    if session_id not in active_sessions or not active_sessions[session_id]:
        return

    events = [
        {"type": "agent_start", "agent": "Orchestrator", "detail": "Orchestration workflow started."},
        {"type": "agent_start", "agent": "Query Agent", "detail": "Fetching sector domain data from BigQuery."},
        {"type": "tool_call", "agent": "Query Agent", "tool": "BigQuery MCP", "detail": f"SELECT * FROM `{sector_id}.feeds`"},
        {"type": "agent_result", "agent": "Query Agent", "summary": f"Retrieved current status feeds for {sector_id}."},
        {"type": "agent_start", "agent": "Correlation Agent", "detail": "Analyzing multi-domain dependencies."},
        {"type": "agent_result", "agent": "Correlation Agent", "summary": "Identified weather-utility-transit correlation factors."},
        {"type": "agent_start", "agent": "Forecast Agent", "detail": "Calculating risk trajectory projections."},
        {"type": "agent_result", "agent": "Forecast Agent", "summary": "Forecasted peak risk window and cascading thresholds."},
        {"type": "agent_start", "agent": "Narrative Agent", "detail": "Synthesizing executive brief using Gemini 3.1 Pro."},
        {"type": "agent_result", "agent": "Narrative Agent", "summary": "Narrative generation completed."},
        {"type": "final_brief", "agent": "Orchestrator", "summary": "Workflow completed. Situation brief generated.", "detail": brief_id}
    ]

    for event in events:
        payload = {
            **event,
            "ts": datetime.utcnow().isoformat()
        }
        # Copy list to prevent mutation during iteration
        websockets_to_send = list(active_sessions[session_id])
        for ws in websockets_to_send:
            try:
                await ws.send_json(payload)
            except Exception:
                # Handle stale connections
                if ws in active_sessions[session_id]:
                    active_sessions[session_id].remove(ws)
        await asyncio.sleep(0.05)  # yield control and simulate network latency

@app.post("/api/v1/query")
async def query_engine(req: QueryRequest, user=Depends(verify_token)):
    # Parse sector_id from query question
    question_lower = req.question.lower()
    sector_id = "sector_7"  # Default
    if "sector 3" in question_lower or "sector_3" in question_lower:
        sector_id = "sector_3"
    elif "sector 1" in question_lower or "sector_1" in question_lower:
        sector_id = "sector_1"
    else:
        # If an unknown sector is explicitly referenced, e.g., Sector 99
        import re
        match = re.search(r"sector\s*(\d+)", question_lower)
        if match:
            sector_id = f"sector_{match.group(1)}"
    
    # Query current DB status for the sector
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if sector exists
    cursor.execute("SELECT * FROM SECTORS WHERE sector_id = ?", (sector_id,))
    sector_row = cursor.fetchone()
    if not sector_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Sector not found")

    # Get latest weather
    cursor.execute("SELECT * FROM WEATHER_EVENTS WHERE sector_id = ? ORDER BY ts DESC LIMIT 1", (sector_id,))
    weather_row = cursor.fetchone()
    
    # Get latest utility
    cursor.execute("SELECT * FROM UTILITY_STATUS WHERE sector_id = ? ORDER BY ts DESC LIMIT 1", (sector_id,))
    utility_row = cursor.fetchone()

    # Get latest transit
    cursor.execute("SELECT * FROM TRANSIT_STATUS WHERE sector_id = ? ORDER BY ts DESC LIMIT 1", (sector_id,))
    transit_row = cursor.fetchone()

    # Get feedback count
    cursor.execute("SELECT COUNT(*) as cnt FROM CITIZEN_FEEDBACK WHERE sector_id = ?", (sector_id,))
    feedback_count = cursor.fetchone()["cnt"]

    conn.close()

    # Calculate dynamic risk score
    severity = weather_row["severity"] if weather_row else 0.0
    weather_type = weather_row["event_type"] if weather_row else "CLEAR"
    utility_status = utility_row["status"] if utility_row else "OPERATIONAL"
    transit_status = transit_row["status"] if transit_row else "OPERATIONAL"

    risk = 20.0  # Base
    risk += severity * 40.0
    # Fix: check all utility failure states, not just FAILED (matches production seeder)
    if utility_status in ("FAILED", "OUTAGE"):
        risk += 25.0
    elif utility_status == "DEGRADED":
        risk += 10.0
    if transit_status in ("DELAYED", "SUSPENDED"):
        risk += 15.0
    elif transit_status == "BLOCKED":
        risk += 25.0
    risk += feedback_count * 4.0
    risk = min(100.0, max(0.0, risk))

    # Determine confidence
    confidence = 0.95
    if not weather_row or not utility_row or not transit_row:
        confidence = 0.70

    # Build recommendations and narrative
    recs = []
    if utility_status in ("FAILED", "OUTAGE", "DEGRADED"):
        recs.append("Dispatch secondary repair teams for emergency restoration.")
    if transit_status in ["DELAYED", "BLOCKED", "SUSPENDED"]:
        recs.append("Reroute public transit lines and establish shuttle lanes.")
    if severity > 0.6:
        recs.append("Issue alert warning citizens to stay indoors.")
    if not recs:
        recs.append("Continue normal automated monitoring of sector parameters.")
    recommendation = " | ".join(recs)

    narrative = (
        f"Sector {sector_row['name']} currently demonstrates a risk score of {risk}%. "
        f"Weather is categorized as {weather_type} (severity: {severity}). "
        f"Utility services are {utility_status}. "
        f"Transit operations are {transit_status}. "
        f"We detected {feedback_count} active citizen complaints."
    )

    brief_id = f"brief_{uuid.uuid4().hex[:8]}"
    generated_at = datetime.utcnow().isoformat()

    # Normalize risk score to [0.0, 1.0] fraction for storage and API responses
    risk_fraction = risk / 100.0

    # Save brief to DB
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO SITUATION_BRIEFS 
        (brief_id, sector_id, ts, risk_score, confidence, recommendation, narrative, session_id) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (brief_id, sector_id, generated_at, risk_fraction, confidence, recommendation, narrative, req.session_id)
    )
    conn.commit()
    conn.close()

    # Broadcast async agent events via WS
    asyncio.create_task(broadcast_ws_events(req.session_id, sector_id, brief_id))

    return {
        "brief_id": brief_id,
        "sector_id": sector_id,
        "risk_score": risk_fraction,
        "confidence": confidence,
        "recommendation": recommendation,
        "narrative": narrative,
        "sources": {
            "sql": f"SELECT * FROM `{sector_id}.feeds` WHERE ts <= '{generated_at}'",
            "signals_used": ["weather", "utility", "transit", "feedback"]
        },
        "generated_at": generated_at
    }

@app.post("/api/v1/whatif")
async def whatif_simulation(req: WhatIfRequest, user=Depends(verify_token)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM SITUATION_BRIEFS WHERE brief_id = ?", (req.brief_id,))
    brief = cursor.fetchone()
    
    if not brief:
        conn.close()
        raise HTTPException(status_code=404, detail="Brief not found")

    original_risk = brief["risk_score"]  # Already stored as fraction [0.0, 1.0]
    original_risk_pct = original_risk * 100.0

    # Calculate adjusted risk score
    # Rainfall intensity adjustment affects risk score: +1% rainfall intensity adds 0.4% risk score
    adjustment_val = req.adjustment.rainfall_intensity_pct
    adjusted_risk_pct = original_risk_pct + (adjustment_val * 0.4)
    adjusted_risk_pct = min(100.0, max(0.0, adjusted_risk_pct))
    adjusted_risk_fraction = adjusted_risk_pct / 100.0

    delta = adjusted_risk_fraction - original_risk

    narrative_delta = (
        f"Simulating a {adjustment_val}% change in rainfall intensity. "
        f"This alters the sector risk rating by {delta * 100:+.2f}%, shifting it from "
        f"{original_risk_pct:.2f}% to {adjusted_risk_pct:.2f}%."
    )

    # Update brief with adjustment (store as fraction)
    cursor.execute(
        """
        UPDATE SITUATION_BRIEFS 
        SET risk_score = ?, narrative = ?, rainfall_intensity_pct = ? 
        WHERE brief_id = ?
        """,
        (adjusted_risk_fraction, brief["narrative"] + f" [What-If Adjusted: {narrative_delta}]", adjustment_val, req.brief_id)
    )
    conn.commit()
    conn.close()

    return {
        "brief_id": req.brief_id,
        "adjusted_risk_score": adjusted_risk_fraction,
        "delta": delta,
        "narrative_delta": narrative_delta
    }

@app.get("/api/v1/sectors")
async def get_sectors(user=Depends(verify_token)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM SECTORS")
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

@app.get("/api/v1/briefs/{sector_id}")
async def get_sector_brief(sector_id: str, user=Depends(verify_token)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM SITUATION_BRIEFS WHERE sector_id = ? ORDER BY ts DESC LIMIT 1", (sector_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Brief for sector not found")
        
    return dict(row)

@app.get("/api/v1/history/{session_id}")
async def get_session_history(session_id: str, user=Depends(verify_token)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM SITUATION_BRIEFS WHERE session_id = ? ORDER BY ts DESC", (session_id,))
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

@app.post("/api/v1/test/reset")
async def reset_database(user=Depends(verify_token)):
    """Reset endpoint for E2E tests to enforce a clean database seed state."""
    init_db()
    return {"status": "success", "message": "Database reset and seeded."}

@app.get("/healthz")
async def healthz():
    """Liveness/readiness probe for Cloud Run."""
    return {"status": "ok"}

@app.post("/api/v1/test/inject/weather")
async def inject_weather(data: dict = Body(...), user=Depends(verify_token)):
    """Inject dynamic weather data for testing propagation."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO WEATHER_EVENTS (event_id, sector_id, ts, event_type, severity) VALUES (?, ?, ?, ?, ?)",
        (data.get("event_id", f"inj_{uuid.uuid4().hex[:6]}"), data["sector_id"], data["ts"], data["event_type"], data["severity"])
    )
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.post("/api/v1/test/inject/utility")
async def inject_utility(data: dict = Body(...), user=Depends(verify_token)):
    """Inject dynamic utility status for testing propagation."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO UTILITY_STATUS (status_id, sector_id, ts, utility_type, status) VALUES (?, ?, ?, ?, ?)",
        (data.get("status_id", f"inj_{uuid.uuid4().hex[:6]}"), data["sector_id"], data["ts"], data["utility_type"], data["status"])
    )
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.websocket("/ws/agent-events/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    if session_id not in active_sessions:
        active_sessions[session_id] = []
    active_sessions[session_id].append(websocket)
    try:
        while True:
            # Keep connection open, wait for client messages or disconnects
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        if session_id in active_sessions and websocket in active_sessions[session_id]:
            active_sessions[session_id].remove(websocket)
            if not active_sessions[session_id]:
                del active_sessions[session_id]
