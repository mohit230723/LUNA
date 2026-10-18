export interface TraceState {
  revealedStepCount: number;
  totalSteps: number;
  playing: boolean;
  speed: 1 | 2 | 5;
  selectedStepSeq: number | null;
  showAll: boolean;
}

export const INITIAL_TRACE_STATE: TraceState = {
  revealedStepCount: 0,
  totalSteps: 0,
  playing: false,
  speed: 1,
  selectedStepSeq: null,
  showAll: false,
};

export type TraceAction =
  | { type: 'SET_TOTAL_STEPS'; totalSteps: number }
  | { type: 'PLAY' }
  | { type: 'PAUSE' }
  | { type: 'TOGGLE_PLAY' }
  | { type: 'STEP_FORWARD' }
  | { type: 'STEP_BACK' }
  | { type: 'SEEK_STEP'; stepIndex: number }
  | { type: 'SET_SPEED'; speed: 1 | 2 | 5 }
  | { type: 'TOGGLE_SHOW_ALL' }
  | { type: 'SELECT_STEP'; seq: number | null };

export function traceReducer(state: TraceState, action: TraceAction): TraceState {
  switch (action.type) {
    case 'SET_TOTAL_STEPS':
      return {
        ...state,
        totalSteps: action.totalSteps,
        revealedStepCount: action.totalSteps, // default to showing full graph initially or step 0
      };

    case 'PLAY':
      return { ...state, playing: true };

    case 'PAUSE':
      return { ...state, playing: false };

    case 'TOGGLE_PLAY':
      return { ...state, playing: !state.playing };

    case 'STEP_FORWARD': {
      const nextCount = Math.min(state.totalSteps, state.revealedStepCount + 1);
      const isAtEnd = nextCount >= state.totalSteps;
      return {
        ...state,
        revealedStepCount: nextCount,
        playing: isAtEnd ? false : state.playing,
        selectedStepSeq: nextCount,
      };
    }

    case 'STEP_BACK': {
      const prevCount = Math.max(0, state.revealedStepCount - 1);
      return {
        ...state,
        revealedStepCount: prevCount,
        selectedStepSeq: prevCount > 0 ? prevCount : null,
      };
    }

    case 'SEEK_STEP': {
      const clamped = Math.max(0, Math.min(state.totalSteps, action.stepIndex));
      return {
        ...state,
        revealedStepCount: clamped,
        selectedStepSeq: clamped > 0 ? clamped : null,
      };
    }

    case 'SET_SPEED':
      return { ...state, speed: action.speed };

    case 'TOGGLE_SHOW_ALL':
      return {
        ...state,
        showAll: !state.showAll,
        revealedStepCount: !state.showAll ? state.totalSteps : state.revealedStepCount,
      };

    case 'SELECT_STEP':
      return { ...state, selectedStepSeq: action.seq };

    default:
      return state;
  }
}
