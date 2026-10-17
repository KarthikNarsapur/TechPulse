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
  const response = await fetch(`${API_BASE}/api/v1/technologies`);
  if (!response.ok) throw new Error("Unable to load technologies");
  const body = await response.json();
  return body.items as Technology[];
}

export async function getUpdates(technology?: string): Promise<Update[]> {
  if (!API_BASE || !technology) return [];
  const query = new URLSearchParams({ technology });
  const response = await fetch(`${API_BASE}/api/v1/updates?${query.toString()}`);
  if (!response.ok) throw new Error("Unable to load updates");
  const body = await response.json();
  return (body.items ?? []) as Update[];
}
