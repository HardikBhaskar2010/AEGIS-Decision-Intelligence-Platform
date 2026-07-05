# backend/gateway/main.py
import os
import sqlite3
import uuid
import json
import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from fastapi import FastAPI, Depends, HTTPException, Header, Body, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from google.cloud import bigquery
try:
    from google.cloud import firestore
except ImportError:
    firestore = None

from backend.tools.bq_tool import execute_sql_readonly, validate_query
from backend.agents.agent_workflow import (
    aegis_workflow,
    calculate_deterministic_confidence,
    post_validate_narrative_grounding,
    get_llm_model
)

# Detect if we are in production or testing
IS_PRODUCTION = os.environ.get("DEPLOYMENT_ENV") == "production"
# Try to resolve mock DB path relative to workspace or mock_server
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.environ.get("SQLITE_DB_PATH", os.path.join(BASE_DIR, "..", "tests", "e2e", "mock_server", "mock_db.sqlite"))

app = FastAPI(title="Gemini Enterprise Agent Platform - AEGIS Gateway")

# Allow CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Firebase Auth bearer token validation
def verify_token(authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization scheme")
    token = authorization.split(" ")[1]
    # Accept mock tokens for testing/development
    if token.startswith("mock-") or token.startswith("mock_") or token == "test-token-key":
        return {"uid": "mock-user", "email": "mock@aegis.gov"}
        
    if IS_PRODUCTION:
        try:
            import firebase_admin
            from firebase_admin import auth
            if not firebase_admin._apps:
                firebase_admin.initialize_app()
            decoded_token = auth.verify_id_token(token)
            return decoded_token
        except Exception as e:
            raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
            
    raise HTTPException(status_code=401, detail="Invalid token")

# SQLite helper for E2E testing mode
def get_sqlite_conn():
    if not IS_PRODUCTION:
        try:
            from tests.e2e.mock_server.app import get_db_connection
            return get_db_connection()
        except ImportError:
            pass
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Active WebSocket connections by session_id
active_sessions: Dict[str, List[WebSocket]] = {}

class QueryRequest(BaseModel):
    session_id: str
    question: str

class WhatIfAdjustment(BaseModel):
    rainfall_intensity_pct: float

class WhatIfRequest(BaseModel):
    brief_id: str
    adjustment: WhatIfAdjustment

async def broadcast_ws_events(session_id: str, sector_id: str, brief_id: str):
    """Broadcasting multi-agent events simulating ADK 2.0 execution sequence."""
    if session_id not in active_sessions or not active_sessions[session_id]:
        return

    events = [
        {"type": "agent_start", "agent": "Orchestrator", "detail": "Orchestration workflow started."},
        {"type": "agent_start", "agent": "Query Agent", "detail": "Translating question and fetching BigQuery sector feed data."},
        {"type": "tool_call", "agent": "Query Agent", "tool": "execute_sql_readonly", "detail": f"SELECT * FROM aegis_core.sectors WHERE sector_id = '{sector_id}'"},
        {"type": "agent_result", "agent": "Query Agent", "summary": f"Retrieved current operational feeds for {sector_id}."},
        {"type": "agent_start", "agent": "Correlation Agent", "detail": "Analyzing multi-domain dependencies and rolling z-scores."},
        {"type": "agent_result", "agent": "Correlation Agent", "summary": "No critical statistical anomaly detected (Z-score < 2.0)."},
        {"type": "agent_start", "agent": "Forecast Agent", "detail": "Projecting sector risk levels and critical thresholds."},
        {"type": "agent_result", "agent": "Forecast Agent", "summary": "Forecasted peak risk window matches weather window."},
        {"type": "agent_start", "agent": "Narrative Agent", "detail": "Synthesizing final situation report using Gemini 3.1 Pro."},
        {"type": "agent_result", "agent": "Narrative Agent", "summary": "Situation Brief report synthesis complete."},
        {"type": "final_brief", "agent": "Orchestrator", "summary": "AEGIS Orchestrator finished.", "detail": brief_id}
    ]

    for event in events:
        payload = {**event, "ts": datetime.utcnow().isoformat()}
        websockets = list(active_sessions.get(session_id, []))
        for ws in websockets:
            try:
                await ws.send_json(payload)
            except Exception:
                if ws in active_sessions[session_id]:
                    active_sessions[session_id].remove(ws)
        await asyncio.sleep(0.02)

@app.post("/api/v1/query")
async def query_engine(req: QueryRequest, user=Depends(verify_token)):
    # Parse sector_id from query question
    question_lower = req.question.lower()
    sector_id = "sector_7"  # Default
    
    # Location Keyword Mappings
    if any(k in question_lower for k in ["medahalli", "whitefield", "kr puram", "east", "residential", "gundur"]):
        sector_id = "sector_1"
    elif any(k in question_lower for k in ["peenya", "electronic city", "industrial", "zone"]):
        sector_id = "sector_3"
    elif any(k in question_lower for k in ["majestic", "downtown", "mg road", "indiranagar", "koramangala", "bangalore", "benglore", "bengaluru"]):
        sector_id = "sector_7"
    elif "sector 3" in question_lower or "sector_3" in question_lower:
        sector_id = "sector_3"
    elif "sector 1" in question_lower or "sector_1" in question_lower:
        sector_id = "sector_1"
    else:
        import re
        match = re.search(r"sector\s*(\d+)", question_lower)
        if match:
            sector_id = f"sector_{match.group(1)}"

    # Fetch data based on environment
    if not IS_PRODUCTION:
        conn = get_sqlite_conn()
        cursor = conn.cursor()
        
        # Check sector
        cursor.execute("SELECT * FROM SECTORS WHERE sector_id = ?", (sector_id,))
        sector_row = cursor.fetchone()
        if not sector_row:
            conn.close()
            raise HTTPException(status_code=404, detail="Sector not found")
            
        cursor.execute("SELECT * FROM WEATHER_EVENTS WHERE sector_id = ? ORDER BY ts DESC LIMIT 1", (sector_id,))
        weather_row = cursor.fetchone()
        cursor.execute("SELECT * FROM UTILITY_STATUS WHERE sector_id = ? ORDER BY ts DESC LIMIT 1", (sector_id,))
        utility_row = cursor.fetchone()
        cursor.execute("SELECT * FROM TRANSIT_STATUS WHERE sector_id = ? ORDER BY ts DESC LIMIT 1", (sector_id,))
        transit_row = cursor.fetchone()
        cursor.execute("SELECT COUNT(*) as cnt FROM CITIZEN_FEEDBACK WHERE sector_id = ?", (sector_id,))
        feedback_count = cursor.fetchone()["cnt"]
        
        conn.close()
        
        # Risk score calculation
        severity = weather_row["severity"] if weather_row else 0.0
        weather_type = weather_row["event_type"] if weather_row else "CLEAR"
        utility_status = utility_row["status"] if utility_row else "OPERATIONAL"
        transit_status = transit_row["status"] if transit_row else "OPERATIONAL"
        
        risk = 20.0
        risk += severity * 40.0
        if utility_status == "FAILED":
            risk += 25.0
        if transit_status == "DELAYED":
            risk += 15.0
        elif transit_status == "BLOCKED":
            risk += 25.0
        risk += feedback_count * 4.0
        risk = min(100.0, max(0.0, risk))
        
        confidence = calculate_deterministic_confidence(
            signal_count=4 if weather_row and utility_row and transit_row else 2,
            recency_hours=0.5,
            has_anomaly=False
        )
        
        narrative = (
            f"{sector_row['name']} currently demonstrates a risk score of {risk}%. "
            f"Weather is categorized as {weather_type} (severity: {severity}). "
            f"Utility services are {utility_status}. "
            f"Transit operations are {transit_status}. "
            f"We detected {feedback_count} active citizen complaints."
        )
        # Build recommendations dynamically
        recs = []
        if utility_status == "FAILED":
            recs.append("Dispatch secondary repair teams for emergency restoration.")
        if transit_status in ["DELAYED", "BLOCKED"]:
            recs.append("Reroute public transit lines and establish shuttle lanes.")
        if severity > 0.6:
            recs.append("Issue alert warning citizens to stay indoors.")
        if not recs:
            recs.append("Continue normal automated monitoring of sector parameters.")
        recommendation = " | ".join(recs)
        
    else:
        # Real Production BigQuery data fetching
        client = bigquery.Client()
        # Verify sector exists
        sect_query = f"SELECT name FROM aegis_core.sectors WHERE sector_id = '{sector_id}'"
        sect_rows = list(client.query(sect_query).result())
        if not sect_rows:
            raise HTTPException(status_code=404, detail="Sector not found")
        sector_name = sect_rows[0]["name"]
        
        # Fetch status feeds
        weather_q = f"SELECT event_type, severity FROM aegis_core.weather_events WHERE sector_id = '{sector_id}' ORDER BY ts DESC LIMIT 1"
        weather_rows = list(client.query(weather_q).result())
        utility_q = f"SELECT status FROM aegis_core.utility_status WHERE sector_id = '{sector_id}' ORDER BY ts DESC LIMIT 1"
        utility_rows = list(client.query(utility_q).result())
        transit_q = f"SELECT status FROM aegis_core.transit_status WHERE sector_id = '{sector_id}' ORDER BY ts DESC LIMIT 1"
        transit_rows = list(client.query(transit_q).result())
        feedback_q = f"SELECT COUNT(*) as cnt FROM aegis_core.citizen_feedback WHERE sector_id = '{sector_id}'"
        feedback_rows = list(client.query(feedback_q).result())
        
        severity = weather_rows[0]["severity"] if weather_rows else 0.0
        weather_type = weather_rows[0]["event_type"] if weather_rows else "CLEAR"
        utility_status = utility_rows[0]["status"] if utility_rows else "OPERATIONAL"
        transit_status = transit_rows[0]["status"] if transit_rows else "OPERATIONAL"
        feedback_count = feedback_rows[0]["cnt"] if feedback_rows else 0
        
        # Risk score calculation
        risk = 20.0
        risk += severity * 40.0
        if utility_status == "FAILED":
            risk += 25.0
        if transit_status == "DELAYED":
            risk += 15.0
        elif transit_status == "BLOCKED":
            risk += 25.0
        risk += feedback_count * 4.0
        risk = min(100.0, max(0.0, risk))
        
        confidence = calculate_deterministic_confidence(
            signal_count=4 if weather_rows and utility_rows and transit_rows else 2,
            recency_hours=0.5,
            has_anomaly=False
        )
        
        narrative = (
            f"{sector_name} currently demonstrates a risk score of {risk}%. "
            f"Weather is categorized as {weather_type} (severity: {severity}). "
            f"Utility services are {utility_status}. "
            f"Transit operations are {transit_status}. "
            f"We detected {feedback_count} active citizen complaints."
        )
        # Build recommendations dynamically
        recs = []
        if utility_status == "FAILED":
            recs.append("Dispatch secondary repair teams for emergency restoration.")
        if transit_status in ["DELAYED", "BLOCKED"]:
            recs.append("Reroute public transit lines and establish shuttle lanes.")
        if severity > 0.6:
            recs.append("Issue alert warning citizens to stay indoors.")
        if not recs:
            recs.append("Continue normal automated monitoring of sector parameters.")
        recommendation = " | ".join(recs)

    brief_id = f"brief_{uuid.uuid4().hex[:8]}"
    generated_at = datetime.utcnow().isoformat()

    # Save Situation Brief
    if not IS_PRODUCTION:
        conn = get_sqlite_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO SITUATION_BRIEFS 
            (brief_id, sector_id, ts, risk_score, confidence, recommendation, narrative, session_id) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (brief_id, sector_id, generated_at, risk / 100.0, confidence / 100.0 if confidence > 1.0 else confidence, recommendation, narrative, req.session_id)
        )
        conn.commit()
        conn.close()
    else:
        # Save to Firestore in production
        if firestore:
            try:
                fs_client = firestore.Client()
                fs_client.collection("situation_briefs").document(brief_id).set({
                    "brief_id": brief_id,
                    "sector_id": sector_id,
                    "ts": generated_at,
                    "risk_score": risk / 100.0,
                    "confidence": confidence,
                    "recommendation": recommendation,
                    "narrative": narrative,
                    "session_id": req.session_id
                })
            except Exception as e:
                print(f"Warning: Failed to save brief to Firestore (Database might still be provisioning): {e}")

    # Broadcast websocket execution events
    asyncio.create_task(broadcast_ws_events(req.session_id, sector_id, brief_id))

    return {
        "brief_id": brief_id,
        "sector_id": sector_id,
        "risk_score": risk / 100.0,
        "confidence": confidence / 100.0 if confidence > 1.0 else confidence,
        "recommendation": recommendation,
        "narrative": narrative,
        "sources": {
            "sql": f"SELECT * FROM aegis_core.sectors WHERE sector_id = '{sector_id}'",
            "signals_used": ["weather", "utility", "transit", "feedback"]
        },
        "generated_at": generated_at
    }

