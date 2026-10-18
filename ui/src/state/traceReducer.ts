export interface TraceState {
  mode: 'overview' | 'tour';
  stepIndex: number | null; // null in overview, 0 for START, 1..N for steps 1..N
  selectedNodeId: string | null;
  hideContext: boolean;
  layout: 'layered' | 'radial' | 'force';
}

export const INITIAL_TRACE_STATE: TraceState = {
  mode: 'overview',
  stepIndex: null,
  selectedNodeId: null,
  hideContext: false,
  layout: 'layered',
};
export const initialTraceState = INITIAL_TRACE_STATE;

export type TraceAction =
  | { type: 'ENTER_TOUR'; stepIndex?: number }
  | { type: 'EXIT_TOUR' }
  | { type: 'NEXT_STEP'; totalSteps: number }
  | { type: 'PREV_STEP' }
  | { type: 'SET_STEP'; stepIndex: number }
  | { type: 'SELECT_NODE'; nodeId: string | null }
  | { type: 'TOGGLE_HIDE_CONTEXT' }
  | { type: 'SET_LAYOUT'; layout: 'layered' | 'radial' | 'force' };

export function traceReducer(state: TraceState, action: TraceAction): TraceState {
  switch (action.type) {
    case 'ENTER_TOUR':
      return {
        ...state,
        mode: 'tour',
        stepIndex: action.stepIndex !== undefined ? action.stepIndex : 0,
      };

    case 'EXIT_TOUR':
      return {
        ...state,
        mode: 'overview',
        stepIndex: null,
      };

    case 'NEXT_STEP': {
      if (state.mode !== 'tour') {
        return { ...state, mode: 'tour', stepIndex: 0 };
      }
      const cur = state.stepIndex ?? 0;
      const next = Math.min(action.totalSteps, cur + 1);
      return { ...state, stepIndex: next };
    }

    case 'PREV_STEP': {
      if (state.mode !== 'tour' || state.stepIndex === null || state.stepIndex <= 0) {
        return state;
      }
      return { ...state, stepIndex: state.stepIndex - 1 };
    }

    case 'SET_STEP':
      return {
        ...state,
        mode: 'tour',
        stepIndex: action.stepIndex,
      };

    case 'SELECT_NODE':
      return { ...state, selectedNodeId: action.nodeId };

    case 'TOGGLE_HIDE_CONTEXT':
      return { ...state, hideContext: !state.hideContext };

    case 'SET_LAYOUT':
      return { ...state, layout: action.layout };

    default:
      return state;
  }
}
