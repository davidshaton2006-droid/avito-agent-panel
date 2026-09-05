const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const TOKEN_KEY = "avito_agent_token";

export type Channel = "avito" | "instagram";
export const CHANNELS: Channel[] = ["avito", "instagram"];
export const CHANNEL_LABELS: Record<Channel, string> = { avito: "Avito", instagram: "Instagram" };

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> | undefined),
  };
  if (token) headers.Authorization = `Bearer ${token}`;

  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export interface KnowledgeBaseEntry {
  id: string;
  question: string;
  answer: string;
  updatedAt?: string;
}

export interface Message {
  role: "guest" | "agent" | "admin" | "system";
  text: string;
  timestamp: string;
  imageUrl?: string | null;
}

export interface Conversation {
  id: string;
  conversationId: string;
  guestName?: string | null;
  chatId: string;
  itemId?: string | null;
  messages: Message[];
  status: "open" | "escalated" | "closed";
  createdAt?: string;
  updatedAt?: string;
  activeScenarioId?: string | null;
  activeStepIndex?: number | null;
  scenarioData?: Record<string, string>;
}

export interface ScenarioStep {
  type: "message" | "wait_photo" | "wait_text" | "notify_admin";
  text?: string | null;
  saveToField?: string | null;
}

export interface Scenario {
  id: string;
  scenarioId: string;
  name?: string | null;
  triggerKeyword: string;
  steps: ScenarioStep[];
  isActive: boolean;
  updatedAt?: string;
}

export interface AgentSettings {
  isActive: boolean;
  name: string;
  company: string;
  products: string;
  goal: string;
  knowledgeBaseText: string;
  allowedItemIds: string[];
}

export const api = {
  login: (username: string, password: string) =>
    request<{ token: string }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),

  listKnowledgeBase: (channel: Channel) => request<KnowledgeBaseEntry[]>(`/api/${channel}/knowledge-base`),
  createKnowledgeBaseEntry: (channel: Channel, question: string, answer: string) =>
    request<KnowledgeBaseEntry>(`/api/${channel}/knowledge-base`, {
      method: "POST",
      body: JSON.stringify({ question, answer }),
    }),
  updateKnowledgeBaseEntry: (channel: Channel, id: string, question: string, answer: string) =>
    request<KnowledgeBaseEntry>(`/api/${channel}/knowledge-base/${id}`, {
      method: "PUT",
      body: JSON.stringify({ question, answer }),
    }),
  deleteKnowledgeBaseEntry: (channel: Channel, id: string) =>
    request<{ ok: boolean }>(`/api/${channel}/knowledge-base/${id}`, { method: "DELETE" }),

  listConversations: (channel: Channel) => request<Conversation[]>(`/api/${channel}/conversations`),
  getConversation: (channel: Channel, id: string) =>
    request<Conversation>(`/api/${channel}/conversations/${id}`),
  sendAdminMessage: (channel: Channel, id: string, text: string) =>
    request<Conversation>(`/api/${channel}/conversations/${id}/send`, {
      method: "POST",
      body: JSON.stringify({ text }),
    }),
  setConversationStatus: (channel: Channel, id: string, status: string) =>
    request<Conversation>(`/api/${channel}/conversations/${id}/status?status=${status}`, {
      method: "PATCH",
    }),

  listScenarios: (channel: Channel) => request<Scenario[]>(`/api/${channel}/scenarios`),
  updateScenario: (channel: Channel, id: string, scenario: Scenario) =>
    request<Scenario>(`/api/${channel}/scenarios/${id}`, {
      method: "PUT",
      body: JSON.stringify(scenario),
    }),
  toggleScenario: (channel: Channel, id: string) =>
    request<Scenario>(`/api/${channel}/scenarios/${id}/toggle`, { method: "PATCH" }),

  getSettings: (channel: Channel) => request<AgentSettings>(`/api/${channel}/settings`),
  updateSettings: (channel: Channel, patch: Partial<AgentSettings>) =>
    request<AgentSettings>(`/api/${channel}/settings`, {
      method: "PUT",
      body: JSON.stringify(patch),
    }),
};

export { ApiError };
