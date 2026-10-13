/**
 * Backend API Client for Litmus Multi-Agent Courtroom Debugger
 * Strictly adheres to FastAPI routes and schemas from Litmus/Backend/app/api/server.py
 */

const API_BASE = '/api';

export async function fetchHealth() {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error(`Health check failed: ${res.statusText}`);
  return res.json();
}

export async function fetchSessions() {
  const res = await fetch(`${API_BASE}/sessions`);
  if (!res.ok) throw new Error(`Failed to fetch sessions: ${res.statusText}`);
  return res.json();
}

export async function createSession(payload) {
  const res = await fetch(`${API_BASE}/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to create session: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchSession(sessionId) {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}`);
  if (!res.ok) throw new Error(`Failed to get session: ${res.statusText}`);
  return res.json();
}

export async function runSession(sessionId) {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) throw new Error(`Failed to start session execution: ${res.statusText}`);
  return res.json();
}

export async function fastForwardSession(sessionId) {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/fast-forward`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) throw new Error(`Failed to fast forward: ${res.statusText}`);
  return res.json();
}

export async function fetchSessionResult(sessionId) {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/result`);
  if (!res.ok) throw new Error(`Failed to get session outcome: ${res.statusText}`);
  return res.json();
}

/**
 * Connects to Server-Sent Events (SSE) stream for real-time courtroom events
 */
export function connectSessionEventStream(sessionId, onMessage, onError, onComplete) {
  const eventSource = new EventSource(`${API_BASE}/sessions/${sessionId}/events`);

  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      onMessage(data);
      if (data.type === 'completed' || data.type === 'error') {
        if (onComplete) onComplete(data);
        eventSource.close();
      }
    } catch (err) {
      console.warn("Failed to parse event JSON:", event.data, err);
    }
  };

  eventSource.onerror = (err) => {
    if (onError) onError(err);
    eventSource.close();
  };

  return () => {
    eventSource.close();
  };
}
