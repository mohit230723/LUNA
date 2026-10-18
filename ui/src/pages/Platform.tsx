import React, { useEffect, useState, useReducer, useCallback, useRef } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { PageShell } from '../components/layout/PageShell';
import { Sidebar } from '../components/chat/Sidebar';
import { Thread } from '../components/chat/Thread';
import { DetailsDrawer } from '../components/chat/DetailsDrawer';
import { IngestScreen } from '../components/ingest/IngestScreen';
import { BuildingScreen } from '../components/ingest/BuildingScreen';
import { LlmBlockerCard } from '../components/ingest/LlmBlockerCard';
import { getApi } from '../api';
import { conversationReducer, initialConversationState } from '../state/conversationReducer';
import { useRun } from '../state/hooks';
import type {
  CaseDetail,
  CaseSummary,
  SendOptions,
  Health,
  BuildEvent,
  Message,
} from '../api/contract';
import styles from './Platform.module.css';

export const Platform: React.FC = () => {
  const { conversationId } = useParams<{ conversationId?: string }>();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const promptParam = searchParams.get('prompt') || '';

  // LLM health state
  const [health, setHealth] = useState<Health | null>(null);
  const [isHealthChecked, setIsHealthChecked] = useState(false);

  // Case & conversations state
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [caseDetail, setCaseDetail] = useState<CaseDetail | null>(null);
  const [, setCaseLoading] = useState(false);

  // Build state
  const [activeBuildId, setActiveBuildId] = useState<string | null>(null);
  const [buildEvents, setBuildEvents] = useState<BuildEvent[]>([]);
  const [isBuildFailed, setIsBuildFailed] = useState(false);
  const [buildError, setBuildError] = useState<string>('');

  // Investigation run state
  const [activeRunId, setActiveRunId] = useState<string | undefined>(undefined);
  const [convState, dispatchConv] = useReducer(conversationReducer, initialConversationState);
  const { runState, connectionState } = useRun(activeRunId);

  // Suggestions
  const [suggestions, setSuggestions] = useState<string[]>([]);

  // Details drawer state
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [detailsTab, setDetailsTab] = useState<'skills' | 'agents' | 'findings' | 'why'>('skills');
  const [whyTarget, setWhyTarget] = useState<string | undefined>(undefined);

  // Prefill prompt logic
  const [initialPrompt, setInitialPrompt] = useState<string>('');

  useEffect(() => {
    document.title = 'Case Workspace · LUNA OS';
  }, []);

  // 1. Health check
  const fetchHealth = useCallback(async () => {
    try {
      const api = getApi();
      const h = await api.health();
      setHealth(h);
    } catch {
      setHealth({
        status: 'degraded',
        falkordb: false,
        llm: { provider: 'unknown', model: 'unknown', remote: false, reachable: false },
      });
    } finally {
      setIsHealthChecked(true);
    }
  }, []);

  useEffect(() => {
    fetchHealth();
  }, [fetchHealth]);

  // 2. Load case list
  const loadCaseList = useCallback(async () => {
    try {
      const api = getApi();
      const list = await api.listConversations();
      setCases(list);
    } catch {
      setCases([]);
    }
  }, []);

  useEffect(() => {
    loadCaseList();
  }, [loadCaseList]);

  // 3. Load active case detail
  const loadCase = useCallback(async (id: string) => {
    setCaseLoading(true);
    try {
      const api = getApi();
      const detail = await api.getCase(id);
      setCaseDetail(detail);

      // Load suggestions if case is ready
      if (detail.status === 'ready') {
        try {
          const suggs = await api.getSuggestions(id);
          setSuggestions(suggs);
        } catch {
          setSuggestions([]);
        }
      }

      // Sync messages
      dispatchConv({
        type: 'LOAD_CONVERSATION',
        conversation: { id: detail.id, title: detail.title, messages: detail.messages || [] },
      });

      // Find latest active run id if any
      const lastMsg = detail.messages && detail.messages[detail.messages.length - 1];
      if (lastMsg && lastMsg.run_id) {
        setActiveRunId(lastMsg.run_id);
      }
    } catch {
      setCaseDetail(null);
    } finally {
      setCaseLoading(false);
    }
  }, []);

  useEffect(() => {
    if (conversationId) {
      loadCase(conversationId);
    } else {
      setCaseDetail(null);
      setActiveRunId(undefined);
      dispatchConv({
        type: 'LOAD_CONVERSATION',
        conversation: { id: '', title: '', messages: [] },
      });
    }
  }, [conversationId, loadCase]);

  // 4. Handle saved prompt from query param
  useEffect(() => {
    if (promptParam) {
      sessionStorage.setItem('luna.savedPrompt', promptParam);
    }
    const saved = sessionStorage.getItem('luna.savedPrompt');
    if (saved && caseDetail?.status === 'ready') {
      setInitialPrompt(saved);
      sessionStorage.removeItem('luna.savedPrompt');
    }
  }, [promptParam, caseDetail?.status]);

  // 5. Pass incoming run events to conversation reducer
  useEffect(() => {
    if (!runState.events || runState.events.length === 0) return;
    const latestEvent = runState.events[runState.events.length - 1];
    if (latestEvent) {
      dispatchConv({ type: 'RUN_EVENT', event: latestEvent });
    }
  }, [runState.events]);

  // 6. Build subscription effect
  const buildUnsubRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    if (!activeBuildId || !conversationId) return;

    const api = getApi();
    setIsBuildFailed(false);
    setBuildError('');

    const unsub = api.subscribeBuild(conversationId, activeBuildId, {
      onEvent: (event: BuildEvent) => {
        setBuildEvents((prev) => [...prev, event]);
        if (event.type === 'completed') {
          setActiveBuildId(null);
          loadCase(conversationId);
          loadCaseList();
        } else if (event.type === 'failed') {
          setIsBuildFailed(true);
          const errData = event.data as Record<string, any>;
          setBuildError(errData?.detail || errData?.error || 'Build failed.');
        } else if (event.type === 'cancelled') {
          setActiveBuildId(null);
          loadCase(conversationId);
        }
      },
      onState: () => {},
    });

    buildUnsubRef.current = unsub;
    return () => {
      if (buildUnsubRef.current) {
        buildUnsubRef.current();
        buildUnsubRef.current = null;
      }
    };
  }, [activeBuildId, conversationId, loadCase, loadCaseList]);

  // INGEST ACTIONS
  const handleAddText = async (name: string, text: string) => {
    const api = getApi();
    let targetId = conversationId || '';
    if (!targetId) {
      const created = await api.createConversation();
      targetId = created.id;
      navigate(`/platform/${targetId}`, { replace: true });
    }
    await api.uploadText(targetId, { name, text });
    await loadCase(targetId);
    await loadCaseList();
  };

  const handleUploadFiles = async (files: File[]) => {
    const api = getApi();
    let targetId = conversationId || '';
    if (!targetId) {
      const created = await api.createConversation();
      targetId = created.id;
      navigate(`/platform/${targetId}`, { replace: true });
    }
    await api.uploadFiles(targetId, files);
    await loadCase(targetId);
    await loadCaseList();
  };

  const handleRemoveSource = async (sourceId: string) => {
    if (!conversationId) return;
    const api = getApi();
    await api.removeSource(conversationId, sourceId);
    await loadCase(conversationId);
    await loadCaseList();
  };

  const handleStartBuild = async (acknowledgeRemote: boolean) => {
    if (!conversationId) return;
    const api = getApi();
    setBuildEvents([]);
    setIsBuildFailed(false);
    setBuildError('');
    try {
      const { build_id } = await api.startBuild(conversationId, { acknowledge_remote: acknowledgeRemote });
      setActiveBuildId(build_id);
    } catch (err: any) {
      setIsBuildFailed(true);
      setBuildError(err?.message || 'Failed to start build.');
    }
  };

  const handleCancelBuild = async () => {
    if (!conversationId || !activeBuildId) return;
    const api = getApi();
    await api.cancelBuild(conversationId, activeBuildId);
    setActiveBuildId(null);
    loadCase(conversationId);
  };

  const handleRetryBuild = () => {
    handleStartBuild(true);
  };

  const handleBackToInputs = () => {
    setIsBuildFailed(false);
    setActiveBuildId(null);
    if (conversationId) loadCase(conversationId);
  };

  // CHAT ACTIONS
  const handleSend = async (content: string, options: SendOptions) => {
    if (!conversationId) return;
    const api = getApi();
    try {
      const { run_id } = await api.sendMessage(conversationId, { content, options });
      setActiveRunId(run_id);
      await loadCase(conversationId);
      await loadCaseList();
    } catch (err: any) {
      // Handled in UI
    }
  };

  const handleCancelRun = async () => {
    if (!activeRunId) return;
    const api = getApi();
    await api.cancelRun(activeRunId);
  };

  const handleAnswerRun = async (choice: string) => {
    if (!activeRunId) return;
    const api = getApi();
    await api.answerRun(activeRunId, choice);
    if (conversationId) loadCase(conversationId);
  };

  const handleNewCase = () => {
    setActiveRunId(undefined);
    setCaseDetail(null);
    navigate('/platform');
  };

  const handleDeleteCase = async (caseId: string) => {
    const api = getApi();
    await api.deleteConversation(caseId);
    await loadCaseList();
    if (conversationId === caseId) {
      handleNewCase();
    }
  };

  const handleViewTrace = (runId?: string) => {
    const targetRun = runId || activeRunId;
    if (conversationId && targetRun) {
      navigate(`/platform/${conversationId}/trace/${targetRun}`);
    }
  };

  const handleOpenWhy = (target?: string) => {
    setWhyTarget(target);
    setDetailsTab('why');
    setDetailsOpen(true);
  };

  const handleCidClick = (cid: string) => {
    const targetRun = activeRunId;
    if (conversationId && targetRun) {
      navigate(`/platform/${conversationId}/trace/${targetRun}?focus=${cid}`);
    } else {
      handleOpenWhy(cid);
    }
  };

  // Derived state
  const isLlmUnreachable = isHealthChecked && (!health?.llm || !health.llm.reachable);
  const caseStatus = caseDetail?.status || 'draft';
  const isBuilding = caseStatus === 'building' || Boolean(activeBuildId);
  const isReady = caseStatus === 'ready';

  // Details drawer info
  const lastAssistantMsg = convState.conversation?.messages
    ?.filter((m) => m.role === 'assistant')
    ?.pop();

  const skillsData =
    lastAssistantMsg?.blocks.find((b) => b.type === 'skills')?.data.assignments || [];
  const findingsData =
    lastAssistantMsg?.blocks.find((b) => b.type === 'findings')?.data.items || [];
  const agentsData = runState.agents;

  // Assembly of messages for Thread
  const threadMessages: Message[] = [];
  if (isReady && caseDetail?.stats) {
    // Synthetic first message showing graph summary
    threadMessages.push({
      id: 'summary_msg',
      role: 'assistant',
      created_at: new Date().toISOString(),
      blocks: [{ type: 'graph_summary', data: caseDetail.stats }],
    });
  }
  if (convState.conversation?.messages) {
    threadMessages.push(...convState.conversation.messages);
  }

  // MiniGraph preview elements for AnswerBlock
  const previewData = lastAssistantMsg?.blocks.find((b) => b.type === 'trace_preview')?.data;
  const previewElements = previewData
    ? {
        nodes: (previewData.path_node_ids || []).map((id: string) => ({
          data: { id, label: id, on_path: true, type: 'Entity' },
        })),
        edges: (previewData.path_node_ids || []).slice(0, -1).map((id: string, i: number) => ({
          data: {
            id: `pe_${i}`,
            source: id,
            target: previewData.path_node_ids[i + 1]!,
            on_path: true,
          },
        })),
      }
    : undefined;

  return (
    <PageShell showFooter={false} compactNav={true}>
      <h1 className="visually-hidden">LUNA Case Workspace</h1>
      <div className={styles.shell}>
        {/* Left Sidebar */}
        <Sidebar
          cases={cases}
          activeId={conversationId}
          onNewCase={handleNewCase}
          onDeleteCase={handleDeleteCase}
          llmInfo={health?.llm}
        />

        {/* Center Workspace */}
        <main className={styles.mainArea}>
          {isLlmUnreachable ? (
            <LlmBlockerCard llmInfo={health?.llm} onCheckAgain={fetchHealth} />
          ) : isBuilding ? (
            <BuildingScreen
              events={buildEvents}
              buildError={buildError || caseDetail?.build_error}
              isFailed={isBuildFailed}
              onCancel={handleCancelBuild}
              onRetry={handleRetryBuild}
              onBackToInputs={handleBackToInputs}
            />
          ) : isReady ? (
            <Thread
              messages={threadMessages}
              graphStats={caseDetail?.stats}
              suggestions={suggestions}
              activeStages={runState.stages}
              activeAgents={agentsData}
              previewElements={previewElements}
              isStreaming={runState.status === 'streaming'}
              connectionState={connectionState}
              composerInitialPrompt={initialPrompt}
              onSend={handleSend}
              onCancel={handleCancelRun}
              onAddSource={() => {
                if (caseDetail) {
                  setCaseDetail({ ...caseDetail, status: 'stale' });
                }
              }}
              onViewTrace={handleViewTrace}
              onOpenWhy={handleOpenWhy}
              onCidClick={handleCidClick}
              onAnswer={handleAnswerRun}
            />
          ) : (
            <IngestScreen
              caseDetail={caseDetail}
              llmInfo={health?.llm}
              onAddText={handleAddText}
              onUploadFiles={handleUploadFiles}
              onRemoveSource={handleRemoveSource}
              onStartBuild={handleStartBuild}
            />
          )}
        </main>

        {/* Right Details Drawer */}
        <DetailsDrawer
          isOpen={detailsOpen}
          onClose={() => setDetailsOpen(false)}
          runId={activeRunId}
          initialTab={detailsTab}
          whyTarget={whyTarget}
          skillsData={skillsData}
          agentsData={agentsData}
          findingsData={findingsData}
          onFocusNode={handleCidClick}
        />
      </div>
    </PageShell>
  );
};
