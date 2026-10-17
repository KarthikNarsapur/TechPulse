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
}

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "");

export async function getTechnologies(): Promise<Technology[]> {
  if (!API_BASE) {
    return [
      { id: "aws", name: "AWS", category: "Cloud" },
      { id: "azure", name: "Azure", category: "Cloud" },
      { id: "gcp", name: "Google Cloud", category: "Cloud" },
      { id: "kubernetes", name: "Kubernetes", category: "Containers" },
      { id: "terraform", name: "Terraform", category: "Infrastructure as Code" },
      { id: "gitlab", name: "GitLab", category: "CI/CD" },
    ];
  }
  const response = await fetch(`${API_BASE}/api/v1/technologies`, { headers: authHeaders() });
  if (!response.ok) throw new Error("Unable to load technologies");
  const body = await response.json();
  return body.items as Technology[];
}

export async function getUpdates(technology?: string): Promise<Update[]> {
  if (!API_BASE) return [];
  const query = new URLSearchParams();
  if (technology) query.set("technology", technology);
  const response = await fetch(`${API_BASE}/api/v1/updates?${query.toString()}`, { headers: authHeaders() });
  if (!response.ok) throw new Error("Unable to load updates");
  const body = await response.json();
  return (body.items ?? []) as Update[];
}

function authHeaders(): HeadersInit {
  const token = getAccessToken();
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
  const response = await fetch(`${API_BASE}/api/v1/subscriptions`, { headers: authHeaders() });
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
    headers: { ...authHeaders(), "Content-Type": "application/json" },
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
    headers: authHeaders(),
  });
  if (!response.ok) throw new Error("Unable to remove subscription");
}
