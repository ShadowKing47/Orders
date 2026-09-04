const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type RunStatus = "RUNNING" | "SLEEPING" | "COMPLETED" | "TERMINATED" | "PAUSED";

export interface SupervisorConfig {
  id: string;
  name: string;
  description: string;
  extra_instructions: string[];
  created_at: string;
}

export interface Run {
  run_id: string;
  order_id: string;
  supervisor_config_id: string;
  status: RunStatus;
  memory_summary: string;
  next_wake_up_at: string | null;
  created_at: string;
}

export interface RunEvent {
  id: string;
  run_id: string;
  event_type: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface RunFinalOutput {
  run_id: string;
  summary: string;
  created_at: string;
}

class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    const body = await res.text();
    throw new ApiError(res.status, body || res.statusText);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return res.json() as Promise<T>;
}

export function listSupervisorConfigs(): Promise<SupervisorConfig[]> {
  return request<SupervisorConfig[]>("/api/supervisors", {
    next: { revalidate: 60 },
  } as RequestInit);
}

export function getSupervisorConfig(configId: string): Promise<SupervisorConfig> {
  return request<SupervisorConfig>(`/api/supervisors/${configId}`, {
    next: { revalidate: 60 },
  } as RequestInit);
}

export function createSupervisorConfig(payload: {
  name: string;
  description?: string;
  extra_instructions?: string[];
}): Promise<SupervisorConfig> {
  return request<SupervisorConfig>("/api/supervisors", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listRuns(): Promise<Run[]> {
  return request<Run[]>("/api/runs", { cache: "no-store" });
}

export function getRun(runId: string): Promise<Run> {
  return request<Run>(`/api/runs/${runId}`, { cache: "no-store" });
}

export function listRunEvents(runId: string): Promise<RunEvent[]> {
  return request<RunEvent[]>(`/api/runs/${runId}/events`, { cache: "no-store" });
}

export function getRunFinalOutput(runId: string): Promise<RunFinalOutput | null> {
  return request<RunFinalOutput | null>(`/api/runs/${runId}/final-output`, { cache: "no-store" });
}

export function startRun(configId: string, orderId: string): Promise<Run> {
  return request<Run>("/api/runs", {
    method: "POST",
    body: JSON.stringify({ supervisor_config_id: configId, order_id: orderId }),
  });
}

export function injectEvent(
  runId: string,
  eventType: string,
  payload: Record<string, unknown>,
): Promise<{ status: string }> {
  return request(`/api/runs/${runId}/events`, {
    method: "POST",
    body: JSON.stringify({ event_type: eventType, payload }),
  });
}

export function addInstruction(runId: string, instruction: string): Promise<{ status: string }> {
  return request(`/api/runs/${runId}/instructions`, {
    method: "POST",
    body: JSON.stringify({ instruction }),
  });
}

export function interruptRun(runId: string): Promise<{ status: string }> {
  return request(`/api/runs/${runId}/interrupt`, { method: "POST" });
}

export function resumeRun(runId: string): Promise<{ status: string }> {
  return request(`/api/runs/${runId}/resume`, { method: "POST" });
}

export function terminateRun(runId: string): Promise<{ status: string }> {
  return request(`/api/runs/${runId}/terminate`, { method: "POST" });
}