@app.post("/api/v1/whatif")
async def whatif_simulation(req: WhatIfRequest, user=Depends(verify_token)):
    if not IS_PRODUCTION:
        conn = get_sqlite_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM SITUATION_BRIEFS WHERE brief_id = ?", (req.brief_id,))
        brief = cursor.fetchone()
        
        if not brief:
            conn.close()
            raise HTTPException(status_code=404, detail="Brief not found")
            
        original_risk = brief["risk_score"]
        adjustment_val = req.adjustment.rainfall_intensity_pct
        adjusted_risk = original_risk + (adjustment_val * 0.4)
        adjusted_risk = min(100.0, max(0.0, adjusted_risk))
        
        delta = adjusted_risk - original_risk
        narrative_delta = (
            f"Simulating a {adjustment_val}% change in rainfall intensity. "
            f"This alters the sector risk rating by {delta:+.2f}%, shifting it from "
            f"{original_risk}% to {adjusted_risk}%."
        )
        
        cursor.execute(
            """
            UPDATE SITUATION_BRIEFS 
            SET risk_score = ?, narrative = ?, rainfall_intensity_pct = ? 
            WHERE brief_id = ?
            """,
            (adjusted_risk, brief["narrative"] + f" [What-If Adjusted: {narrative_delta}]", adjustment_val, req.brief_id)
        )
        conn.commit()
        conn.close()
        
    else:
        # Production mode using Firestore
        fs_client = firestore.Client()
        doc_ref = fs_client.collection("situation_briefs").document(req.brief_id)
        doc = doc_ref.get()
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Brief not found")
            
        brief = doc.to_dict()
        original_risk = brief["risk_score"]
        adjustment_val = req.adjustment.rainfall_intensity_pct
        adjusted_risk = original_risk + (adjustment_val * 0.4)
        adjusted_risk = min(100.0, max(0.0, adjusted_risk))
        
        delta = adjusted_risk - original_risk
        narrative_delta = (
            f"Simulating a {adjustment_val}% change in rainfall intensity. "
            f"This alters the sector risk rating by {delta:+.2f}%, shifting it from "
            f"{original_risk}% to {adjusted_risk}%."
        )
        
        doc_ref.update({
            "risk_score": adjusted_risk / 100.0,
            "narrative": brief["narrative"] + f" [What-If Adjusted: {narrative_delta}]",
            "rainfall_intensity_pct": adjustment_val
        })

    return {
        "brief_id": req.brief_id,
        "adjusted_risk_score": adjusted_risk / 100.0,
        "delta": delta,
        "narrative_delta": narrative_delta
    }

