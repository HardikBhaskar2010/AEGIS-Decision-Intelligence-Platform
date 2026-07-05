import React from 'react';
import { History, X, Trash2, Clock } from 'lucide-react';
import type { SituationBrief } from './types';

interface HistoryConsoleProps {
  isOpen: boolean;
  onToggle: () => void;
  history: SituationBrief[];
  activeBriefId: string | null;
  onSelectBrief: (brief: SituationBrief) => void;
  onClearHistory: () => void;
}

export const HistoryConsole: React.FC<HistoryConsoleProps> = ({
  isOpen,
  onToggle,
  history,
  activeBriefId,
  onSelectBrief,
  onClearHistory,
}) => {
  const getRiskClass = (score: number) => {
    if (score < 0.35) return 'low';
    if (score < 0.70) return 'med';
    return 'high';
  };

  const getRiskText = (score: number) => {
    if (score < 0.35) return 'LOW';
    if (score < 0.70) return 'MED';
    return 'HIGH';
  };

  return (
    <div className={`history-sidebar-container ${isOpen ? 'open' : ''}`} id="history-console-sidebar">
      {/* Sidebar trigger */}
      <button 
        className="history-sidebar-trigger" 
        onClick={onToggle}
        title="Toggle Session History"
        aria-label="Toggle Session History"
        id="btn-toggle-history"
      >
        {isOpen ? <X size={20} /> : <History size={20} />}
      </button>

      {/* Header */}
      <div className="history-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <History size={18} color="var(--accent-cyan)" />
          <h3 style={{ fontSize: '15px' }}>SESSION ROOM</h3>
        </div>
        {history.length > 0 && (
          <button
            onClick={onClearHistory}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--text-muted)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '4px',
              transition: 'color var(--transition-fast)',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--accent-high)')}
            onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text-muted)')}
            title="Clear History"
            aria-label="Clear History"
            id="btn-clear-history"
          >
            <Trash2 size={16} />
          </button>
        )}
      </div>

      {/* List */}
      <div className="history-list">
        {history.length === 0 ? (
          <div className="history-empty">
            <Clock size={36} className="history-empty-icon" />
            <p style={{ fontSize: '12px' }}>No session logs saved.</p>
          </div>
        ) : (
          history.map((brief) => {
            const riskClass = getRiskClass(brief.risk_score);
            const isActive = activeBriefId === brief.brief_id;
            
            return (
              <button
                key={brief.brief_id}
                className={`history-item ${isActive ? 'active' : ''}`}
                onClick={() => onSelectBrief(brief)}
                id={`history-item-${brief.brief_id}`}
                style={{ background: 'rgba(18, 22, 31, 0.5)', border: '1px solid var(--border-color)', width: '100%' }}
              >
                <div className="history-item-question">
                  Sector: {brief.sector_id}
                </div>
                <div className="history-item-meta">
                  <span className={`history-item-risk ${riskClass}`}>
                    Risk: {getRiskText(brief.risk_score)} ({Math.round(brief.risk_score * 100)}%)
                  </span>
                  <span>
                    {brief.generated_at ? new Date(brief.generated_at).toLocaleTimeString() : 'N/A'}
                  </span>
                </div>
              </button>
            );
          })
        )}
      </div>
    </div>
  );
};
