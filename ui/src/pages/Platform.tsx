import React, { useEffect, useState, useReducer } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { PageShell } from '../components/layout/PageShell';
import { Sidebar } from '../components/chat/Sidebar';
import { Thread } from '../components/chat/Thread';
import { DetailsDrawer } from '../components/chat/DetailsDrawer';
import { getApi } from '../api';
import { conversationReducer, initialConversationState } from '../state/conversationReducer';
import { useRun } from '../state/hooks';
import type { ConversationSummary, SendOptions, ActionResult, FileNode } from '../api/contract';
import styles from './Platform.module.css';

export const Platform: React.FC = () => {
  const { conversationId } = useParams<{ conversationId?: string }>();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const promptParam = searchParams.get('prompt') || '';

  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | undefined>(conversationId);
  const [activeRunId, setActiveRunId] = useState<string | undefined>(undefined);

  // Conversation state
  const [convState, dispatchConv] = useReducer(conversationReducer, initialConversationState);

  // Run pipeline subscription
  const { runState, connectionState } = useRun(activeRunId);

  // Details drawer state
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [detailsTab, setDetailsTab] = useState<'skills' | 'agents' | 'findings' | 'why' | 'files'>('skills');
  const [whyTarget, setWhyTarget] = useState<string | undefined>(undefined);
  const [selectedFile, setSelectedFile] = useState<string | undefined>(undefined);
  const [filePreview, setFilePreview] = useState<{ path: string; content: string; truncated: boolean } | undefined>(undefined);
  const [artifacts, setArtifacts] = useState<FileNode[]>([]);

  useEffect(() => {
    document.title = 'Platform · LUNA OS';
  }, []);

  // Sync activeConvId with route param
  useEffect(() => {
    setActiveConvId(conversationId);
  }, [conversationId]);

  // Load conversation list
  const loadConversations = async () => {
    try {
      const api = getApi();
      const list = await api.listConversations();
      setConversations(list);
    } catch {
      // offline / mock handling
    }
  };

  useEffect(() => {
    loadConversations();
  }, []);

  // Load active conversation messages
  useEffect(() => {
    if (!activeConvId) {
      dispatchConv({
        type: 'LOAD_CONVERSATION',
        conversation: { id: '', title: '', messages: [] },
      });
      return;
    }

    const loadConv = async () => {
      try {
        const api = getApi();
        const conv = await api.getConversation(activeConvId);
        dispatchConv({ type: 'LOAD_CONVERSATION', conversation: conv });
        // Find latest streaming or active run id if any
        const lastMsg = conv.messages[conv.messages.length - 1];
        if (lastMsg && lastMsg.run_id && lastMsg.status === 'streaming') {
          setActiveRunId(lastMsg.run_id);
        }
      } catch {
        // Handle error
      }
    };
    loadConv();
  }, [activeConvId]);

  // Pass incoming run events from useRun to conversationReducer
  useEffect(() => {
    if (!runState.events || runState.events.length === 0) return;
    const latestEvent = runState.events[runState.events.length - 1];
    if (latestEvent) {
      dispatchConv({ type: 'RUN_EVENT', event: latestEvent });
    }
  }, [runState.events]);

  // Load artifact preview when file is selected
  useEffect(() => {
    if (!activeRunId || !selectedFile) return;
    const fetchFile = async () => {
      try {
        const api = getApi();
        const res = await api.getArtifactFile(activeRunId, selectedFile);
        setFilePreview(res);
      } catch {
        //
      }
    };
    fetchFile();
  }, [activeRunId, selectedFile]);

  // Load artifacts tree
  useEffect(() => {
    if (!activeRunId) return;
    const fetchArtifacts = async () => {
      try {
        const api = getApi();
        const res = await api.getArtifacts(activeRunId);
        setArtifacts(res);
      } catch {
        //
      }
    };
    fetchArtifacts();
  }, [activeRunId]);

  const handleNewChat = () => {
    setActiveRunId(undefined);
    dispatchConv({
      type: 'LOAD_CONVERSATION',
      conversation: { id: '', title: '', messages: [] },
    });
    navigate('/platform');
  };

  const handleSend = async (content: string, options: SendOptions) => {
    const api = getApi();
    let currentId = activeConvId;

    if (!currentId) {
      const created = await api.createConversation();
      currentId = created.id;
      setActiveConvId(currentId);
    }

    try {
      const { run_id } = await api.sendMessage(currentId, { content, options });
      setActiveRunId(run_id);
      const updatedConv = await api.getConversation(currentId);
      dispatchConv({ type: 'LOAD_CONVERSATION', conversation: updatedConv });
      loadConversations();
      navigate(`/platform/${currentId}`, { replace: true });
    } catch {
      // Error handling
    }
  };

  const handleCancel = async () => {
    if (!activeRunId) return;
    try {
      const api = getApi();
      await api.cancelRun(activeRunId);
    } catch {
      //
    }
  };

  const handleAnswer = async (choice: string) => {
    if (!activeRunId) return;
    try {
      const api = getApi();
      await api.answerRun(activeRunId, choice);
    } catch {
      //
    }
  };

  const handleApproveAction = async (actionId: string, approver: string): Promise<ActionResult> => {
    if (!activeRunId) return { ok: false };
    const api = getApi();
    const result = await api.approveAction(activeRunId, actionId, approver);
    // Update local action state
    dispatchConv({
      type: 'RUN_EVENT',
      event: {
        run_id: activeRunId,
        seq: 99999,
        ts: new Date().toISOString(),
        type: 'executed',
        data: { action_id: actionId, approver, result },
      },
    });
    return result;
  };

  const handleRejectAction = async (actionId: string, approver: string, reason: string): Promise<void> => {
    if (!activeRunId) return;
    const api = getApi();
    await api.rejectAction(activeRunId, actionId, approver, reason);
  };

  const handleViewTrace = (runId?: string) => {
    const targetRun = runId || activeRunId;
    if (activeConvId && targetRun) {
      navigate(`/platform/${activeConvId}/trace/${targetRun}`);
    }
  };

  const handleOpenWhy = (target?: string) => {
    setWhyTarget(target);
    setDetailsTab('why');
    setDetailsOpen(true);
  };

  const handleCidClick = (cid: string) => {
    setWhyTarget(cid);
    setDetailsTab('why');
    setDetailsOpen(true);
  };

  const handleSelectFile = (path: string) => {
    setSelectedFile(path);
    setDetailsTab('files');
    setDetailsOpen(true);
  };

  // Collect data for DetailsDrawer from current messages
  const lastAssistantMsg = convState?.conversation?.messages
    ?.filter((m) => m.role === 'assistant')
    ?.pop();

  const skillsData =
    lastAssistantMsg?.blocks.find((b) => b.type === 'skills')?.data.assignments || [];
  const findingsData =
    lastAssistantMsg?.blocks.find((b) => b.type === 'findings')?.data.items || [];
  const agentsData = runState.agents;

  // MiniGraph preview elements for answer block
  const previewData = lastAssistantMsg?.blocks.find((b) => b.type === 'trace_preview')?.data;
  const previewElements = previewData
    ? {
        nodes: previewData.path_node_ids.map((id) => ({
          data: { id, label: id, on_path: true, type: id.startsWith('cust') ? 'Customer' : 'Phone' },
        })),
        edges: previewData.path_node_ids.slice(0, -1).map((id, i) => ({
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
      <h1 className="visually-hidden">Platform</h1>
      <div className={styles.shell}>
        {/* Left Sidebar */}
        <Sidebar
          conversations={conversations}
          activeId={activeConvId}
          onNewChat={handleNewChat}
        />

        {/* Center Thread */}
        <Thread
          messages={convState.conversation?.messages || []}
          activeStages={runState.stages}
          activeAgents={agentsData}
          previewElements={previewElements}
          isStreaming={runState.status === 'streaming'}
          connectionState={connectionState}
          composerInitialPrompt={promptParam}
          onSend={handleSend}
          onCancel={handleCancel}
          onViewTrace={handleViewTrace}
          onOpenWhy={handleOpenWhy}
          onCidClick={handleCidClick}
          onAnswer={handleAnswer}
          onApproveAction={handleApproveAction}
          onRejectAction={handleRejectAction}
          onSelectFile={handleSelectFile}
          filePreview={filePreview}
        />

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
          filesData={artifacts}
          onFocusNode={handleCidClick}
          onSelectFile={handleSelectFile}
        />
      </div>
    </PageShell>
  );
};
