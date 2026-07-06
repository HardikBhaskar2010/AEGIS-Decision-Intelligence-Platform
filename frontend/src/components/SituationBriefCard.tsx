import React, { useState, useEffect, useRef } from 'react';
import {
  ShieldAlert, AlertTriangle, CheckCircle, Database,
  Cpu, HelpCircle, Zap, Activity, ChevronDown, Droplets
} from 'lucide-react';
import { LineChart, Line, Tooltip, ResponsiveContainer } from 'recharts';
import gsap from 'gsap';
import type { SituationBrief, WhatIfResult } from './types';

// ──────────────────────────────────────────────────────────────
// Props
// ──────────────────────────────────────────────────────────────
interface SituationBriefCardProps {
  brief: SituationBrief | null;
  sectorName?: string;
  isLoading: boolean;
  onWhatIfSubmit: (rainfallIntensity: number) => Promise<void>;
  whatIfResult: WhatIfResult | null;
  isWhatIfLoading: boolean;
  onResetWhatIf: () => void;
}

// ──────────────────────────────────────────────────────────────
// Risk sparkline data generator (simulated trajectory)
// ──────────────────────────────────────────────────────────────
const generateSparkData = (risk: number) => {
  const points = 8;
  const data = [];
  let v = Math.max(0.05, risk - 0.3 + Math.random() * 0.15);
  for (let i = 0; i < points; i++) {
    v = Math.min(1, Math.max(0, v + (Math.random() - 0.4) * 0.12));
    data.push({ v: parseFloat(v.toFixed(3)) });
  }
  data.push({ v: risk }); // End at current risk
  return data;
};

// ──────────────────────────────────────────────────────────────
// GSAP counter hook
// ──────────────────────────────────────────────────────────────
function useGsapCounter(target: number, enabled: boolean) {
  const elRef = useRef<HTMLSpanElement>(null);
  const objRef = useRef({ val: 0 });

  useEffect(() => {
    if (!enabled || !elRef.current) return;
    const obj = objRef.current;
    gsap.killTweensOf(obj);
    gsap.to(obj, {
      val: target,
      duration: 1.2,
      ease: 'power2.out',
      onUpdate: () => {
        if (elRef.current) {
          elRef.current.textContent = Math.round(obj.val).toString();
        }
      },
    });
  }, [target, enabled]);

  return elRef;
}

