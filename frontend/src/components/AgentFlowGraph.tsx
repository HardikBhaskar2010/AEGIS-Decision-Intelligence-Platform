import React, { useMemo } from 'react';
import {
  ReactFlow,
  Handle,
  Position,
  ConnectionLineType,
} from '@xyflow/react';
import type { Node, Edge } from '@xyflow/react';

// Custom Node Component to fit the Cyberpunk design
interface AgentNodeData {
  label: string;
  state: 'idle' | 'active' | 'done';
  statusText?: string;
  role: string;
}

const AgentNode: React.FC<{ data: AgentNodeData }> = ({ data }) => {
  const stateColorMap = {
    idle: '#6B7280',
    active: '#00E5FF',
    done: '#3DD6A3',
  };

  const glowColor = stateColorMap[data.state] || stateColorMap.idle;

  return (
    <div className={`custom-agent-node ${data.state}`}>
      {/* Handle ports - styled as tiny cyberpunk terminals */}
      <Handle
        type="target"
        position={Position.Top}
        style={{
          background: glowColor,
          borderColor: '#FFFFFF',
          width: '6px',
          height: '6px',
          boxShadow: `0 0 6px ${glowColor}`,
        }}
      />
      
      <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
        <div style={{ fontSize: '9px', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600, letterSpacing: '0.05em' }}>
          {data.role}
        </div>
        <div className="node-title">{data.label}</div>
        <div className="node-status-text" style={{ color: glowColor }}>
          {data.statusText || data.state}
        </div>
      </div>

      <Handle
        type="source"
        position={Position.Bottom}
        style={{
          background: glowColor,
          borderColor: '#FFFFFF',
          width: '6px',
          height: '6px',
          boxShadow: `0 0 6px ${glowColor}`,
        }}
      />
    </div>
  );
};

interface AgentFlowGraphProps {
  // Keyed by agent ID: orchestrator, query, correlation, forecast, narrative
  agentStates: {
    [key: string]: {
      state: 'idle' | 'active' | 'done';
      statusText?: string;
    };
  };
}

export const AgentFlowGraph: React.FC<AgentFlowGraphProps> = ({ agentStates }) => {
  const nodeTypes = useMemo(() => ({ agentNode: AgentNode }), []);

  // Compute graph nodes based on active states
  const nodes: Node[] = useMemo(() => {
    return [
      {
        id: 'orchestrator',
        type: 'agentNode',
        position: { x: 230, y: 15 },
        data: {
          label: 'Orchestrator',
          role: 'Coordinator (Gemini 3 Flash)',
          state: agentStates.orchestrator?.state || 'idle',
          statusText: agentStates.orchestrator?.statusText || 'Standby',
        },
      },
      {
        id: 'query',
        type: 'agentNode',
        position: { x: 30, y: 95 },
        data: {
          label: 'Query Agent',
          role: 'SQL Engine (Gemini 3 Flash)',
          state: agentStates.query?.state || 'idle',
          statusText: agentStates.query?.statusText || 'Standby',
        },
      },
      {
        id: 'correlation',
        type: 'agentNode',
        position: { x: 230, y: 95 },
        data: {
          label: 'Correlation Agent',
          role: 'Anomaly Detector (Gemini 3 Flash)',
          state: agentStates.correlation?.state || 'idle',
          statusText: agentStates.correlation?.statusText || 'Standby',
        },
      },
      {
        id: 'forecast',
        type: 'agentNode',
        position: { x: 430, y: 95 },
        data: {
          label: 'Forecast Agent',
          role: 'Predictive Modeler (Gemini 3 Flash)',
          state: agentStates.forecast?.state || 'idle',
          statusText: agentStates.forecast?.statusText || 'Standby',
        },
      },
      {
        id: 'narrative',
        type: 'agentNode',
        position: { x: 230, y: 175 },
        data: {
          label: 'Narrative Agent',
          role: 'Synthesizer (Gemini 3.1 Pro)',
          state: agentStates.narrative?.state || 'idle',
          statusText: agentStates.narrative?.statusText || 'Standby',
        },
      },
    ];
  }, [agentStates]);

  // Compute edges with active styling
  const edges: Edge[] = useMemo(() => {
    // Helper to check if an edge is active
    const isEdgeActive = (source: string, target: string) => {
      // Edge is active if source is done or active, and target is active
      const sourceState = agentStates[source]?.state;
      const targetState = agentStates[target]?.state;
      return (sourceState === 'active' || sourceState === 'done') && targetState === 'active';
    };

    const isEdgeDone = (source: string, target: string) => {
      return agentStates[source]?.state === 'done' && agentStates[target]?.state === 'done';
    };

    const getEdgeClass = (source: string, target: string) => {
      if (isEdgeActive(source, target)) return 'active';
      if (isEdgeDone(source, target)) return 'done';
      return '';
    };

    return [
      // Control flow from Orchestrator to Specialists
      {
        id: 'o-q',
        source: 'orchestrator',
        target: 'query',
        animated: isEdgeActive('orchestrator', 'query'),
        className: getEdgeClass('orchestrator', 'query'),
      },
      {
        id: 'o-c',
        source: 'orchestrator',
        target: 'correlation',
        animated: isEdgeActive('orchestrator', 'correlation'),
        className: getEdgeClass('orchestrator', 'correlation'),
      },
      {
        id: 'o-f',
        source: 'orchestrator',
        target: 'forecast',
        animated: isEdgeActive('orchestrator', 'forecast'),
        className: getEdgeClass('orchestrator', 'forecast'),
      },
      {
        id: 'o-n',
        source: 'orchestrator',
        target: 'narrative',
        animated: isEdgeActive('orchestrator', 'narrative'),
        className: getEdgeClass('orchestrator', 'narrative'),
      },
      // Data Pipeline flows
      {
        id: 'q-c',
        source: 'query',
        target: 'correlation',
        animated: isEdgeActive('query', 'correlation'),
        className: getEdgeClass('query', 'correlation'),
      },
      {
        id: 'c-f',
        source: 'correlation',
        target: 'forecast',
        animated: isEdgeActive('correlation', 'forecast'),
        className: getEdgeClass('correlation', 'forecast'),
      },
      {
        id: 'f-n',
        source: 'forecast',
        target: 'narrative',
        animated: isEdgeActive('forecast', 'narrative'),
        className: getEdgeClass('forecast', 'narrative'),
      },
      {
        id: 'q-n',
        source: 'query',
        target: 'narrative',
        animated: isEdgeActive('query', 'narrative'),
        className: getEdgeClass('query', 'narrative'),
      },
    ];
  }, [agentStates]);

  return (
    <div className="react-flow-container" id="agent-graph-viewport">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        connectionLineType={ConnectionLineType.SmoothStep}
        fitView
        fitViewOptions={{ padding: 0.15 }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        panOnDrag={false}
        zoomOnScroll={false}
        zoomOnPinch={false}
        zoomOnDoubleClick={false}
        preventScrolling={true}
        style={{ width: '100%', height: '100%' }}
      />
    </div>
  );
};
