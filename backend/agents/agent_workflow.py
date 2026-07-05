# backend/agents/agent_workflow.py
import os
import json
import re
import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from google.adk import Agent, Runner, Workflow
from google.adk.workflow import START, Edge
from google.adk.sessions import InMemorySessionService, Session
from google.genai import types

from backend.tools.bq_tool import execute_sql_readonly
from backend.data.config import PROJECT_ID, CORE_DATASET

# Helper to resolve Gemini models based on credentials/env
def get_llm_model(tier: str = "flash") -> str:
    """
    Returns the appropriate model string. If GCS project env is configured,
    uses the project-scoped Vertex AI model to support ADC authentication.
    """
    project = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCP_PROJECT")
    
    # Check if we should use enterprise vertexai model path
    if project:
        model_name = "gemini-2.5-flash" if tier == "flash" else "gemini-2.5-pro"
        return f"projects/{project}/locations/us-central1/publishers/google/models/{model_name}"
        
    # Default to Gemini Developer API models
    return "gemini-2.5-flash" if tier == "flash" else "gemini-2.5-pro"

# 1. Query Agent
query_agent = Agent(
    name="query_agent",
    description="Translates natural language questions to SQL and queries BigQuery.",
    instruction=f"""You are the Query Agent for the Gemini Enterprise Agent Platform.
Your task is to translate the user's natural language question into a SELECT SQL query on BigQuery.
You must use the `execute_sql_readonly` tool to run the query and retrieve the results.
Only query tables in the `{CORE_DATASET}` dataset:
- `{CORE_DATASET}.sectors`
- `{CORE_DATASET}.citizen_feedback`
- `{CORE_DATASET}.weather_events`
- `{CORE_DATASET}.utility_status`
- `{CORE_DATASET}.transit_status`

Do NOT perform inserts or deletes. Return the raw JSON results and the exact SQL query you executed.""",
    tools=[execute_sql_readonly],
    model=get_llm_model("flash")
)

# 2. Correlation Agent
correlation_agent = Agent(
    name="correlation_agent",
    description="Identifies cross-domain statistical anomalies.",
    instruction=f"""You are the Correlation Agent. Your task is to analyze the data fetched for the target sector to identify cross-domain anomalies.
Using the `execute_sql_readonly` tool, query `{CORE_DATASET}.summary_rollup` for the targeted sector to find if there is an active statistical anomaly (z-score > 2.0 or anomaly_flag = TRUE).
Identify any co-occurring events (e.g. transit delays, power outages, storm weather) and output a structured list of correlation signals.""",
    tools=[execute_sql_readonly],
    model=get_llm_model("flash")
)

# 3. Forecast Agent
forecast_agent = Agent(
    name="forecast_agent",
    description="Calculates future risk trajectory and supports what-if parameter simulations.",
    instruction="""You are the Forecast Agent.
Your task is to forecast the future risk trajectory of the sector.
Additionally, you handle what-if simulation parameter adjustments:
- Every 1% increase in rainfall intensity adds 0.4 to the risk score (max 100, min 0).
Calculate the risk score delta and explain the forecasted trajectory.""",
    model=get_llm_model("flash")
)

# 4. Narrative Agent
narrative_agent = Agent(
    name="narrative_agent",
    description="Synthesizes all findings into a Situation Brief with confidence rating.",
    instruction="""You are the Narrative Agent.
Your task is to synthesize the findings from the Query, Correlation and Forecast agents into a plain-English Situation Brief.
Summarize the current situation, cite specific sector IDs or anomaly metrics, and provide a clear operational recommendation.
Make sure all cited sector IDs or metric values exist in the upstream payloads (do not hallucinate).""",
    model=get_llm_model("pro")
)

def calculate_deterministic_confidence(
    signal_count: int, 
    recency_hours: float, 
    has_anomaly: bool
) -> float:
    """
    Deterministically computes a 0-100 confidence score based on:
    - signal_count: number of distinct signal domains corroborated (max 4: weather, utility, transit, feedback)
    - recency_hours: how old the latest data point is
    - has_anomaly: statistical rolling z-score > 2.0
    """
    # 1. Signal count score (40%)
    w1 = 0.40
    sig_score = min(signal_count / 4.0 * 100.0, 100.0)
    
    # 2. Recency score (30%)
    w2 = 0.30
    if recency_hours <= 1.0:
        rec_score = 100.0
    elif recency_hours <= 3.0:
        rec_score = 80.0
    elif recency_hours <= 12.0:
        rec_score = 50.0
    else:
        rec_score = 20.0
        
    # 3. Correlation strength score (30%)
    w3 = 0.30
    corr_score = 100.0 if has_anomaly else 70.0
    
    confidence = (w1 * sig_score) + (w2 * rec_score) + (w3 * corr_score)
    return round(confidence, 2)

def post_validate_narrative_grounding(narrative: str, upstream_ids: List[str]) -> bool:
    """
    Post-validates that all sector_id or brief_id patterns mentioned in the narrative
    exist in the upstream payloads.
    """
    found_ids = re.findall(r"\bsector_\d+\b|\bbrief_[a-f0-9]+\b", narrative.lower())
    for fid in found_ids:
        if fid not in [uid.lower() for uid in upstream_ids]:
            return False
    return True

# Assemble ADK 2.0 Workflow
edges = [
    Edge(from_node=START, to_node=query_agent),
    Edge(from_node=query_agent, to_node=correlation_agent),
    Edge(from_node=correlation_agent, to_node=forecast_agent),
    Edge(from_node=forecast_agent, to_node=narrative_agent)
]

aegis_workflow = Workflow(
    name="aegis_workflow",
    edges=edges
)
