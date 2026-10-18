import { Block, Conversation, Message, RunEvent } from '../api/contract';
import { runReducer } from './runReducer';

export interface ConversationState {
  conversation: Conversation | null;
  activeRunId: string | null;
  isLoading: boolean;
  error: string | null;
}

export const INITIAL_CONVERSATION_STATE: ConversationState = {
  conversation: null,
  activeRunId: null,
  isLoading: false,
  error: null,
};

export type ConversationAction =
  | { type: 'LOAD_CONVERSATION'; conversation: Conversation }
  | { type: 'SEND_OPTIMISTIC'; userMessage: Message; assistantPlaceholder: Message }
  | { type: 'MESSAGE_CONFIRMED'; placeholderId: string; messageId: string; runId: string }
  | { type: 'RUN_EVENT'; event: RunEvent }
  | { type: 'SET_STATUS'; status: Message['status']; runId?: string }
  | { type: 'SET_ERROR'; error: string | null }
  | { type: 'SET_LOADING'; isLoading: boolean };

export function conversationReducer(
  state: ConversationState,
  action: ConversationAction
): ConversationState {
  switch (action.type) {
    case 'LOAD_CONVERSATION':
      return {
        ...state,
        conversation: action.conversation,
        isLoading: false,
        error: null,
      };

    case 'SET_LOADING':
      return { ...state, isLoading: action.isLoading };

    case 'SET_ERROR':
      return { ...state, error: action.error };

    case 'SEND_OPTIMISTIC': {
      if (!state.conversation) return state;
      const newMessages = [
        ...state.conversation.messages,
        action.userMessage,
        action.assistantPlaceholder,
      ];
      return {
        ...state,
        conversation: {
          ...state.conversation,
          messages: newMessages,
        },
        activeRunId: action.assistantPlaceholder.run_id || null,
      };
    }

    case 'MESSAGE_CONFIRMED': {
      if (!state.conversation) return state;
      const newMessages = state.conversation.messages.map((m) =>
        m.id === action.placeholderId
          ? { ...m, id: action.messageId, run_id: action.runId }
          : m
      );
      return {
        ...state,
        conversation: {
          ...state.conversation,
          messages: newMessages,
        },
        activeRunId: action.runId,
      };
    }

    case 'RUN_EVENT': {
      if (!state.conversation) return state;
      const { event } = action;

      // Find the assistant message associated with this run_id
      const msgIndex = state.conversation.messages.findIndex(
        (m) => m.run_id === event.run_id
      );
      if (msgIndex === -1) return state;

      const targetMsg = state.conversation.messages[msgIndex]!;

      // Synthetic run state to process this single event through runReducer
      const tempRunState = {
        runId: event.run_id,
        status: targetMsg.status || 'streaming',
        events: [],
        stages: [],
        agents: [],
        findings: [],
        blocks: [...targetMsg.blocks],
        files: [],
        actions: [],
        lastEventId: 0,
      };

      const nextRunState = runReducer(tempRunState, { type: 'ADD_EVENT', event });

      // Build updated blocks without duplicate types (e.g. one routing block, one skills block)
      const mergedBlocks: Block[] = [];
      const seenTypes = new Set<string>();

      // Keep later blocks or update existing
      for (const block of nextRunState.blocks) {
        if (block.type === 'routing' || block.type === 'skills' || block.type === 'answer') {
          if (!seenTypes.has(block.type)) {
            mergedBlocks.push(block);
            seenTypes.add(block.type);
          }
        } else {
          mergedBlocks.push(block);
        }
      }

      const updatedMsg: Message = {
        ...targetMsg,
        status: nextRunState.status === 'done' ? 'done' : nextRunState.status === 'failed' ? 'failed' : targetMsg.status,
        blocks: mergedBlocks.length > 0 ? mergedBlocks : targetMsg.blocks,
      };

      const updatedMessages = [...state.conversation.messages];
      updatedMessages[msgIndex] = updatedMsg;

      return {
        ...state,
        conversation: {
          ...state.conversation,
          messages: updatedMessages,
        },
      };
    }

    case 'SET_STATUS': {
      if (!state.conversation) return state;
      const updatedMessages = state.conversation.messages.map((m) =>
        action.runId && m.run_id === action.runId ? { ...m, status: action.status } : m
      );
      return {
        ...state,
        conversation: {
          ...state.conversation,
          messages: updatedMessages,
        },
      };
    }

    default:
      return state;
  }
}
