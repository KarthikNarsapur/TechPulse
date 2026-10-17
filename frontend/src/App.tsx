import { useEffect, useMemo, useState } from "react";
import {
  Activity, ArrowUpRight, Bell, Bookmark, Boxes, ChevronDown,
  CircleAlert, Cloud, Command, GitBranch, LayoutDashboard, Search,
  Settings2, ShieldCheck, Sparkles, Workflow, LogOut,
} from "lucide-react";
import { getTechnologies, getUpdates, type Technology, type Update } from "./api";
import { beginLogin, finishLoginCallback, isAuthConfigured, isRemoteApiConfigured, signOut } from "./auth";

const fallbackUpdates: Update[] = [
  {
    update_id: "demo-1",
    title: "Your engineering update feed starts here",
    technology: "TechPulse",
    category: "Getting started",
    priority: "informational",
    summary: "Connect validated official sources to start collecting release notes, deprecations, security advisories, and product announcements.",
    published_at: new Date().toISOString(),
    canonical_url: "https://github.com/KarthikNarsapur/TechPulse",
  },
];

function priorityLabel(priority: Update["priority"]): string {
  return priority.charAt(0).toUpperCase() + priority.slice(1);
}

export default function App() {
  const [technologies, setTechnologies] = useState<Technology[]>([]);
  const [updates, setUpdates] = useState<Update[]>([]);
  const [selected, setSelected] = useState("all");
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
        if (!cancelled) setError("API unavailable. Showing the preview state.");
      });
    getUpdates(selected === "all" ? undefined : selected)
      .then((updateList) => {
        if (!cancelled) setUpdates(updateList);
      })
      .catch(() => {
        if (!cancelled) setError("Could not load updates for this filter.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [selected, authStatus]);

  const visibleUpdates = useMemo(() => {
    const dataset = updates.length > 0 ? updates : fallbackUpdates;
    return dataset.filter((update) => {
      const technologyMatches = selected === "all" || update.technology.toLowerCase() === selected;
      const searchMatches = `${update.title} ${update.summary ?? "Analysis is pending. Open the official announcement for full details."} ${update.technology} ${update.category}`
        .toLowerCase().includes(search.toLowerCase());
      return technologyMatches && searchMatches;
    });
  }, [updates, selected, search]);

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
        <div className="workspace-card"><span className="workspace-dot" /> Platform Engineering <span className="workspace-caret">⌄</span></div>
        <nav className="navigation" aria-label="Main navigation">
          <span className="nav-section">DISCOVER</span>
          <a className="nav-link active" href="#updates"><LayoutDashboard size={17} /> Overview <span className="nav-count">01</span></a>
          <a className="nav-link" href="#updates"><Search size={17} /> All updates</a>
          <a className="nav-link" href="#technologies"><Boxes size={17} /> My technologies</a>
          <a className="nav-link" href="#saved"><Bookmark size={17} /> Saved updates</a>
          <span className="nav-section spaced">YOUR STACK</span>
          {technologies.map((technology) => (
            <button key={technology.id} className={selected === technology.id ? "nav-link tech-link selected" : "nav-link tech-link"} onClick={() => setSelected(technology.id)}>
              <span className={`tech-icon ${technology.id}`}>{technology.id === "aws" || technology.id === "azure" || technology.id === "gcp" ? <Cloud size={15} /> : technology.id === "gitlab" ? <GitBranch size={15} /> : <Workflow size={15} />}</span>
              {technology.name}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="sync-card"><span className="sync-pulse" /><div><strong>Source monitoring</strong><small>Registry configured</small></div><ShieldCheck size={16} /></div>
          <button className="nav-link"><Settings2 size={17} /> Settings</button>
          <div className="user-card"><div className="avatar">KN</div><div><strong>Engineering user</strong><small>Cloud & DevOps</small></div><Command size={16} /></div>
        </div>
      </aside>

      <main className="main-content" id="updates">
        <header className="topbar">
          <div className="breadcrumbs">Workspace <span>/</span> <strong>Overview</strong></div>
          <div className="top-actions">
            <div className="status-pill"><span /> Serverless pilot</div>
            <button className="icon-button" aria-label="Notifications"><Bell size={18} /><i /></button>
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
            <button className="date-button"><Activity size={15} /> Live overview <ChevronDown size={14} /></button>
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

          <section className="feed-section">
            <div className="section-heading">
              <div><div className="eyebrow muted">YOUR FEED</div><h2>Latest updates <span className="subtle-count">{visibleUpdates.length}</span></h2></div>
              <div className="feed-controls">
                <label className="search-box"><Search size={16} /><input aria-label="Search updates" placeholder="Search technologies, features..." value={search} onChange={(event) => setSearch(event.target.value)} /><kbd>⌘ K</kbd></label>
                <button className="filter-button" onClick={() => setSelected("all")}>All updates <ChevronDown size={14} /></button>
              </div>
            </div>
            <div className="technology-filters" id="technologies">
              <button className={selected === "all" ? "filter-chip active" : "filter-chip"} onClick={() => setSelected("all")}>All technologies</button>
              {technologies.map((technology) => <button key={technology.id} className={selected === technology.id ? "filter-chip active" : "filter-chip"} onClick={() => setSelected(technology.id)}>{technology.name}</button>)}
            </div>
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
                    <div className="update-footer"><span className={`priority priority-${update.priority}`}>{priorityLabel(update.priority)} priority</span><span className="verified-label"><ShieldCheck size={13} /> Source linked</span></div>
                  </div>
                  <a className="open-update" href={update.canonical_url} target="_blank" rel="noreferrer" aria-label="Open original announcement"><ArrowUpRight size={17} /></a>
                </article>
              ))}
              {!loading && visibleUpdates.length === 0 && <div className="empty-state"><Search size={22} /><strong>No updates found</strong><span>Try another search or technology filter.</span></div>}
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
