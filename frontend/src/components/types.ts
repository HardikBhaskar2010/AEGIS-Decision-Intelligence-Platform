export interface Sector {
  sector_id: string;
  name: string;
  lat: number;
  lng: number;
  population?: number;
  risk_score: number; // 0.0 to 1.0
}

export interface SituationBrief {
  brief_id: string;
  sector_id: string;
  risk_score: number;
  confidence: number;
  recommendation: string;
  narrative: string;
  sources?: {
    sql: string;
    signals_used?: string[];
  };
  generated_at?: string;
}

export interface WhatIfResult {
  brief_id: string;
  adjusted_risk_score: number;
  delta: number;
  narrative_delta: string;
}

export interface AgentEvent {
  type: 'agent_start' | 'tool_call' | 'agent_result' | 'final_brief';
  agent: 'Orchestrator' | 'Query' | 'Correlation' | 'Forecast' | 'Narrative';
  tool?: string;
  detail?: string;
  summary?: string;
  ts: string;
}
