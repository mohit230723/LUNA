import React, { useEffect, useMemo, useRef, useState } from 'react';
import cytoscape from 'cytoscape';
import type { Core, ElementDefinition, StylesheetStyle } from 'cytoscape';
import dagre from 'cytoscape-dagre';
import { getApi } from '../../api';
import type { ForgeSkillDetail } from '../../api/contract';
import './forge.css';

let dagreRegistered = false;
function ensureDagre() {
  if (dagreRegistered) return;
  try {
    cytoscape.use(dagre);
  } catch {
    // already registered by another module
  }
  dagreRegistered = true;
}

// Fallbacks are the Hyperstudio token values the forge.css variables map onto.
const FALLBACK: Record<string, string> = {
  '--forge-node-bg': '#080808',
  '--forge-node-text': '#f3f3f3',
  '--forge-edge': '#474747',
  '--forge-status-done': '#f3f3f3',
};

function cssVar(name: string): string {
  if (typeof window === 'undefined' || typeof getComputedStyle !== 'function') return FALLBACK[name]!;
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v && !v.startsWith('var(') ? v : FALLBACK[name]!;
}

function buildStyle(): StylesheetStyle[] {
  return [
    {
      selector: 'node',
      style: {
        shape: 'round-rectangle',
        width: 120,
        height: 36,
        'background-color': cssVar('--forge-node-bg'),
        'border-width': 1,
        'border-color': cssVar('--forge-edge'),
        color: cssVar('--forge-node-text'),
        label: 'data(label)',
        'text-wrap': 'wrap',
        'text-max-width': '110px',
        'text-valign': 'center',
        'text-halign': 'center',
        'font-family': 'IBM Plex Mono, monospace',
        'font-size': 9,
        'overlay-opacity': 0,
      },
    },
    { selector: 'node.focus', style: { 'border-width': 3, 'border-color': cssVar('--forge-status-done') } },
    {
      selector: 'edge',
      style: {
        width: 1,
        'line-color': cssVar('--forge-edge'),
        'target-arrow-color': cssVar('--forge-edge'),
        'target-arrow-shape': 'triangle',
        'curve-style': 'bezier',
        label: 'data(type)',
        'font-size': 8,
        color: cssVar('--forge-edge'),
      },
    },
  ];
}

const Neighbourhood: React.FC<{ detail: ForgeSkillDetail }> = ({ detail }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const elements = useMemo<ElementDefinition[]>(() => {
    const ids = new Set(detail.neighbourhood.nodes.map((n) => n.id));
    return [
      ...detail.neighbourhood.nodes.map((n) => ({
        data: { id: n.id, label: n.label },
        classes: n.id === detail.id ? 'focus' : n.type,
      })),
      ...detail.neighbourhood.edges
        .filter((e) => ids.has(e.source) && ids.has(e.target))
        .map((e, i) => ({ data: { id: `e${i}`, source: e.source, target: e.target, type: e.type } })),
    ];
  }, [detail]);
  const signature = JSON.stringify(elements);

  useEffect(() => {
    if (!containerRef.current) return;
    ensureDagre();
    const cy: Core = cytoscape({
      container: containerRef.current,
      elements: JSON.parse(signature) as ElementDefinition[],
      style: buildStyle(),
      layout: { name: 'dagre', rankDir: 'LR', nodeSep: 16, rankSep: 50 } as cytoscape.LayoutOptions,
      userZoomingEnabled: true,
      boxSelectionEnabled: false,
      autoungrabify: true,
    });
    return () => {
      cy.destroy();
    };
  }, [signature]);

  return (
    <div
      ref={containerRef}
      className="forge-dag forge-neighbourhood"
      role="img"
      aria-label={`Skill neighbourhood graph: ${detail.neighbourhood.nodes.length} nodes and ${detail.neighbourhood.edges.length} relations around ${detail.name}.`}
    />
  );
};

export interface SkillDetailProps {
  skillId: string;
  onClose: () => void;
}

export const SkillDetail: React.FC<SkillDetailProps> = ({ skillId, onClose }) => {
  const [detail, setDetail] = useState<ForgeSkillDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    setDetail(null);
    setError(null);
    getApi()
      .forgeSkill(skillId)
      .then((d) => live && setDetail(d))
      .catch((e) => live && setError(e instanceof Error ? e.message : 'Could not load the skill.'));
    return () => {
      live = false;
    };
  }, [skillId]);

  return (
    <section className="forge-panel" aria-label="Skill detail">
      <div className="forge-run-head">
        <h2 className="forge-run-prompt">{detail?.name ?? skillId}</h2>
        <button type="button" className="forge-btn" onClick={onClose}>
          Close detail
        </button>
      </div>
      {error && (
        <p className="forge-error" role="alert">
          {error}
        </p>
      )}
      {!detail && !error && <p className="forge-muted">Loading skill…</p>}
      {detail && (
        <>
          <p className="forge-muted">
            {detail.description} · Status: {detail.status.replace('_', ' ')} · Source: {detail.source}
          </p>
          <Neighbourhood detail={detail} />
          <h3 className="forge-panel-title">Sections</h3>
          {detail.sections.length === 0 ? (
            <p className="forge-muted">No sections.</p>
          ) : (
            [...detail.sections]
              .sort((a, b) => a.order - b.order)
              .map((s) => (
                <details key={s.slug} className="forge-section" open>
                  <summary>{s.title}</summary>
                  <p>{s.content}</p>
                </details>
              ))
          )}
          <h3 className="forge-panel-title">Checklist</h3>
          {detail.checklist.length === 0 ? (
            <p className="forge-muted">No checklist items.</p>
          ) : (
            <ul>
              {detail.checklist.map((c) => (
                <li key={c.id}>{c.text}</li>
              ))}
            </ul>
          )}
          {detail.requires.length > 0 && <p className="forge-muted">Requires: {detail.requires.join(', ')}</p>}
          {detail.required_by.length > 0 && (
            <p className="forge-muted">Required by: {detail.required_by.join(', ')}</p>
          )}
        </>
      )}
    </section>
  );
};

export default SkillDetail;
