import { getAccessToken } from "./auth";

export interface Technology {
  id: string;
  name: string;
  category: string;
}

export interface Update {
  update_id: string;
  title: string;
  technology: string;
  category: string;
  priority: "critical" | "high" | "medium" | "low" | "informational";
  summary?: string;
  published_at?: string;
  canonical_url: string;
  observed_at?: string;
  department_relevance?: string[];
  relevance_topics?: Record<string, string[]>;
  department_relevance_scores?: Record<string, number>;
  primary_department?: string;
}

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "");

export const DEFAULT_TECHNOLOGIES: Technology[] = [
  { id: "aws", name: "AWS", category: "Cloud" },
  { id: "azure", name: "Azure", category: "Cloud" },
  { id: "gcp", name: "Google Cloud", category: "Cloud" },
  { id: "kubernetes", name: "Kubernetes", category: "Containers" },
  { id: "terraform", name: "Terraform", category: "Infrastructure as Code" },
  { id: "gitlab", name: "GitLab", category: "CI/CD" },
];

export async function getTechnologies(): Promise<Technology[]> {
  if (!API_BASE) return DEFAULT_TECHNOLOGIES;
  const response = await fetch(`${API_BASE}/api/v1/technologies`, { headers: await authHeaders() });
  if (!response.ok) throw new Error("Unable to load technologies");
  const body = await response.json();
  return body.items as Technology[];
}

export async function getUpdates(technology?: string): Promise<Update[]> {
  if (!API_BASE) return [];
  const query = new URLSearchParams({ days: "7", limit: "100" });
  if (technology) query.set("technology", technology);
  const response = await fetch(`${API_BASE}/api/v1/updates?${query.toString()}`, { headers: await authHeaders() });
  if (!response.ok) throw new Error("Unable to load updates");
  const body = await response.json();
  return (body.items ?? []) as Update[];
}

async function authHeaders(): Promise<HeadersInit> {
  const token = await getAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}


export type NotificationChannel = "email" | "slack" | "teams";

export interface Subscription {
  technology_id: string;
  channel: NotificationChannel;
  enabled: boolean;
  created_at?: string | null;
  updated_at?: string | null;
  secret_configured: boolean;
}

export async function getSubscriptions(): Promise<Subscription[]> {
  if (!API_BASE) return [];
  const response = await fetch(`${API_BASE}/api/v1/subscriptions`, { headers: await authHeaders() });
  if (!response.ok) throw new Error("Unable to load subscriptions");
  const body = await response.json();
  return (body.items ?? []) as Subscription[];
}

export async function saveSubscription(
  technologyId: string,
  channel: NotificationChannel = "email",
  secretId?: string,
): Promise<Subscription> {
  if (!API_BASE) throw new Error("Configure the TechPulse API before managing subscriptions.");
  const response = await fetch(`${API_BASE}/api/v1/subscriptions/${encodeURIComponent(technologyId)}`, {
    method: "PUT",
    headers: { ...await authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify({ channel, ...(secretId ? { secret_id: secretId } : {}) }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({})) as { detail?: { message?: string } };
    throw new Error(body.detail?.message ?? "Unable to save subscription");
  }
  const body = await response.json();
  return body.item as Subscription;
}

export async function removeSubscription(technologyId: string): Promise<void> {
  if (!API_BASE) throw new Error("Configure the TechPulse API before managing subscriptions.");
  const response = await fetch(`${API_BASE}/api/v1/subscriptions/${encodeURIComponent(technologyId)}`, {
    method: "DELETE",
    headers: await authHeaders(),
  });
  if (!response.ok) throw new Error("Unable to remove subscription");
}

export interface UserUpdateState {
  update_id: string;
  saved: boolean;
  read: boolean;
  created_at?: string | null;
  updated_at?: string | null;
}

export async function getUserState(): Promise<UserUpdateState[]> {
  if (!API_BASE) return [];
  const response = await fetch(`${API_BASE}/api/v1/user-state`, { headers: await authHeaders() });
  if (!response.ok) throw new Error("Unable to load saved/read state");
  const body = await response.json();
  return (body.items ?? []) as UserUpdateState[];
}

export async function saveUserState(
  updateId: string,
  change: { saved?: boolean; read?: boolean },
): Promise<UserUpdateState> {
  if (!API_BASE) throw new Error("Configure the TechPulse API before saving updates.");
  const response = await fetch(`${API_BASE}/api/v1/user-state/${encodeURIComponent(updateId)}`, {
    method: "PUT",
    headers: { ...await authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify(change),
  });
  if (!response.ok) throw new Error("Unable to update saved/read state");
  const body = await response.json();
  return body.item as UserUpdateState;
}


export interface RefreshResult {
  queued_sources: number;
  source_ids: string[];
}

export async function refreshUpdates(): Promise<RefreshResult> {
  if (!API_BASE) throw new Error("Configure the TechPulse API before refreshing updates.");
  const response = await fetch(`${API_BASE}/api/v1/refresh`, {
    method: "POST",
    headers: await authHeaders(),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({})) as { detail?: { message?: string } };
    throw new Error(body.detail?.message ?? "Could not start source polling.");
  }
  return await response.json() as RefreshResult;
}
