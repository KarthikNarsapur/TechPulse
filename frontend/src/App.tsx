import { useEffect, useMemo, useState } from "react";
import {
  Activity, ArrowUpRight, Bell, Bookmark, Boxes, ChevronDown,
  CircleAlert, Cloud, Command, GitBranch, LayoutDashboard, Search,
  Settings2, ShieldCheck, Sparkles, Workflow, LogOut,
} from "lucide-react";
import { DEFAULT_TECHNOLOGIES, getTechnologies, getUpdates, getSubscriptions, getSourceStatus, getUserState, saveUserState, saveSubscription, removeSubscription, refreshUpdates, type SourcePollStatus, type UserUpdateState, type Subscription, type Technology, type Update } from "./api";
import { beginLogin, finishLoginCallback, isAuthConfigured, isRemoteApiConfigured, signOut } from "./auth";

type WorkspaceView = "focus" | "shared";

interface DepartmentWorkspace {
  id: string;
  label: string;
  group: string;
  description: string;
  technologies: string[];
}

const ALL_TECHNOLOGIES = ["aws", "azure", "gcp", "kubernetes", "terraform", "gitlab"];
const DEPARTMENT_WORKSPACES: DepartmentWorkspace[] = [
  { id: "tc-data-aiot", label: "TC - Data and AIoT", group: "Tech Consulting", description: "Data platforms, AI, databases, and cloud services", technologies: ["aws", "azure", "gcp"] },
  { id: "tc-development", label: "TC - Development", group: "Tech Consulting", description: "Application engineering and developer tooling", technologies: ["gitlab", "aws", "azure", "gcp"] },
  { id: "tc-devops-kubernetes", label: "TC - DevOps & Kubernetes", group: "Tech Consulting", description: "Platform engineering, Kubernetes, IaC, and CI/CD", technologies: ["kubernetes", "terraform", "gitlab", "aws", "azure", "gcp"] },
  { id: "tc-general", label: "TC - General", group: "Tech Consulting", description: "Shared cloud, infrastructure, and engineering updates", technologies: ALL_TECHNOLOGIES },
  { id: "tc-infra-security", label: "TC - Infra and Security", group: "Tech Consulting", description: "Cloud infrastructure, identity, network security, and compliance", technologies: ["aws", "azure", "gcp", "kubernetes", "terraform"] },
  { id: "tc-it-support", label: "TC - IT Support", group: "Tech Consulting", description: "Service health, support lifecycle, incidents, and troubleshooting", technologies: ALL_TECHNOLOGIES },
  { id: "tc-ld-content", label: "TC - L&D, Content", group: "Tech Consulting", description: "Technical learning, content, and certification updates", technologies: ALL_TECHNOLOGIES },
  { id: "tc-managed-services", label: "TC - Managed Services", group: "Tech Consulting", description: "Operations, monitoring, backup, patching, and service reliability", technologies: ALL_TECHNOLOGIES },
  { id: "tc-migration-finops", label: "TC - Migration and FinOps", group: "Tech Consulting", description: "Migration, modernization, cloud infrastructure, and cost optimization", technologies: ["aws", "azure", "gcp", "terraform", "kubernetes"] },
  { id: "tc-presales", label: "TC - Pre-Sales", group: "Tech Consulting", description: "Solution architecture and technical enablement", technologies: ["aws", "azure", "gcp", "kubernetes", "terraform"] },
  { id: "ts-ms-programs", label: "TS - MS Programs", group: "Training Sales", description: "Microsoft training program updates", technologies: ["azure"] },
  { id: "ts-corporate-accounts", label: "TS - Corporate Accounts", group: "Training Sales", description: "Cross-technology updates for corporate accounts", technologies: ALL_TECHNOLOGIES },
  { id: "ts-inside-sales", label: "TS - Inside Sales Management", group: "Training Sales", description: "Technology changes relevant to inside sales", technologies: ALL_TECHNOLOGIES },
  { id: "ts-demand-generation", label: "TS - Demand Generation", group: "Training Sales", description: "Technology announcements and training demand signals", technologies: ALL_TECHNOLOGIES },
  { id: "general", label: "General", group: "Company-wide", description: "Cross-company engineering announcements", technologies: ALL_TECHNOLOGIES },
];

function priorityLabel(priority: Update["priority"]): string {
  return priority.charAt(0).toUpperCase() + priority.slice(1);
}