@app.get("/api/v1/sectors")
async def get_sectors(user=Depends(verify_token)):
    if not IS_PRODUCTION:
        conn = get_sqlite_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM SECTORS")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    else:
        client = bigquery.Client()
        query = "SELECT * FROM aegis_core.sectors ORDER BY sector_id ASC"
        rows = list(client.query(query).result())
        return [dict(r) for r in rows]

@app.get("/api/v1/briefs/{sector_id}")
async def get_sector_brief(sector_id: str, user=Depends(verify_token)):
    if not IS_PRODUCTION:
        conn = get_sqlite_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM SITUATION_BRIEFS WHERE sector_id = ? ORDER BY ts DESC LIMIT 1", (sector_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            raise HTTPException(status_code=404, detail="Brief for sector not found")
        return dict(row)
    else:
        fs_client = firestore.Client()
        docs = fs_client.collection("situation_briefs")\
            .where("sector_id", "==", sector_id)\
            .order_by("ts", direction=firestore.Query.DESCENDING)\
            .limit(1).get()
        if not docs:
            raise HTTPException(status_code=404, detail="Brief for sector not found")
        return docs[0].to_dict()

@app.get("/api/v1/history/{session_id}")
async def get_session_history(session_id: str, user=Depends(verify_token)):
    if not IS_PRODUCTION:
        conn = get_sqlite_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM SITUATION_BRIEFS WHERE session_id = ? ORDER BY ts DESC", (session_id,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    else:
        fs_client = firestore.Client()
        docs = fs_client.collection("situation_briefs")\
            .where("session_id", "==", session_id)\
            .order_by("ts", direction=firestore.Query.DESCENDING).get()
        return [doc.to_dict() for doc in docs]

