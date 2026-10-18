import React from 'react';
import type { ForgeAgent } from '../../api/contract';
import { ago } from './format';
import './forge.css';

export const AgentList: React.FC<{ agents: ForgeAgent[]; now: number }> = ({ agents, now }) => {
  return (
    <section className="forge-panel" aria-labelledby="forge-agents-title">
      <h2 id="forge-agents-title" className="forge-panel-title">
        Agents
      </h2>
      {agents.length === 0 ? (
        <p className="forge-muted">No agents connected yet</p>
      ) : (
        <ul className="forge-list" aria-label="Connected agents">
          {agents.map((a) => (
            <li key={a.session_id} className="forge-agent">
              <span>
                <span className={`forge-status-dot${a.connected ? ' is-live' : ''}`} aria-hidden="true" />
                <span className="forge-agent-name">{a.client_name || a.session_id}</span>
                {a.client_version && <span className="forge-muted"> v{a.client_version}</span>}
              </span>
              <span className="forge-status-label" title={`Last seen ${a.last_seen}`}>
                {a.connected ? 'connected' : `idle · ${ago(a.last_seen, now)}`}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
};

export default AgentList;