export default function App() {
  const [technologies, setTechnologies] = useState<Technology[]>([]);
  const [updates, setUpdates] = useState<Update[]>([]);
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
  const [sourceStatuses, setSourceStatuses] = useState<SourcePollStatus[]>([]);
  const [userStates, setUserStates] = useState<UserUpdateState[]>([]);
  const [userStateMessage, setUserStateMessage] = useState("");
  const [sourceStatusMessage, setSourceStatusMessage] = useState("");
  const [subscriptionBusy, setSubscriptionBusy] = useState<string | null>(null);
  const [refreshBusy, setRefreshBusy] = useState(false);
  const [refreshMessage, setRefreshMessage] = useState("");
  const [subscriptionMessage, setSubscriptionMessage] = useState("");
  const [selected, setSelected] = useState("all");
  const [activeWorkspaceId, setActiveWorkspaceId] = useState(() => window.localStorage.getItem("techpulse.activeWorkspace") ?? "tc-migration-finops");
  const [workspaceMenuOpen, setWorkspaceMenuOpen] = useState(false);
  const [workspaceView, setWorkspaceView] = useState<WorkspaceView>("focus");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [authStatus, setAuthStatus] = useState<"checking" | "authenticated" | "preview" | "login_required" | "config_error">("checking");
  const [authError, setAuthError] = useState("");

  useEffect(() => {
    let cancelled = false;
    if (!isRemoteApiConfigured()) {
      setAuthStatus("preview");
      return () => { cancelled = true; };
    }
    if (!isAuthConfigured()) {
      setAuthStatus("config_error");
      return () => { cancelled = true; };
    }
    finishLoginCallback()
      .then((authenticated) => {
        if (!cancelled) setAuthStatus(authenticated ? "authenticated" : "login_required");
      })
      .catch((cause: unknown) => {
        if (!cancelled) {
          setAuthError(cause instanceof Error ? cause.message : "Sign-in could not be completed.");
          setAuthStatus("login_required");
        }
      });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (authStatus !== "authenticated" && authStatus !== "preview") return;
    let cancelled = false;
    setLoading(true);
    getTechnologies()
      .then((technologyList) => {
        if (!cancelled) setTechnologies(technologyList);
      })
      .catch(() => {
        if (!cancelled) { setTechnologies(DEFAULT_TECHNOLOGIES); setError("The API could not load. Technology filters remain available; updates and account features need a healthy API connection."); }
      });
    getUpdates()
      .then((updateList) => {
        if (!cancelled) setUpdates(updateList);
      })
      .catch(() => {
        if (!cancelled) setError("Could not load updates for this filter.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    if (authStatus === "authenticated") {
      getSubscriptions()
        .then((items) => {
          if (!cancelled) setSubscriptions(items);
        })
        .catch(() => {
          if (!cancelled) setSubscriptionMessage("Could not load your subscriptions.");
        });
    } else {
      setSubscriptions([]);
    }
    return () => { cancelled = true; };
  }, [authStatus]);


  useEffect(() => {
    if (authStatus !== "authenticated") {
      setSourceStatuses([]);
      setSourceStatusMessage("");
      return;
    }
    let cancelled = false;
    getSourceStatus()
      .then((items) => {
        if (!cancelled) {
          setSourceStatuses(items);
          setSourceStatusMessage("");
        }
      })
      .catch(() => {
        if (!cancelled) setSourceStatusMessage("Source polling status is currently unavailable.");
      });
    return () => { cancelled = true; };
  }, [authStatus]);

  useEffect(() => {
    if (authStatus !== "authenticated") {
      setUserStates([]);
      setUserStateMessage("");
      return;
    }
    let cancelled = false;
    getUserState()
      .then((items) => {
        if (!cancelled) {
          setUserStates(items);
          setUserStateMessage("");
        }
      })
      .catch(() => {
        if (!cancelled) setUserStateMessage("Saved/read state could not be loaded.");
      });
    return () => { cancelled = true; };
  }, [authStatus]);

  useEffect(() => {
    window.localStorage.setItem("techpulse.activeWorkspace", activeWorkspaceId);
  }, [activeWorkspaceId]);

  async function runRefresh() {
    setRefreshBusy(true);
    setRefreshMessage("");
    try {
      const result = await refreshUpdates();
      setRefreshMessage(`Queued polling for ${result.queued_sources} official sources. New updates from the past 7 days will appear as processing finishes; refresh the feed in a few moments.`);
      const latest = await getUpdates();
      setUpdates(latest);
      const statuses = await getSourceStatus();
      setSourceStatuses(statuses);
    } catch (cause: unknown) {
      setRefreshMessage(cause instanceof Error ? cause.message : "Could not start source polling.");
    } finally {
      setRefreshBusy(false);
    }
  }

  async function changeUserState(updateId: string, change: { saved?: boolean; read?: boolean }) {
    setUserStateMessage("");
    try {
      const updated = await saveUserState(updateId, change);
      setUserStates((items) => [...items.filter((item) => item.update_id !== updateId), updated]);
    } catch (cause: unknown) {
      setUserStateMessage(cause instanceof Error ? cause.message : "Saved/read state could not be updated.");
    }
  }

  async function toggleSubscription(technologyId: string) {
    const existing = subscriptions.find((item) => item.technology_id === technologyId);
    setSubscriptionBusy(technologyId);
    setSubscriptionMessage("");
    try {
      if (existing) {
        await removeSubscription(technologyId);
        setSubscriptions((items) => items.filter((item) => item.technology_id !== technologyId));
        setSubscriptionMessage("Email alerts disabled for this technology.");
      } else {
        const created = await saveSubscription(technologyId, "email");
        setSubscriptions((items) => [...items.filter((item) => item.technology_id !== technologyId), created]);
        setSubscriptionMessage("Email alerts enabled for this technology.");
      }
    } catch (cause: unknown) {
      setSubscriptionMessage(cause instanceof Error ? cause.message : "Subscription could not be updated.");
    } finally {
      setSubscriptionBusy(null);
    }
  }

  const activeWorkspace = DEPARTMENT_WORKSPACES.find((workspace) => workspace.id === activeWorkspaceId) ?? DEPARTMENT_WORKSPACES[0];

  const visibleUpdates = useMemo(() => {
    const filtered = updates.filter((update) => {
      const technologyId = update.technology.toLowerCase();
      const technologyMatches = selected === "all" || technologyId === selected;
      const departmentMatches = workspaceView === "shared" || (update.department_relevance ?? []).includes(activeWorkspace.id);
      const technologyMatchesWorkspace = selected !== "all" || activeWorkspace.technologies.includes(technologyId) || workspaceView === "shared";
      const searchMatches = `${update.title} ${update.summary ?? "Analysis is pending. Open the official announcement for full details."} ${update.technology} ${update.category} ${(update.relevance_topics?.[activeWorkspace.id] ?? []).join(" ")}`
        .toLowerCase().includes(search.toLowerCase());
      return technologyMatches && departmentMatches && technologyMatchesWorkspace && searchMatches;
    });
    if (workspaceView === "focus" && activeWorkspace.id === "tc-migration-finops" && selected === "all") {
      return filtered.sort((a, b) =>
        (b.department_relevance_scores?.[activeWorkspace.id] ?? 0) - (a.department_relevance_scores?.[activeWorkspace.id] ?? 0)
        || new Date(b.published_at ?? b.observed_at ?? 0).getTime() - new Date(a.published_at ?? a.observed_at ?? 0).getTime()
      );
    }
    return filtered;
  }, [updates, selected, search, workspaceView, activeWorkspace]);

  if (authStatus === "checking") {
    return <AuthScreen title="Opening TechPulse" subtitle="Checking the sign-in session…" />;
  }
  if (authStatus === "config_error") {
    return <AuthScreen title="TechPulse needs configuration" subtitle="Set the API URL and Cognito Hosted UI values for the deployed frontend." />;
  }
  if (authStatus === "login_required") {
    return (
      <AuthScreen
        title="Your engineering radar awaits"
        subtitle="Sign in to view your organization's Cloud & DevOps release intelligence."
        error={authError}
        actionLabel="Sign in"
        onAction={() => { void beginLogin().catch((cause: unknown) => setAuthError(cause instanceof Error ? cause.message : "Unable to start sign-in.")); }}
      />
    );
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#" aria-label="TechPulse home">
          <span className="brand-mark"><Activity size={21} /></span>
          <span><strong>techpulse</strong><small>ENGINEERING INTELLIGENCE</small></span>
        </a>
        <div className="workspace-label">WORKSPACE <ChevronDown size={13} /></div>
        <div className="workspace-menu">
          <button
            type="button"
            className="workspace-picker"
            aria-label="Choose department workspace"
            aria-haspopup="true"
            aria-expanded={workspaceMenuOpen}
            onClick={() => setWorkspaceMenuOpen((open) => !open)}
          >
            <span className="workspace-dot" />
            <span className="workspace-picker-label">{activeWorkspace.label}</span>
            <ChevronDown size={14} />
          </button>
          {workspaceMenuOpen && (
            <>
              <button className="workspace-menu-backdrop" aria-label="Close workspace menu" onClick={() => setWorkspaceMenuOpen(false)} />
              <div className="workspace-menu-list" role="menu" aria-label="Department workspaces">
                {["Tech Consulting", "Training Sales", "Company-wide"].map((group) => {
                  const groupWorkspaces = DEPARTMENT_WORKSPACES.filter((workspace) => workspace.group === group);
                  if (groupWorkspaces.length === 0) return null;
                  return (
                    <div className="workspace-menu-group" key={group}>
                      <div className="workspace-menu-group-label">{group}</div>
                      {groupWorkspaces.map((workspace) => (
                        <button
                          type="button"
                          role="menuitem"
                          key={workspace.id}
                          className={workspace.id === activeWorkspace.id ? "workspace-menu-option active" : "workspace-menu-option"}
                          aria-current={workspace.id === activeWorkspace.id ? "true" : undefined}
                          onClick={() => {
                            setActiveWorkspaceId(workspace.id);
                            setSelected("all");
                            setWorkspaceView("focus");
                            setWorkspaceMenuOpen(false);
                          }}
                        >
                          {workspace.label}
                          {workspace.id === activeWorkspace.id && <span aria-hidden="true">✓</span>}
                        </button>
                      ))}
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </div>
        <nav className="navigation" aria-label="Main navigation">
          <span className="nav-section">DISCOVER</span>
          <a className="nav-link active" href="#updates"><LayoutDashboard size={17} /> Overview <span className="nav-count">01</span></a>
          <a className="nav-link" href="#updates"><Search size={17} /> All updates</a>
          <a className="nav-link" href="#my-technologies"><Boxes size={17} /> My technologies</a>
          <a className="nav-link" href="#saved"><Bookmark size={17} /> Saved updates</a>
          <span className="nav-section spaced">YOUR STACK</span>
          {technologies.filter((technology) => activeWorkspace.technologies.includes(technology.id)).map((technology) => (
            <button key={technology.id} className={selected === technology.id ? "nav-link tech-link selected" : "nav-link tech-link"} onClick={() => setSelected(technology.id)}>
              <span className={`tech-icon ${technology.id}`}>{technology.id === "aws" || technology.id === "azure" || technology.id === "gcp" ? <Cloud size={15} /> : technology.id === "gitlab" ? <GitBranch size={15} /> : <Workflow size={15} />}</span>
              {technology.name}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="sync-card"><span className="sync-pulse" /><div><strong>Source monitoring</strong><small>Registry configured</small></div><ShieldCheck size={16} /></div>
          <button className="nav-link" onClick={() => document.getElementById("my-technologies")?.scrollIntoView({ behavior: "smooth" })}><Settings2 size={17} /> Settings & alerts</button>
          <div className="user-card"><div className="avatar">KN</div><div><strong>Engineering user</strong><small>Cloud & DevOps</small></div><Command size={16} /></div>
        </div>
      </aside>

      <main className="main-content" id="updates">
        <header className="topbar">
          <div className="breadcrumbs">Workspace <span>/</span> <strong>{activeWorkspace.label}</strong></div>
          <div className="top-actions">
            <div className="status-pill"><span /> Serverless pilot</div>
            <button className="icon-button" aria-label="Notifications and subscriptions" title="Go to notification settings" onClick={() => document.getElementById("my-technologies")?.scrollIntoView({ behavior: "smooth" })}><Bell size={18} /><i /></button>
            {authStatus === "authenticated" ? (
              <button className="icon-button" aria-label="Sign out" title="Sign out" onClick={signOut}><LogOut size={17} /></button>
            ) : <div className="mini-avatar">DE</div>}
          </div>
        </header>

        <div className="page-container">
          <section className="welcome-row">
            <div>
              <div className="eyebrow"><Sparkles size={14} /> CLOUD & DEVOPS RELEASE INTELLIGENCE</div>
              <h1>Stay ahead of <span>what changes.</span></h1>
              <p className="page-subtitle">One feed for the technologies you build, ship, and operate.</p>
            </div>
            <button className="date-button" onClick={() => { void runRefresh(); }} disabled={refreshBusy}><Activity size={15} /> {refreshBusy ? "Refreshing…" : "Refresh updates"} <ChevronDown size={14} /></button>
          </section>

          <section className="workspace-context-panel" aria-label="Department workspace">
            <div className="workspace-context-copy">
              <span className="workspace-context-kicker">{activeWorkspace.group} WORKSPACE</span>
              <h2>{activeWorkspace.label}</h2>
              <p>{activeWorkspace.description}. Browse related updates from other teams without leaving this workspace.</p>
            </div>
            <div className="workspace-view-switch" role="group" aria-label="Workspace update view">
              <button className={workspaceView === "focus" ? "workspace-view-button active" : "workspace-view-button"} onClick={() => setWorkspaceView("focus")} aria-pressed={workspaceView === "focus"}>Department focus</button>
              <button className={workspaceView === "shared" ? "workspace-view-button active" : "workspace-view-button"} onClick={() => setWorkspaceView("shared")} aria-pressed={workspaceView === "shared"}>All shared updates</button>
            </div>
            <div className="workspace-technology-note">
              {workspaceView === "focus"
                ? `Focused on ${activeWorkspace.technologies.map((id) => technologies.find((technology) => technology.id === id)?.name ?? id).join(" · ")}. Choose any technology below to browse its updates here.`
                : "Showing the shared update catalog. Your active department workspace stays the same."}
            </div>
          </section>

          <section className="hero-panel">
            <div className="hero-copy">
              <div className="hero-label"><span className="hero-spark">✳</span> YOUR ENGINEERING RADAR</div>
              <h2>Less release-note hunting.<br /><em>More time to engineer.</em></h2>
              <p>TechPulse brings official releases into one place, explains why they matter, and helps your team spot changes worth acting on.</p>
              <a className="hero-link" href="#technologies">Explore your technology stack <ArrowUpRight size={16} /></a>
            </div>
            <div className="radar-art" aria-hidden="true">
              <div className="radar-ring ring-one" /><div className="radar-ring ring-two" /><div className="radar-ring ring-three" />
              <div className="radar-sweep" /><div className="radar-center"><Activity size={26} /></div>
              <span className="radar-node node-one" /><span className="radar-node node-two" /><span className="radar-node node-three" />
            </div>
            <div className="hero-foot"><span><span className="green-dot" /> Automated discovery</span><span><span className="green-dot" /> Source-grounded summaries</span><span><span className="green-dot" /> Team-relevant alerts</span></div>
          </section>

          <section className="stats-grid" aria-label="Update summary">
            <StatCard icon={<Activity size={17} />} label="UPDATES TRACKED" value={String(updates.length).padStart(2, "0")} detail={updates.length ? "In the current feed" : "Waiting for first ingestion"} color="teal" />
            <StatCard icon={<CircleAlert size={17} />} label="NEEDS ATTENTION" value="—" detail="Impact assessment pending" color="orange" />
            <StatCard icon={<Boxes size={17} />} label="TECHNOLOGIES" value={String(technologies.length).padStart(2, "0")} detail="Initial technology groups" color="purple" />
            <StatCard icon={<Bell size={17} />} label="DELIVERY CHANNELS" value="03" detail="Portal · Email · Chat-ready" color="blue" />
          </section>


          <section className="source-health-panel" aria-label="Source polling health">
            <div className="subscription-heading">
              <div><div className="eyebrow muted">INGESTION HEALTH</div><h2>Source polling status</h2></div>
              <span className="subscription-count">{sourceStatuses.length} tracked</span>
            </div>
            {authStatus !== "authenticated" ? (
              <p className="subscription-hint">Sign in to view durable source polling checkpoints.</p>
            ) : sourceStatusMessage ? (
              <p className="subscription-message" role="status">{sourceStatusMessage}</p>
            ) : sourceStatuses.length === 0 ? (
              <p className="subscription-hint">No poll checkpoints yet. They appear after the first source poll completes.</p>
            ) : (
              <div className="source-status-list">
                {sourceStatuses.map((source) => (
                  <div className="source-status-row" key={source.source_id}>
                    <div className={`source-status-dot ${source.poll_status ?? "unknown"}`} />
                    <div className="source-status-copy">
                      <strong>{source.source_id}</strong>
                      <small>
                        {source.last_poll_success_at
                          ? `Last success ${new Date(source.last_poll_success_at).toLocaleString()}`
                          : source.last_poll_completed_at
                            ? `Last attempt ${new Date(source.last_poll_completed_at).toLocaleString()}`
                            : "Not polled yet"}
                        {source.last_poll_error_type ? ` · ${source.last_poll_error_type}` : ""}
                      </small>
                    </div>
                    <span className={`source-status-label ${source.poll_status ?? "unknown"}`}>{source.poll_status ?? "pending"}</span>
                    <span className="source-status-count">{source.last_poll_fetched ?? 0} fetched</span>
                  </div>
                ))}
              </div>
            )}
          </section>

          <section className="source-health-panel" id="saved" aria-label="Saved updates">
            <div className="subscription-heading">
              <div><div className="eyebrow muted">YOUR LIBRARY</div><h2>Saved updates</h2></div>
              <span className="subscription-count">{userStates.filter((item) => item.saved).length} saved</span>
            </div>
            {userStateMessage && <p className="subscription-message" role="status">{userStateMessage}</p>}
            {userStates.filter((item) => item.saved).length === 0 ? (
              <p className="subscription-hint">Save an update from the feed to keep it in your personal library.</p>
            ) : (
              <div className="source-status-list">
                {userStates.filter((item) => item.saved).map((state) => {
                  const update = updates.find((item) => item.update_id === state.update_id);
                  return (
                    <div className="source-status-row" key={state.update_id}>
                      <Bookmark size={15} />
                      <div className="source-status-copy">
                        <strong>{update?.title ?? state.update_id}</strong>
                        <small>{update ? update.technology : "Saved update"}{state.read ? " · Read" : " · Unread"}</small>
                      </div>
                      {update && <a className="hero-link" href={update.canonical_url} target="_blank" rel="noreferrer">Open source <ArrowUpRight size={14} /></a>}
                    </div>
                  );
                })}
              </div>
            )}
          </section>
          <section className="feed-section">
            <div className="section-heading">
              <div><div className="eyebrow muted">{activeWorkspace.label.toUpperCase()} · YOUR FEED</div><h2>{workspaceView === "focus" && selected === "all" ? "Department updates" : "Updates from the past 7 days"} <span className="subtle-count">{visibleUpdates.length}</span></h2></div>
              <div className="feed-controls">
                <label className="search-box"><Search size={16} /><input aria-label="Search updates" placeholder="Search technologies, features..." value={search} onChange={(event) => setSearch(event.target.value)} /><kbd>⌘ K</kbd></label>
                <button className="filter-button" onClick={() => setSelected("all")}>All updates <ChevronDown size={14} /></button>
              </div>
            </div>
            {refreshMessage && <p className="subscription-message" role="status">{refreshMessage}</p>}
            <div className="technology-filters" id="technologies">
              <button className={selected === "all" ? "filter-chip active" : "filter-chip"} onClick={() => setSelected("all")}>All technologies</button>
              {technologies.filter((technology) => workspaceView === "shared" || activeWorkspace.technologies.includes(technology.id)).map((technology) => <button key={technology.id} className={selected === technology.id ? "filter-chip active" : "filter-chip"} onClick={() => setSelected(technology.id)}>{technology.name}</button>)}
            </div>
            <section className="subscriptions-panel" id="my-technologies">
              <div className="subscription-heading">
                <div><div className="eyebrow muted">PERSONAL ALERTS</div><h2>My technology subscriptions</h2></div>
                <span className="subscription-count">{subscriptions.length} subscribed</span>
              </div>
              {authStatus === "authenticated" ? (
                <div className="subscription-grid">
                  {technologies.map((technology) => {
                    const subscription = subscriptions.find((item) => item.technology_id === technology.id);
                    const busy = subscriptionBusy === technology.id;
                    return (
                      <div className="subscription-row" key={technology.id}>
                        <div className={`subscription-symbol ${technology.id}`}><Boxes size={16} /></div>
                        <div className="subscription-copy"><strong>{technology.name}</strong><small>{subscription ? `Alerts via ${subscription.channel}` : "No alerts configured"}</small></div>
                        <button
                          className={subscription ? "subscription-toggle enabled" : "subscription-toggle"}
                          onClick={() => { void toggleSubscription(technology.id); }}
                          disabled={subscriptionBusy !== null}
                          aria-pressed={Boolean(subscription)}
                        >
                          {busy ? "Saving…" : subscription ? "Subscribed" : "Email alerts"}
                        </button>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="subscription-hint">Sign in to manage email alerts for the technologies you follow.</p>
              )}
              {subscriptionMessage && <p className="subscription-message" role="status">{subscriptionMessage}</p>}
            </section>
            {error && <div className="inline-notice"><CircleAlert size={16} /> {error}</div>}
            {loading && <div className="loading-row">Connecting to TechPulse API<span className="loading-dots">•••</span></div>}
            <div className="updates-list">
              {visibleUpdates.map((update) => (
                <article className="update-card" key={update.update_id}>
                  <div className={`update-provider ${update.technology.toLowerCase().replace(/[^a-z0-9]/g, "")}`}><Workflow size={20} /></div>
                  <div className="update-main">
                    <div className="update-meta"><span>{update.technology}</span><span className="meta-dot">•</span><span>{update.category}</span><span className="meta-dot">•</span><time>{new Date(update.published_at ?? Date.now()).toLocaleDateString()}</time></div>
                    <h3>{update.title}</h3>
                    <p>{update.summary}</p>
                    {(update.relevance_topics?.[activeWorkspace.id] ?? []).length > 0 && (
                      <div className="relevance-tags" aria-label="Why this update is relevant to the active workspace">
                        <span className="relevance-tags-label">MATCHED</span>
                        {(update.relevance_topics?.[activeWorkspace.id] ?? []).slice(0, 4).map((topic) => (
                          <span className="relevance-tag" key={topic}>{topic}</span>
                        ))}
                      </div>
                    )}
                    <div className="update-footer">
                      <span className={`priority priority-${update.priority}`}>{priorityLabel(update.priority)} priority</span>
                      <span className="verified-label"><ShieldCheck size={13} /> Source linked</span>
                      {authStatus === "authenticated" && (() => {
                        const state = userStates.find((item) => item.update_id === update.update_id);
                        return (
                          <>
                            <button className={state?.saved ? "update-state-button active" : "update-state-button"} onClick={() => { void changeUserState(update.update_id, { saved: !state?.saved }); }} aria-pressed={Boolean(state?.saved)}>
                              <Bookmark size={13} /> {state?.saved ? "Saved" : "Save"}
                            </button>
                            <button className={state?.read ? "update-state-button active" : "update-state-button"} onClick={() => { void changeUserState(update.update_id, { read: !state?.read }); }} aria-pressed={Boolean(state?.read)}>
                              {state?.read ? "Read" : "Mark read"}
                            </button>
                          </>
                        );
                      })()}
                    </div>
                  </div>
                  <a className="open-update" href={update.canonical_url} target="_blank" rel="noreferrer" aria-label="Open original announcement"><ArrowUpRight size={17} /></a>
                </article>
              ))}
              {!loading && visibleUpdates.length === 0 && <div className="empty-state"><Search size={22} /><strong>No real updates found in the past 7 days</strong><span>Use Refresh updates, then check Source polling status for failed or empty feeds. TechPulse won't show a placeholder as a real announcement.</span></div>}
            </div>
            <div className="feed-end"><span /> YOU'RE ALL CAUGHT UP <span /></div>
          </section>

          <footer className="footer"><span>TechPulse <b>·</b> Release intelligence for engineering teams</span><span>Sources first. Signal over noise.</span></footer>
        </div>
      </main>
    </div>
  );
}

function StatCard({ icon, label, value, detail, color }: { icon: React.ReactNode; label: string; value: string; detail: string; color: string }) {
  return <div className="stat-card"><div className={`stat-icon ${color}`}>{icon}</div><div className="stat-label">{label}</div><div className="stat-value">{value}</div><div className="stat-detail">{detail}</div></div>;
}

function AuthScreen({ title, subtitle, error, actionLabel, onAction }: { title: string; subtitle: string; error?: string; actionLabel?: string; onAction?: () => void }) {
  return (
    <main className="auth-screen">
      <div className="auth-card">
        <span className="brand-mark auth-mark"><Activity size={22} /></span>
        <div className="auth-eyebrow">ENGINEERING INTELLIGENCE</div>
        <h1>{title}</h1>
        <p>{subtitle}</p>
        {error && <div className="auth-error">{error}</div>}
        {onAction && actionLabel && <button className="auth-button" onClick={onAction}>{actionLabel}</button>}
        <span className="auth-caption">TechPulse · Cloud & DevOps Release Intelligence</span>
      </div>
    </main>
  );
}