// ──────────────────────────────────────────────────────────────
// Loading Skeleton
// ──────────────────────────────────────────────────────────────
const BriefSkeleton = () => (
  <div style={{ padding: '18px 20px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
      <div className="spinner" />
      <span style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', letterSpacing: '0.08em' }}>
        SYNTHESIZING SITUATION BRIEF…
      </span>
    </div>
    <div className="brief-skeleton">
      <div className="skeleton-line" style={{ width: '45%', height: '10px' }} />
      <div className="skeleton-line" style={{ width: '70%', height: '16px' }} />
      <div className="skeleton-box" />
      <div className="skeleton-line" style={{ width: '100%', height: '12px' }} />
      <div className="skeleton-line" style={{ width: '85%', height: '12px' }} />
      <div className="skeleton-line" style={{ width: '60%', height: '12px' }} />
    </div>
  </div>
);

// ──────────────────────────────────────────────────────────────
// Main Component
// ──────────────────────────────────────────────────────────────
export const SituationBriefCard: React.FC<SituationBriefCardProps> = ({
  brief,
  sectorName,
  isLoading,
  onWhatIfSubmit,
  whatIfResult,
  isWhatIfLoading,
  onResetWhatIf,
}) => {
  const [rainfallVal, setRainfallVal] = useState<number>(50);
  const [sqlExpanded, setSqlExpanded]   = useState<boolean>(false);
  const [sigExpanded, setSigExpanded]   = useState<boolean>(false);
  const [sparkData,   setSparkData]     = useState<{ v: number }[]>([]);
  const cardRef = useRef<HTMLDivElement>(null);

  // Reset state on brief change
  useEffect(() => {
    setRainfallVal(50);
    onResetWhatIf();
    setSqlExpanded(false);
    setSigExpanded(false);
  }, [brief?.brief_id]); // eslint-disable-line react-hooks/exhaustive-deps

  // Regenerate sparkline on brief change
  useEffect(() => {
    if (brief) setSparkData(generateSparkData(brief.risk_score));
  }, [brief?.brief_id]); // eslint-disable-line react-hooks/exhaustive-deps

  // Animate card in on brief change
  useEffect(() => {
    if (brief && cardRef.current) {
      gsap.fromTo(cardRef.current,
        { opacity: 0, y: 12 },
        { opacity: 1, y: 0, duration: 0.5, ease: 'power3.out' }
      );
    }
  }, [brief?.brief_id]); // eslint-disable-line react-hooks/exhaustive-deps

  // Risk calculations
  const baseRisk    = brief ? Math.round(brief.risk_score * 100) : 0;
  const showWhatIf  = whatIfResult !== null;
  const currentRisk = showWhatIf ? Math.round((whatIfResult?.adjusted_risk_score ?? 0) * 100) : baseRisk;

  const riskColor = currentRisk < 35 ? 'var(--risk-low)' : currentRisk < 70 ? 'var(--risk-med)' : 'var(--risk-high)';
  const riskClass = currentRisk < 35 ? 'low' : currentRisk < 70 ? 'med' : 'high';
  const accentBar  = currentRisk < 35 ? 'low' : currentRisk < 70 ? 'med' : 'high';

  const confidence   = brief ? Math.round(brief.confidence * 100) : 0;
  const deltaVal     = showWhatIf ? Math.round((whatIfResult?.delta ?? 0) * 100) : 0;
  const deltaText    = deltaVal > 0 ? `+${deltaVal}%` : `${deltaVal}%`;
  const deltaColor   = deltaVal > 0 ? 'var(--risk-high)' : deltaVal < 0 ? 'var(--risk-low)' : 'var(--text-muted)';

  const sparkColor = currentRisk < 35 ? '#3DD6A3' : currentRisk < 70 ? '#F0B429' : '#F0453A';

  // GSAP counter ref for risk score
  const riskCounterRef = useGsapCounter(currentRisk, !!brief);
  const confCounterRef = useGsapCounter(confidence, !!brief);

  // Recommendation items split by pipe
  const recItems = brief?.recommendation?.split(' | ').filter(Boolean) ?? [];

  // ── Loading state ──────────────────────────────────────────
  if (isLoading) return <BriefSkeleton />;

  // ── Empty state ────────────────────────────────────────────
  if (!brief) {
    return (
      <div className="brief-empty">
        <div className="brief-empty-icon">
          <HelpCircle size={22} />
        </div>
        <h3>NO BRIEF SELECTED</h3>
        <p>
          Click a sector marker on the map or type a natural-language question to run the multi-agent analysis.
        </p>
      </div>
    );
  }

  // ── Main brief ─────────────────────────────────────────────
  return (
    <div className="brief-card" ref={cardRef} id={`brief-${brief.brief_id}`}>
      {/* Top accent gradient bar */}
      <div className={`brief-card-accent ${accentBar}`} />

      <div className="brief-inner">

        {/* ── Header ── */}
        <div className="brief-header">
          <div className="brief-header-left">
            <div className="brief-sector-label">
              <span className="synthetic-badge">
                <Zap size={8} />
                Synthetic Data
              </span>
              {brief.generated_at && (
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: '9px', color: 'var(--text-muted)' }}>
                  {new Date(brief.generated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                </span>
              )}
            </div>
            <div className="brief-sector-name" title={sectorName || brief.sector_id}>
              {sectorName || brief.sector_id}
            </div>
            <div style={{ fontSize: '10px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', marginTop: '1px' }}>
              {brief.brief_id}
            </div>
          </div>
          <div className={`brief-status-icon ${riskClass}`}>
            {currentRisk >= 70
              ? <ShieldAlert size={20} color="var(--risk-high)" />
              : currentRisk >= 35
              ? <AlertTriangle size={20} color="var(--risk-med)" />
              : <CheckCircle size={20} color="var(--risk-low)" />
            }
          </div>
        </div>

        {/* ── Metrics Row ── */}
        <div className="brief-metrics-row">
          {/* Risk Score */}
          <div className="metric-card">
            <div className="metric-label">Risk Index</div>
            <div className="metric-value-row">
              <span className="metric-value" style={{ color: riskColor }}>
                <span ref={riskCounterRef}>{currentRisk}</span>
                <span style={{ fontSize: '16px', fontWeight: 600, opacity: 0.7 }}>%</span>
              </span>
              {showWhatIf && (
                <span className="metric-delta" style={{ color: deltaColor }}>
                  ({deltaText})
                </span>
              )}
            </div>
            <div className="gauge-bar-track">
              <div
                className="gauge-bar-fill"
                style={{
                  width: `${currentRisk}%`,
                  background: riskColor,
                  boxShadow: `0 0 8px ${riskColor}`,
                }}
              />
            </div>
          </div>

          {/* Confidence + Sparkline */}
          <div className="metric-card">
            <div className="metric-label" style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Confidence</span>
              <span style={{ color: 'var(--text-muted)', fontSize: '8.5px' }}>Risk trend</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: '8px' }}>
              <div className="metric-value-row">
                <span className="metric-value" style={{ color: 'var(--text-primary)', fontSize: '26px' }}>
                  <span ref={confCounterRef}>{confidence}</span>
                  <span style={{ fontSize: '14px', fontWeight: 600, opacity: 0.6 }}>%</span>
                </span>
              </div>
              {/* Recharts sparkline */}
              {sparkData.length > 0 && (
                <div style={{ width: 70, height: 36, flexShrink: 0 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={sparkData}>
                      <Line
                        type="monotone"
                        dataKey="v"
                        stroke={sparkColor}
                        strokeWidth={1.5}
                        dot={false}
                        isAnimationActive={true}
                        animationDuration={900}
                      />
                      <Tooltip
                        content={() => null}
                        wrapperStyle={{ display: 'none' }}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>
            <div className="gauge-bar-track">
              <div
                className="gauge-bar-fill"
                style={{
                  width: `${confidence}%`,
                  background: 'linear-gradient(90deg, #1A56DB 0%, #00E5FF 100%)',
                  boxShadow: '0 0 8px rgba(0,229,255,0.4)',
                }}
              />
            </div>
          </div>
        </div>

        {/* ── Narrative ── */}
        <div className="brief-narrative">
          <div className="section-label">
            <Activity size={10} style={{ display: 'inline', marginRight: '5px' }} />
            Situation Narrative
          </div>
          <p className="narrative-text">{brief.narrative}</p>

          {showWhatIf && whatIfResult?.narrative_delta && (
            <div className="whatif-narrative">
              <div className="whatif-narrative-label">
                What-If Simulation Trajectory
              </div>
              <p className="whatif-narrative-text">{whatIfResult.narrative_delta}</p>
            </div>
          )}
        </div>

        {/* ── Recommendations ── */}
        <div className="brief-rec">
          <div className="brief-rec-header">
            <Cpu size={11} />
            Recommended Actions
          </div>
          <div className="brief-rec-actions">
            {recItems.length > 0
              ? recItems.map((item, i) => (
                  <div key={i} className="brief-rec-item">{item.trim()}</div>
                ))
              : <div className="brief-rec-item">{brief.recommendation}</div>
            }
          </div>
        </div>

        {/* ── What-If Rainfall Slider ── */}
        <div className="whatif-section">
          <div className="whatif-header">
            <span className="whatif-label">
              <Droplets size={13} />
              What-If: Rainfall Intensity
            </span>
            <span className="whatif-value" id="whatif-val-display">
              {isWhatIfLoading
                ? <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}><span className="spinner" style={{ width: '12px', height: '12px', borderWidth: '1.5px' }} />Simulating…</span>
                : `${rainfallVal}%`
              }
            </span>
          </div>
          <input
            type="range"
            min="0"
            max="100"
            value={rainfallVal}
            onChange={(e) => setRainfallVal(Number(e.target.value))}
            onMouseUp={() => onWhatIfSubmit(rainfallVal)}
            onTouchEnd={() => onWhatIfSubmit(rainfallVal)}
            disabled={isWhatIfLoading}
            className="cyber-slider"
            id="whatif-rainfall-intensity"
            aria-label="What-If Rainfall Intensity"
            style={{
              background: `linear-gradient(to right, ${riskColor} 0%, ${riskColor} ${rainfallVal}%, rgba(255,255,255,0.08) ${rainfallVal}%, rgba(255,255,255,0.08) 100%)`,
            }}
          />
          <div className="slider-labels">
            <span>Dry 0%</span>
            <span>Baseline 50%</span>
            <span>Severe 100%</span>
          </div>
        </div>

        {/* ── Expandable SQL ── */}
        {brief.sources?.sql && (
          <div className="expandable-panel">
            <button
              className="expandable-trigger"
              onClick={() => setSqlExpanded(!sqlExpanded)}
              id="btn-toggle-sql"
              aria-expanded={sqlExpanded}
            >
              <span style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
                <Database size={12} />
                Generated BigQuery SQL
              </span>
              <ChevronDown
                size={14}
                className={`expandable-chevron ${sqlExpanded ? 'open' : ''}`}
              />
            </button>
            {sqlExpanded && (
              <div className="expandable-content">
                <pre className="sql-code">
                  <code>{brief.sources.sql}</code>
                </pre>
              </div>
            )}
          </div>
        )}

        {/* ── Expandable Signals ── */}
        {brief.sources?.signals_used && brief.sources.signals_used.length > 0 && (
          <div className="expandable-panel">
            <button
              className="expandable-trigger"
              onClick={() => setSigExpanded(!sigExpanded)}
              id="btn-toggle-signals"
              aria-expanded={sigExpanded}
            >
              <span style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
                <Activity size={12} />
                Cross-Domain Signals ({brief.sources.signals_used.length})
              </span>
              <ChevronDown
                size={14}
                className={`expandable-chevron ${sigExpanded ? 'open' : ''}`}
              />
            </button>
            {sigExpanded && (
              <div className="expandable-content">
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                  {brief.sources.signals_used.map((sig, i) => {
                    const isFeedback = sig.toLowerCase().includes('feedback') || sig.toLowerCase().includes('citizen');
                    return (
                      <span
                        key={i}
                        className="signal-chip"
                        style={{
                          color: isFeedback ? 'var(--risk-med)' : 'var(--text-secondary)',
                          borderColor: isFeedback ? 'rgba(240,180,41,0.25)' : undefined,
                        }}
                      >
                        {sig}
                        {isFeedback && (
                          <span style={{ fontSize: '8px', opacity: 0.65, marginLeft: '2px' }}>SYNTHETIC</span>
                        )}
                      </span>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        )}

      </div>{/* /brief-inner */}
    </div>
  );
};
