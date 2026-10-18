import React, { useState } from 'react';
import { Finding, FindingStatus, Verdict } from '../types';
import { HelpCircle, Filter, Search, ShieldAlert, CheckCircle2 } from 'lucide-react';

interface FindingsTableProps {
  findings: Finding[];
  onSelectCustomer: (customerId: string) => void;
  onExplainCustomer: (customerId: string) => void;
  selectedCustomerId?: string | null;
}

export const FindingsTable: React.FC<FindingsTableProps> = ({
  findings,
  onSelectCustomer,
  onExplainCustomer,
  selectedCustomerId,
}) => {
  const [verdictFilter, setVerdictFilter] = useState<'all' | Verdict>('all');
  const [statusFilter, setStatusFilter] = useState<'all' | FindingStatus>('all');
  const [searchQuery, setSearchQuery] = useState('');

  const filtered = findings.filter((f) => {
    if (verdictFilter !== 'all' && f.verdict !== verdictFilter) return false;
    if (statusFilter !== 'all' && f.status !== statusFilter) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      const matchCid = f.customer_id.toLowerCase().includes(q);
      const matchAid = f.agent_id.toLowerCase().includes(q);
      const matchSkill = f.skill_id.toLowerCase().includes(q);
      if (!matchCid && !matchAid && !matchSkill) return false;
    }
    return true;
  });

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        background: 'var(--bg-surface)',
        borderRight: '1px solid var(--border-default)',
        overflow: 'hidden',
      }}
    >
      {/* Header & Filter Controls */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: '8px',
          padding: '12px 14px',
          borderBottom: '1px solid var(--border-default)',
          background: 'var(--bg-panel)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '13px', fontWeight: 700, letterSpacing: '0.02em' }}>
              AGENT FINDINGS
            </span>
            <span
              style={{
                fontSize: '11px',
                fontFamily: 'var(--font-mono)',
                color: 'var(--text-muted)',
                background: 'var(--bg-subtle)',
                padding: '1px 6px',
                borderRadius: '10px',
              }}
            >
              {findings.length}
            </span>
          </div>

          {/* Quick Filter Tabs */}
          <div style={{ display: 'flex', gap: '4px' }}>
            {(['all', 'suspicious', 'benign'] as const).map((v) => (
              <button
                key={v}
                onClick={() => setVerdictFilter(v)}
                style={{
                  padding: '2px 8px',
                  fontSize: '10px',
                  fontWeight: 600,
                  borderRadius: '4px',
                  cursor: 'pointer',
                  border: '1px solid',
                  borderColor: verdictFilter === v ? 'var(--accent-blue)' : 'transparent',
                  background: verdictFilter === v ? 'rgba(88, 166, 255, 0.15)' : 'transparent',
                  color: verdictFilter === v ? 'var(--accent-blue)' : 'var(--text-secondary)',
                  textTransform: 'uppercase',
                }}
              >
                {v}
              </button>
            ))}
          </div>
        </div>

        {/* Search Bar & Status Filter */}
        <div style={{ display: 'flex', gap: '6px' }}>
          <div
            style={{
              flex: 1,
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              background: 'var(--bg-canvas)',
              border: '1px solid var(--border-default)',
              borderRadius: '5px',
              padding: '4px 8px',
            }}
          >
            <Search size={12} color="var(--text-muted)" />
            <input
              type="text"
              placeholder="Search customer, agent, skill..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                flex: 1,
                background: 'transparent',
                border: 'none',
                color: 'var(--text-primary)',
                fontSize: '11px',
                outline: 'none',
              }}
            />
          </div>

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as any)}
            style={{
              background: 'var(--bg-canvas)',
              border: '1px solid var(--border-default)',
              color: 'var(--text-secondary)',
              fontSize: '11px',
              borderRadius: '5px',
              padding: '0 6px',
              outline: 'none',
              cursor: 'pointer',
            }}
          >
            <option value="all">All Status</option>
            <option value="active">Active Only</option>
            <option value="superseded">Superseded Only</option>
          </select>
        </div>
      </div>

      {/* Table Container */}
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {filtered.length === 0 ? (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              height: '100%',
              color: 'var(--text-muted)',
              fontSize: '12px',
              gap: '6px',
              padding: '20px',
              textAlign: 'center',
            }}
          >
            <span>No findings match current filters.</span>
            <span style={{ fontSize: '11px' }}>Findings will appear here during investigation.</span>
          </div>
        ) : (
          <table
            style={{
              width: '100%',
              borderCollapse: 'collapse',
              fontSize: '12px',
              textAlign: 'left',
            }}
          >
            <thead>
              <tr
                style={{
                  background: 'var(--bg-subtle)',
                  color: 'var(--text-muted)',
                  fontSize: '10px',
                  textTransform: 'uppercase',
                  borderBottom: '1px solid var(--border-default)',
                  position: 'sticky',
                  top: 0,
                  zIndex: 2,
                }}
              >
                <th style={{ padding: '8px 10px' }}>Target</th>
                <th style={{ padding: '8px 10px' }}>Verdict</th>
                <th style={{ padding: '8px 10px' }}>Conf</th>
                <th style={{ padding: '8px 10px' }}>Skill</th>
                <th style={{ padding: '8px 10px' }}>Status</th>
                <th style={{ padding: '8px 10px', textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((f) => {
                const isSelected = selectedCustomerId === f.customer_id;
                const isSuspicious = f.verdict === 'suspicious';
                const isSuperseded = f.status === 'superseded';

                return (
                  <tr
                    key={f.finding_id}
                    onClick={() => onSelectCustomer(f.customer_id)}
                    style={{
                      borderBottom: '1px solid var(--border-subtle)',
                      background: isSelected
                        ? 'rgba(88, 166, 255, 0.08)'
                        : isSuperseded
                        ? 'rgba(139, 148, 158, 0.03)'
                        : 'transparent',
                      opacity: isSuperseded ? 0.6 : 1,
                      cursor: 'pointer',
                      transition: 'background 0.15s ease',
                    }}
                  >
                    {/* Customer */}
                    <td style={{ padding: '8px 10px', fontFamily: 'var(--font-mono)' }}>
                      <span
                        style={{
                          color: isSelected ? 'var(--accent-blue)' : 'var(--text-primary)',
                          fontWeight: 600,
                        }}
                      >
                        {f.customer_id}
                      </span>
                    </td>

                    {/* Verdict */}
                    <td style={{ padding: '8px 10px' }}>
                      <span
                        className={`badge ${
                          isSuspicious ? 'badge-suspicious' : 'badge-benign'
                        }`}
                        style={{ fontSize: '10px', padding: '1px 6px' }}
                      >
                        {isSuspicious ? (
                          <ShieldAlert size={10} />
                        ) : (
                          <CheckCircle2 size={10} />
                        )}
                        {f.verdict}
                      </span>
                    </td>

                    {/* Confidence */}
                    <td style={{ padding: '8px 10px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <div
                          style={{
                            width: '32px',
                            height: '5px',
                            background: 'var(--bg-subtle)',
                            borderRadius: '3px',
                            overflow: 'hidden',
                          }}
                        >
                          <div
                            style={{
                              width: `${Math.round(f.confidence * 100)}%`,
                              height: '100%',
                              background: isSuspicious ? 'var(--verdict-suspicious)' : 'var(--verdict-benign)',
                            }}
                          />
                        </div>
                        <span style={{ fontSize: '11px', fontFamily: 'var(--font-mono)' }}>
                          {(f.confidence * 100).toFixed(0)}%
                        </span>
                      </div>
                    </td>

                    {/* Skill */}
                    <td style={{ padding: '8px 10px', fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-secondary)' }}>
                      {f.skill_id}
                    </td>

                    {/* Status */}
                    <td style={{ padding: '8px 10px' }}>
                      <span
                        className={`badge ${
                          isSuperseded ? 'badge-superseded' : 'badge-blue'
                        }`}
                        style={{ fontSize: '9px', padding: '1px 5px' }}
                      >
                        {f.status}
                      </span>
                    </td>

                    {/* Actions */}
                    <td style={{ padding: '8px 10px', textAlign: 'right' }}>
                      <button
                        className="btn"
                        onClick={(e) => {
                          e.stopPropagation();
                          onExplainCustomer(f.customer_id);
                        }}
                        style={{
                          padding: '3px 8px',
                          fontSize: '11px',
                          background: 'rgba(88, 166, 255, 0.1)',
                          borderColor: 'rgba(88, 166, 255, 0.3)',
                          color: 'var(--accent-blue)',
                        }}
                        title="View 'Why?' Explanation & Provenance"
                      >
                        <HelpCircle size={12} />
                        Why?
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};
