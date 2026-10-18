import { CustomerExplanation, GraphScopeData, ProposedAction, ReplayRecording } from '../types';

export const API_BASE = '/api';

export async function fetchReplayData(): Promise<ReplayRecording> {
  const res = await fetch(`${API_BASE}/replay`);
  if (!res.ok) {
    throw new Error(`Failed to load replay: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchRunWhy(runId: string, customerId: string): Promise<CustomerExplanation> {
  const res = await fetch(`${API_BASE}/runs/${encodeURIComponent(runId)}/why/${encodeURIComponent(customerId)}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch explanation for ${customerId}: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchGraphScope(runId: string, scope: string): Promise<GraphScopeData> {
  const res = await fetch(`${API_BASE}/graphs/${encodeURIComponent(scope)}?run_id=${encodeURIComponent(runId)}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch graph scope ${scope}: ${res.statusText}`);
  }
  return res.json();
}

export async function approveAction(runId: string, actionId: string, approvalToken?: string): Promise<{ status: string; action_id: string; execution_result?: any }> {
  const res = await fetch(`${API_BASE}/runs/${encodeURIComponent(runId)}/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      action_id: actionId,
      approval_token: approvalToken || 'human_review_token',
    }),
  });
  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(errorBody.detail || `Approval failed with ${res.status}`);
  }
  return res.json();
}

export async function rejectAction(runId: string, actionId: string, reason?: string): Promise<{ status: string; action_id: string }> {
  const res = await fetch(`${API_BASE}/runs/${encodeURIComponent(runId)}/reject`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      action_id: actionId,
      reason: reason || 'Rejected by investigator in UI',
    }),
  });
  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(errorBody.detail || `Rejection failed with ${res.status}`);
  }
  return res.json();
}

export async function startLiveRun(config?: {
  scenario?: string;
  parallel?: number;
  use_llm?: boolean;
}): Promise<{ run_id: string; status: string }> {
  const res = await fetch(`${API_BASE}/runs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config || {}),
  });
  if (!res.ok) {
    throw new Error(`Failed to start run: ${res.statusText}`);
  }
  return res.json();
}
