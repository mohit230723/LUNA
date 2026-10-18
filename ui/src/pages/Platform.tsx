import React, { useEffect, useRef } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { PageShell } from '../components/layout/PageShell';
import { AgentsTab } from '../components/forge/AgentsTab';
import CaseWorkspace from './platform/CaseWorkspace';
import '../components/forge/forge.css';

const TABS = [
  { id: 'agents', label: 'Agents' },
  { id: 'cases', label: 'Cases' },
  { id: 'skills', label: 'Skills' },
] as const;

type TabId = (typeof TABS)[number]['id'];

const isTab = (v: string | null): v is TabId => TABS.some((t) => t.id === v);

export const Platform: React.FC = () => {
  const { conversationId } = useParams<{ conversationId?: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const raw = searchParams.get('tab');
  // Case links (/platform/:id, ?prompt=) predate the tabs, so they keep landing on Cases.
  const fallback: TabId = conversationId || searchParams.get('prompt') ? 'cases' : 'agents';
  const active: TabId = isTab(raw) ? raw : fallback;
  const tabRefs = useRef<Record<string, HTMLButtonElement | null>>({});

  useEffect(() => {
    // The Cases tab keeps its own "Case Workspace" title.
    if (active !== 'cases') document.title = 'Platform · LUNA OS';
  }, [active]);

  const select = (id: TabId, focus = false) => {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.set('tab', id);
        return next;
      },
      { replace: true }
    );
    if (focus) tabRefs.current[id]?.focus();
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLButtonElement>) => {
    const idx = TABS.findIndex((t) => t.id === active);
    let next = -1;
    if (e.key === 'ArrowRight') next = (idx + 1) % TABS.length;
    else if (e.key === 'ArrowLeft') next = (idx - 1 + TABS.length) % TABS.length;
    else if (e.key === 'Home') next = 0;
    else if (e.key === 'End') next = TABS.length - 1;
    if (next < 0) return;
    e.preventDefault();
    select(TABS[next]!.id, true);
  };

  return (
    <PageShell showFooter={false} compactNav={true}>
      <h1 className="visually-hidden">Platform</h1>
      <div className="platform-tabs-shell">
        <div className="platform-tablist" role="tablist" aria-label="Platform sections">
          {TABS.map((t) => {
            const selected = t.id === active;
            return (
              <button
                key={t.id}
                ref={(el) => {
                  tabRefs.current[t.id] = el;
                }}
                type="button"
                role="tab"
                id={`platform-tab-${t.id}`}
                aria-selected={selected}
                aria-controls={`platform-panel-${t.id}`}
                tabIndex={selected ? 0 : -1}
                className="platform-tab"
                onClick={() => select(t.id)}
                onKeyDown={onKeyDown}
              >
                {t.label}
              </button>
            );
          })}
        </div>
        <div
          className="platform-tabpanel"
          role="tabpanel"
          id={`platform-panel-${active}`}
          aria-labelledby={`platform-tab-${active}`}
        >
          {active === 'agents' && <AgentsTab />}
          {active === 'cases' && <CaseWorkspace />}
          {active === 'skills' && (
            <p className="platform-placeholder">The skill library is coming to this tab.</p>
          )}
        </div>
      </div>
    </PageShell>
  );
};

export default Platform;