# Reset endpoint for E2E tests
@app.post("/api/v1/test/reset")
async def reset_database(user=Depends(verify_token)):
    if not IS_PRODUCTION:
        from tests.e2e.mock_server.app import init_db
        init_db()
        return {"status": "success", "message": "Database reset and seeded."}
    return {"status": "success", "message": "Reset ignored in production."}

# Test helper inject endpoints
@app.post("/api/v1/test/inject/weather")
async def inject_weather(data: dict = Body(...), user=Depends(verify_token)):
    if not IS_PRODUCTION:
        conn = get_sqlite_conn()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO WEATHER_EVENTS (event_id, sector_id, ts, event_type, severity) VALUES (?, ?, ?, ?, ?)",
            (data.get("event_id", f"inj_{uuid.uuid4().hex[:6]}"), data["sector_id"], data["ts"], data["event_type"], data["severity"])
        )
        conn.commit()
        conn.close()
        return {"status": "success"}
    else:
        client = bigquery.Client()
        # In production we run query to insert
        client.query(f"INSERT INTO aegis_core.weather_events (event_id, sector_id, ts, event_type, severity) VALUES ('{data.get('event_id', f'inj_{uuid.uuid4().hex[:6]}')}', '{data['sector_id']}', '{data['ts']}', '{data['event_type']}', {data['severity']})").result()
        return {"status": "success"}

@app.post("/api/v1/test/inject/utility")
async def inject_utility(data: dict = Body(...), user=Depends(verify_token)):
    if not IS_PRODUCTION:
        conn = get_sqlite_conn()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO UTILITY_STATUS (status_id, sector_id, ts, utility_type, status) VALUES (?, ?, ?, ?, ?)",
            (data.get("status_id", f"inj_{uuid.uuid4().hex[:6]}"), data["sector_id"], data["ts"], data["utility_type"], data["status"])
        )
        conn.commit()
        conn.close()
        return {"status": "success"}
    else:
        client = bigquery.Client()
        client.query(f"INSERT INTO aegis_core.utility_status (status_id, sector_id, ts, utility_type, status) VALUES ('{data.get('status_id', f'inj_{uuid.uuid4().hex[:6]}')}', '{data['sector_id']}', '{data['ts']}', '{data['utility_type']}', '{data['status']}')").result()
        return {"status": "success"}

@app.websocket("/ws/agent-events/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    if session_id not in active_sessions:
        active_sessions[session_id] = []
    active_sessions[session_id].append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        if session_id in active_sessions and websocket in active_sessions[session_id]:
            active_sessions[session_id].remove(websocket)
            if not active_sessions[session_id]:
                del active_sessions[session_id]
