"use client";

import { useState, useRef, useEffect, useCallback } from "react";

const API_BASE = "http://localhost:8000";

type Message = { role: "user" | "assistant"; content: string };

type SprintInfo = {
  number: number;
  name: string;
  status: "pending" | "in_progress" | "completed";
};

type PipelineStatus = {
  session_id: string;
  is_planning: boolean;
  current_sprint: number;
  total_sprints: number;
  sprints: SprintInfo[];
};

type JiraIssue = {
  id: string;
  title: string;
  status: string;
  role: string;
};

/* ── Field display config ─────────────────────────────────────────────── */

const FIELD_LABELS: Record<string, string> = {
  org_name: "Organization Name",
  mission: "Mission",
  vision: "Vision",
  about: "About",
  target_audience: "Who They Serve",
  values: "Core Values",
  tone_impression: "Brand Tone",
  year_founded: "Year Founded",
  location: "Location",
  website_url: "Website",
  contact_info: "Contact Info",
  financials_summary: "Financials",
};

/* ── Helpers ──────────────────────────────────────────────────────────── */

function formatValue(val: any): string {
  if (val === null || val === undefined || val === "") return "—";
  if (Array.isArray(val)) {
    if (val.length === 0) return "—";
    if (typeof val[0] === "object") return JSON.stringify(val);
    return val.join(", ");
  }
  return String(val);
}

/* ── Editable Field Component ─────────────────────────────────────────── */

function EditableField({
  label,
  value,
  fieldKey,
  onSave,
  onDelete,
}: {
  label: string;
  value: any;
  fieldKey: string;
  onSave: (key: string, val: string) => void;
  onDelete: (key: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(typeof value === "string" ? value : JSON.stringify(value));

  const displayVal = formatValue(value);
  if (displayVal === "—" && !editing) return null;

  return (
    <div className="group flex items-start gap-3 py-2.5 border-b border-stone-800/50 last:border-0">
      <div className="flex-1 min-w-0">
        <div className="text-[11px] font-medium text-stone-500 uppercase tracking-wider mb-0.5">{label}</div>
        {editing ? (
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={2}
            className="w-full bg-stone-900 border border-stone-700 rounded-lg px-3 py-2 text-sm text-stone-200 focus:border-teal-500 focus:ring-1 focus:ring-teal-500/30 outline-none resize-y"
          />
        ) : (
          <div className="text-sm text-stone-200 leading-relaxed">{displayVal}</div>
        )}
      </div>
      <div className="flex items-center gap-1 pt-3 opacity-0 group-hover:opacity-100 transition-opacity">
        {editing ? (
          <>
            <button
              onClick={() => { onSave(fieldKey, draft); setEditing(false); }}
              className="p-1 text-teal-400 hover:text-teal-300"
              title="Save"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </button>
            <button
              onClick={() => setEditing(false)}
              className="p-1 text-stone-500 hover:text-stone-300"
              title="Cancel"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </>
        ) : (
          <>
            <button
              onClick={() => { setDraft(typeof value === "string" ? value : JSON.stringify(value)); setEditing(true); }}
              className="p-1 text-stone-600 hover:text-stone-300"
              title="Edit"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
            </button>
            <button
              onClick={() => onDelete(fieldKey)}
              className="p-1 text-stone-600 hover:text-red-400"
              title="Remove"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          </>
        )}
      </div>
    </div>
  );
}

/* ── Array Section ────────────────────────────────────────────────────── */

function ArraySection({
  title,
  items,
  fieldKey,
  onSave,
  onDelete,
}: {
  title: string;
  items: any[];
  fieldKey: string;
  onSave: (key: string, val: string) => void;
  onDelete: (key: string) => void;
}) {
  if (!items || items.length === 0) return null;

  return (
    <div className="mb-4">
      <div className="flex items-center justify-between mb-2">
        <h4 className="text-[11px] font-bold text-teal-500 uppercase tracking-wider">{title}</h4>
        <button
          onClick={() => onDelete(fieldKey)}
          className="text-stone-600 hover:text-red-400 p-1 opacity-0 group-hover:opacity-100"
          title="Remove all"
        >
          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
      <div className="space-y-1.5">
        {items.map((item: any, i: number) => (
          <div key={i} className="bg-stone-900/60 rounded-lg px-3 py-2 text-sm">
            {typeof item === "string" ? (
              <span className="text-stone-300">{item}</span>
            ) : (
              <div>
                <span className="text-stone-200 font-medium">{item.name || item.label || item.page_name}</span>
                {(item.description || item.value || item.role || item.reason) && (
                  <span className="text-stone-500 ml-1.5">
                    — {item.description || item.value || item.role || item.reason}
                  </span>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── Sprint Timeline ──────────────────────────────────────────────────── */

function SprintTimeline({
  sprints,
  currentSprint,
  totalSprints,
  isPlanning,
}: {
  sprints: SprintInfo[];
  currentSprint: number;
  totalSprints: number;
  isPlanning: boolean;
}) {
  // While planning, render placeholder nodes
  const nodes = isPlanning || sprints.length === 0
    ? Array.from({ length: totalSprints || 4 }, (_, i) => ({
        number: i + 1,
        name: `Sprint ${i + 1}`,
        status: "pending" as const,
      }))
    : sprints;

  return (
    <div className="relative flex items-center justify-between px-6 py-5">
      {/* Connecting line */}
      <div className="absolute left-6 right-6 top-1/2 -translate-y-1/2 h-px bg-stone-800" />

      {nodes.map((sprint, i) => {
        const isDone = sprint.status === "completed";
        const isActive = sprint.status === "in_progress" || sprint.number === currentSprint;
        const isPending = !isDone && !isActive;

        return (
          <div key={i} className="relative flex flex-col items-center gap-2 z-10">
            {/* Node */}
            <div
              className={`
                w-9 h-9 rounded-full border-2 flex items-center justify-center transition-all duration-500
                ${isDone
                  ? "bg-teal-500 border-teal-500 shadow-[0_0_12px_rgba(20,184,166,0.4)]"
                  : isActive
                  ? "bg-stone-950 border-teal-400 shadow-[0_0_14px_rgba(45,212,191,0.35)]"
                  : "bg-stone-900 border-stone-700"
                }
              `}
            >
              {isDone ? (
                <svg className="w-4 h-4 text-stone-950" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                </svg>
              ) : isActive ? (
                <div className="w-2 h-2 rounded-full bg-teal-400 animate-pulse" />
              ) : (
                <span className="text-[11px] font-semibold text-stone-600">{sprint.number}</span>
              )}
            </div>

            {/* Label */}
            <div className="text-center">
              <div className={`text-[10px] font-semibold uppercase tracking-wider whitespace-nowrap
                ${isDone ? "text-teal-400" : isActive ? "text-stone-200" : "text-stone-600"}`}>
                {isPlanning && isPending ? "—" : sprint.name}
              </div>
              <div className={`text-[9px] mt-0.5 uppercase tracking-wider
                ${isDone ? "text-teal-600" : isActive ? "text-teal-400" : "text-stone-700"}`}>
                {isDone ? "Done" : isActive ? "Active" : "Queued"}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ── Agent Card ───────────────────────────────────────────────────────── */

type AgentRole = "pm" | "backend" | "frontend" | "qa";

const AGENT_META: Record<AgentRole, { label: string; abbr: string; color: string; jiraRole: string }> = {
  pm: {
    label: "Product Manager",
    abbr: "Project Manager",
    color: "violet",
    jiraRole: "", // PM isn't a Jira issue role
  },
  backend: {
    label: "Backend Engineer",
    abbr: "Backend Engineer",
    color: "amber",
    jiraRole: "backend",
  },
  frontend: {
    label: "Frontend Engineer",
    abbr: "Frontend Engineer",
    color: "sky",
    jiraRole: "frontend",
  },
  qa: {
    label: "Integration Tester",
    abbr: "QA Tester",
    color: "rose",
    jiraRole: "tester",
  },
};

const colorMap: Record<string, { ring: string; bg: string; text: string; dot: string; badge: string }> = {
  violet: {
    ring: "border-violet-500/50",
    bg: "bg-violet-500/10",
    text: "text-violet-400",
    dot: "bg-violet-400",
    badge: "bg-violet-500/20 text-violet-300",
  },
  amber: {
    ring: "border-amber-500/50",
    bg: "bg-amber-500/10",
    text: "text-amber-400",
    dot: "bg-amber-400",
    badge: "bg-amber-500/20 text-amber-300",
  },
  sky: {
    ring: "border-sky-500/50",
    bg: "bg-sky-500/10",
    text: "text-sky-400",
    dot: "bg-sky-400",
    badge: "bg-sky-500/20 text-sky-300",
  },
  rose: {
    ring: "border-rose-500/50",
    bg: "bg-rose-500/10",
    text: "text-rose-400",
    dot: "bg-rose-400",
    badge: "bg-rose-500/20 text-rose-300",
  },
};

function AgentCard({
  role,
  pipelineStatus,
  issue,
}: {
  role: AgentRole;
  pipelineStatus: PipelineStatus | null;
  issue: JiraIssue | undefined;
}) {
  const meta = AGENT_META[role];
  const c = colorMap[meta.color];

  /* ── Derive PM-specific state ── */
  const getPMState = (): { label: string; sublabel: string; isDone: boolean; isWorking: boolean } => {
    if (!pipelineStatus) return { label: "Initialising…", sublabel: "Starting up", isDone: false, isWorking: true };
    if (pipelineStatus.is_planning) return { label: "Thinking…", sublabel: "Generating sprint plan", isDone: false, isWorking: true };

    const { current_sprint, total_sprints, sprints } = pipelineStatus;
    const currentRecord = sprints.find((s) => s.number === current_sprint);

    if (currentRecord?.status === "in_progress") {
      return { label: "Waiting for team…", sublabel: `Sprint ${current_sprint} in progress`, isDone: false, isWorking: false };
    }
    if (currentRecord?.status === "completed" && current_sprint < total_sprints) {
      return { label: "Reviewing sprint…", sublabel: `Reviewing Sprint ${current_sprint}`, isDone: false, isWorking: true };
    }
    if (current_sprint >= total_sprints && sprints.every((s) => s.status === "completed")) {
      return { label: "All sprints done", sublabel: "Pipeline complete", isDone: true, isWorking: false };
    }
    return { label: "Standby", sublabel: "Waiting for next sprint", isDone: false, isWorking: false };
  };

  /* ── Derive dev agent state ── */
  const getAgentState = (): { title: string; statusLabel: string; isDone: boolean; isWorking: boolean } => {
    if (!issue) {
      return { title: "Waiting for task…", statusLabel: "Idle", isDone: false, isWorking: false };
    }
    const isDone = issue.status.toLowerCase() === "done";
    return {
      title: issue.title,
      statusLabel: isDone ? "Done" : issue.status,
      isDone,
      isWorking: !isDone,
    };
  };

  const isPM = role === "pm";
  const pmState = isPM ? getPMState() : null;
  const agentState = !isPM ? getAgentState() : null;

  const isDone = isPM ? pmState!.isDone : agentState!.isDone;
  const isWorking = isPM ? pmState!.isWorking : agentState!.isWorking;
  const title = isPM ? pmState!.label : agentState!.title;
  const sublabel = isPM ? pmState!.sublabel : agentState!.statusLabel;

  return (
    <div className={`
      relative rounded-2xl border p-5 flex flex-col gap-4 overflow-hidden
      transition-all duration-300
      ${isDone
        ? "border-stone-700 bg-stone-900/40"
        : isWorking
        ? `${c.ring} ${c.bg}`
        : "border-stone-800 bg-stone-900/30"
      }
    `}>
      {/* Subtle glow when working */}
      {isWorking && (
        <div className={`absolute inset-0 opacity-5 rounded-2xl ${c.dot}`}
          style={{ background: `radial-gradient(ellipse at top left, currentColor 0%, transparent 70%)` }} />
      )}

      {/* Header row */}
      <div className="flex items-center justify-between relative">
        {/* Avatar */}
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center font-bold text-sm
          ${isDone ? "bg-stone-800 text-stone-400" : isWorking ? `${c.bg} ${c.text}` : "bg-stone-800/60 text-stone-500"}`}>
          {meta.abbr}
        </div>

        {/* Status indicator */}
        <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-semibold uppercase tracking-wider
          ${isDone
            ? "bg-teal-500/15 text-teal-400"
            : isWorking
            ? `${c.badge}`
            : "bg-stone-800/60 text-stone-500"
          }`}>
          {isDone ? (
            <>
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
              </svg>
              Done
            </>
          ) : isWorking ? (
            <>
              <div className={`w-1.5 h-1.5 rounded-full ${c.dot} animate-pulse`} />
              Working
            </>
          ) : (
            <>
              <div className="w-1.5 h-1.5 rounded-full bg-stone-600" />
              Idle
            </>
          )}
        </div>
      </div>

      {/* Agent name */}
      <div>
        <div className={`text-[10px] font-semibold uppercase tracking-widest mb-0.5
          ${isWorking ? c.text : "text-stone-600"}`}>
          {meta.label}
        </div>

        {/* Task title */}
        <div className={`text-sm font-medium leading-snug
          ${isDone ? "text-stone-400" : isWorking ? "text-stone-100" : "text-stone-500"}`}>
          {title}
        </div>

        {/* Sub-label */}
        {sublabel && (
          <div className="text-[11px] text-stone-600 mt-1">{sublabel}</div>
        )}
      </div>
    </div>
  );
}

/* ── Pipeline Screen ──────────────────────────────────────────────────── */

function PipelineScreen({
  sessionId,
  orgName,
}: {
  sessionId: string;
  orgName: string;
}) {
  const [pipelineStatus, setPipelineStatus] = useState<PipelineStatus | null>(null);
  const [jiraIssues, setJiraIssues] = useState<JiraIssue[]>([]);

  useEffect(() => {
    let alive = true;

    const poll = async () => {
      try {
        const [statusRes, issuesRes] = await Promise.all([
          fetch(`${API_BASE}/pipeline/status/${sessionId}`),
          fetch(`${API_BASE}/jira/sprint-issues`),
        ]);
        const statusData = await statusRes.json();
        const issuesData = await issuesRes.json();
        if (alive && !statusData.error) setPipelineStatus(statusData);
        if (alive && !issuesData.error) setJiraIssues(issuesData.issues || []);
      } catch {
        /* silently retry next tick */
      }
    };

    poll();
    const interval = setInterval(poll, 5000);
    return () => {
      alive = false;
      clearInterval(interval);
    };
  }, [sessionId]);

  const getIssueForRole = (jiraRole: string): JiraIssue | undefined =>
    jiraRole ? jiraIssues.find((i) => i.role === jiraRole) : undefined;

  const allDone =
    pipelineStatus &&
    !pipelineStatus.is_planning &&
    pipelineStatus.total_sprints > 0 &&
    pipelineStatus.current_sprint >= pipelineStatus.total_sprints &&
    pipelineStatus.sprints.every((s) => s.status === "completed");

  return (
    <div className="min-h-screen bg-stone-950 flex flex-col"
      style={{ fontFamily: "'DM Sans', system-ui, sans-serif" }}>
      <style>{`@import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=DM+Sans:wght@300;400;500;600;700&display=swap');`}</style>

      {/* Top bar */}
      <header className="flex items-center justify-between px-8 py-4 border-b border-stone-800/70">
        <div>
          <div className="text-teal-500 text-[10px] font-bold tracking-[0.3em] uppercase mb-0.5">AgileGPT</div>
          <h1 className="text-stone-100 text-sm font-semibold">
            {orgName} — Pipeline Running
          </h1>
        </div>

        {allDone ? (
          <div className="flex items-center gap-2 px-3 py-1.5 bg-teal-500/15 border border-teal-500/30 rounded-lg">
            <div className="w-2 h-2 rounded-full bg-teal-400" />
            <span className="text-teal-300 text-xs font-semibold">All sprints complete</span>
          </div>
        ) : (
          <div className="flex items-center gap-2 px-3 py-1.5 bg-stone-800/60 border border-stone-700/50 rounded-lg">
            <div className="w-2 h-2 rounded-full bg-teal-400 animate-pulse" />
            <span className="text-stone-400 text-xs font-medium">
              {pipelineStatus?.is_planning
                ? "Planning sprints…"
                : `Sprint ${pipelineStatus?.current_sprint ?? "—"} of ${pipelineStatus?.total_sprints ?? "—"}`}
            </span>
          </div>
        )}
      </header>

      {/* Timeline */}
      <div className="border-b border-stone-800/70 bg-stone-900/20">
        {pipelineStatus ? (
          <SprintTimeline
            sprints={pipelineStatus.sprints}
            currentSprint={pipelineStatus.current_sprint}
            totalSprints={pipelineStatus.total_sprints}
            isPlanning={pipelineStatus.is_planning}
          />
        ) : (
          /* Skeleton while first poll hasn't returned */
          <div className="flex items-center justify-center gap-3 py-8">
            <div className="w-4 h-4 border-2 border-teal-400 border-t-transparent rounded-full animate-spin" />
            <span className="text-stone-500 text-sm">Fetching pipeline status…</span>
          </div>
        )}
      </div>

      {/* Agent cards — 2×2 grid */}
      <div className="flex-1 p-8">
        <div className="max-w-3xl mx-auto">
          <div className="text-[10px] font-bold text-stone-600 uppercase tracking-widest mb-5">
            Agent Activity
          </div>
          <div className="grid grid-cols-2 gap-4">
            <AgentCard
              role="pm"
              pipelineStatus={pipelineStatus}
              issue={undefined}
            />
            <AgentCard
              role="backend"
              pipelineStatus={pipelineStatus}
              issue={getIssueForRole(AGENT_META.backend.jiraRole)}
            />
            <AgentCard
              role="frontend"
              pipelineStatus={pipelineStatus}
              issue={getIssueForRole(AGENT_META.frontend.jiraRole)}
            />
            <AgentCard
              role="qa"
              pipelineStatus={pipelineStatus}
              issue={getIssueForRole(AGENT_META.qa.jiraRole)}
            />
          </div>

          {/* Polling indicator */}
          <div className="flex items-center justify-center gap-2 mt-8 text-stone-700 text-[11px]">
            <div className="w-1.5 h-1.5 rounded-full bg-stone-700 animate-pulse" />
            Refreshing every 5 seconds
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Main Component ───────────────────────────────────────────────────── */

export default function NonprofitExtractor() {
  const [phase, setPhase] = useState<"upload" | "processing" | "review" | "pipeline" | "done">("upload");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [profile, setProfile] = useState<Record<string, any>>({});
  const [questions, setQuestions] = useState<string[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [pmContext, setPmContext] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [isConfirming, setIsConfirming] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  /* ── Upload & extract ─────────────────────────────────────────────── */

  const startExtraction = async (file: File) => {
    setPhase("processing");
    setIsLoading(true);

    try {
      const form = new FormData();
      form.append("annual_report", file);
      const res = await fetch(`${API_BASE}/session/new`, { method: "POST", body: form });
      const data = await res.json();

      if (data.error) {
        alert(data.error);
        setPhase("upload");
        return;
      }

      setSessionId(data.session_id);
      setProfile(data.profile);
      setQuestions(data.questions || []);
      setMessages([{ role: "assistant", content: data.greeting }]);
      setPhase("review");
    } catch (err) {
      console.error(err);
      alert("Failed to process the report. Please try again.");
      setPhase("upload");
    } finally {
      setIsLoading(false);
    }
  };

  /* ── Chat ──────────────────────────────────────────────────────────── */

  const sendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || !sessionId || isLoading) return;
    const userMsg = input.trim();
    setInput("");
    setMessages((p) => [...p, { role: "user", content: userMsg }]);
    setIsLoading(true);

    try {
      const res = await fetch(`${API_BASE}/session/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, message: userMsg }),
      });
      const data = await res.json();
      if (data.reply) setMessages((p) => [...p, { role: "assistant", content: data.reply }]);
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  /* ── Profile editing ──────────────────────────────────────────────── */

  const saveField = async (key: string, value: string) => {
    let parsed: any = value;
    try {
      const attempt = JSON.parse(value);
      if (typeof attempt === "object") parsed = attempt;
    } catch { /* keep as string */ }

    const updated = { ...profile, [key]: parsed };
    setProfile(updated);

    if (sessionId) {
      try {
        await fetch(`${API_BASE}/session/${sessionId}/profile`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ [key]: parsed }),
        });
      } catch (err) {
        console.error("Failed to sync edit:", err);
      }
    }
  };

  const deleteField = async (key: string) => {
    const updated = { ...profile };
    delete updated[key];
    setProfile(updated);

    if (sessionId) {
      try {
        await fetch(`${API_BASE}/session/${sessionId}/profile`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ [key]: null }),
        });
      } catch (err) {
        console.error("Failed to sync delete:", err);
      }
    }
  };

  /* ── Confirm & handoff ────────────────────────────────────────────── */

  const confirmAndHandoff = async () => {
    if (!sessionId) return;
    setIsConfirming(true);
    try {
      const res = await fetch(`${API_BASE}/session/${sessionId}/confirm`, { method: "POST" });
      const data = await res.json();
      if (data.pm_context) {
        setPmContext(data.pm_context);
        // Transition to pipeline phase — the background thread is now running
        setPhase("pipeline");
      }
    } catch (err) {
      console.error(err);
    } finally {
      setIsConfirming(false);
    }
  };

  /* ── Drop handler ─────────────────────────────────────────────────── */

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file?.type === "application/pdf") setUploadedFile(file);
  }, []);

  // ═══════════════════════════════════════════════════════════════════════
  // RENDER
  // ═══════════════════════════════════════════════════════════════════════

  const fonts = `@import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=DM+Sans:wght@300;400;500;600;700&display=swap');`;

  /* ── PIPELINE SCREEN ──────────────────────────────────────────────── */

  if (phase === "pipeline" && sessionId) {
    return (
      <PipelineScreen
        sessionId={sessionId}
        orgName={profile.org_name || "Nonprofit"}
      />
    );
  }

  /* ── UPLOAD SCREEN ────────────────────────────────────────────────── */

  if (phase === "upload") {
    return (
      <div className="min-h-screen bg-stone-950 flex items-center justify-center p-8"
        style={{ fontFamily: "'DM Sans', system-ui, sans-serif" }}>
        <style>{fonts}</style>

        <div className="w-full max-w-md">
          <div className="mb-10">
            <div className="text-teal-500 text-xs font-semibold tracking-[0.3em] uppercase mb-3">
              AgileGPT
            </div>
            <h1 style={{ fontFamily: "'Instrument Serif', serif" }}
              className="text-4xl text-stone-100 leading-tight mb-3">
              Nonprofit <em className="text-teal-400">Data Engineer</em>
            </h1>
            <p className="text-stone-500 text-sm leading-relaxed max-w-sm">
              Upload an annual report. We'll extract everything we can about the
              organization and prepare it for the PM.
            </p>
          </div>

          <div
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-xl p-10 cursor-pointer transition-all mb-4 ${
              dragOver ? "border-teal-400 bg-teal-400/5"
                : uploadedFile ? "border-emerald-500 bg-emerald-500/5"
                : "border-stone-800 bg-stone-900/30 hover:border-stone-600"
            }`}
          >
            <input ref={fileInputRef} type="file" accept=".pdf" className="hidden"
              onChange={(e) => setUploadedFile(e.target.files?.[0] ?? null)} />

            {uploadedFile ? (
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-emerald-500/20 flex items-center justify-center">
                  <svg className="w-5 h-5 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <div>
                  <p className="text-emerald-400 font-medium text-sm">{uploadedFile.name}</p>
                  <p className="text-stone-600 text-xs mt-0.5">{(uploadedFile.size / 1024).toFixed(0)} KB</p>
                </div>
              </div>
            ) : (
              <div className="text-center">
                <div className="w-12 h-12 rounded-xl bg-stone-800 flex items-center justify-center mx-auto mb-3">
                  <svg className="w-6 h-6 text-stone-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                  </svg>
                </div>
                <p className="text-stone-300 text-sm font-medium">Drop annual report here</p>
                <p className="text-stone-600 text-xs mt-1">PDF format</p>
              </div>
            )}
          </div>

          <button
            onClick={() => uploadedFile && startExtraction(uploadedFile)}
            disabled={!uploadedFile}
            className="w-full py-3.5 rounded-xl font-semibold text-sm transition-all bg-teal-500 text-stone-950 hover:bg-teal-400 disabled:opacity-30 disabled:cursor-not-allowed active:scale-[0.98]"
          >
            Extract & Analyse →
          </button>
        </div>
      </div>
    );
  }

  /* ── PROCESSING SCREEN ────────────────────────────────────────────── */

  if (phase === "processing") {
    return (
      <div className="min-h-screen bg-stone-950 flex items-center justify-center"
        style={{ fontFamily: "'DM Sans', system-ui, sans-serif" }}>
        <style>{fonts}</style>
        <div className="text-center">
          <div className="w-12 h-12 border-2 border-teal-400 border-t-transparent rounded-full animate-spin mx-auto mb-6" />
          <p className="text-stone-300 font-medium">Reading annual report…</p>
          <p className="text-stone-600 text-sm mt-1">Extracting organization details</p>
        </div>
      </div>
    );
  }

  /* ── DONE SCREEN (PM Context) ─────────────────────────────────────── */

  if (phase === "done" && pmContext) {
    return (
      <div className="min-h-screen bg-stone-950 flex items-center justify-center p-8"
        style={{ fontFamily: "'DM Sans', system-ui, sans-serif" }}>
        <style>{fonts}</style>
        <div className="w-full max-w-2xl">
          <div className="mb-8 text-center">
            <div className="w-14 h-14 rounded-full bg-emerald-500/20 flex items-center justify-center mx-auto mb-4">
              <svg className="w-7 h-7 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <h2 style={{ fontFamily: "'Instrument Serif', serif" }}
              className="text-2xl text-stone-100 mb-2">
              Ready for the PM
            </h2>
            <p className="text-stone-500 text-sm">
              This context block will be sent to the Product Manager agent.
            </p>
          </div>

          <div className="bg-stone-900 border border-stone-800 rounded-xl p-6 mb-6">
            <div className="text-[10px] font-bold text-teal-500 uppercase tracking-wider mb-3">PM Context</div>
            <div className="text-sm text-stone-300 leading-relaxed whitespace-pre-wrap">
              {pmContext}
            </div>
          </div>

          <div className="flex gap-3">
            <button
              onClick={() => { navigator.clipboard.writeText(pmContext); }}
              className="flex-1 py-3 bg-stone-800 hover:bg-stone-700 text-stone-300 text-sm font-medium rounded-xl transition-colors"
            >
              Copy to Clipboard
            </button>
            <button
              onClick={() => {
                const blob = new Blob([pmContext], { type: "text/plain" });
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a"); a.href = url;
                a.download = `${profile.org_name || "nonprofit"}-pm-context.txt`;
                a.click();
              }}
              className="flex-1 py-3 bg-teal-500 hover:bg-teal-400 text-stone-950 text-sm font-semibold rounded-xl transition-colors"
            >
              Download .txt
            </button>
          </div>

          <button
            onClick={() => { setPhase("upload"); setProfile({}); setPmContext(null); setMessages([]); setSessionId(null); }}
            className="w-full mt-3 py-2.5 text-stone-600 hover:text-stone-400 text-xs transition-colors"
          >
            Start over with a new report
          </button>
        </div>
      </div>
    );
  }

  /* ── REVIEW SCREEN (Chat + Profile Panel) ─────────────────────────── */

  const scalarFields = Object.entries(profile).filter(
    ([_, v]) => typeof v === "string" || typeof v === "number" || typeof v === "boolean" || v === null
  );
  const arrayFields = Object.entries(profile).filter(
    ([_, v]) => Array.isArray(v) && v.length > 0
  );

  return (
    <div className="flex h-screen bg-stone-950 overflow-hidden"
      style={{ fontFamily: "'DM Sans', system-ui, sans-serif" }}>
      <style>{`
        ${fonts}
        * { box-sizing: border-box; }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #44403c; border-radius: 2px; }
      `}</style>

      {/* ── LEFT: Chat ──────────────────────────────────────────────── */}
      <div className="flex flex-col h-full flex-1 min-w-0 border-r border-stone-800">

        {/* Header */}
        <header className="flex items-center justify-between px-5 py-3.5 border-b border-stone-800 bg-stone-950 flex-shrink-0">
          <div>
            <div className="text-stone-100 text-sm font-semibold">
              {profile.org_name || "Review Findings"}
            </div>
            <div className="text-stone-600 text-[11px] mt-0.5">
              Review, edit, or add to the extracted data
            </div>
          </div>
          <button
            onClick={confirmAndHandoff}
            disabled={isConfirming || isLoading}
            className="flex items-center gap-1.5 px-4 py-2 bg-teal-500 hover:bg-teal-400 disabled:opacity-40 text-stone-950 text-xs font-semibold rounded-lg transition-all active:scale-95"
          >
            {isConfirming ? (
              <><div className="w-3 h-3 border border-stone-900 border-t-transparent rounded-full animate-spin" /> Confirming…</>
            ) : (
              "Confirm & Send to PM →"
            )}
          </button>
        </header>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-5 py-6 space-y-4">
          {messages.map((msg, i) => (
            <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
              {msg.role === "assistant" && (
                <div className="w-7 h-7 rounded-full bg-teal-500/20 border border-teal-500/30 flex items-center justify-center flex-shrink-0 mt-0.5 mr-2.5">
                  <span className="text-teal-400 text-xs font-bold">A</span>
                </div>
              )}
              <div className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap ${
                msg.role === "user"
                  ? "bg-stone-800 text-stone-100 rounded-br-sm"
                  : "bg-stone-900 border border-stone-800 text-stone-300 rounded-bl-sm"
              }`}>
                {msg.content}
              </div>
            </div>
          ))}

          {isLoading && (
            <div className="flex justify-start">
              <div className="w-7 h-7 rounded-full bg-teal-500/20 border border-teal-500/30 flex items-center justify-center flex-shrink-0 mt-0.5 mr-2.5">
                <span className="text-teal-400 text-xs font-bold">A</span>
              </div>
              <div className="bg-stone-900 border border-stone-800 rounded-2xl rounded-bl-sm px-4 py-3 flex gap-1 items-center">
                {[0, 1, 2].map((i) => (
                  <div key={i} className="w-1.5 h-1.5 bg-stone-600 rounded-full animate-bounce"
                    style={{ animationDelay: `${i * 0.15}s` }} />
                ))}
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="px-5 py-4 border-t border-stone-800 bg-stone-950 flex-shrink-0">
          <div className="flex gap-2">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(e as any); } }}
              disabled={isLoading}
              placeholder="Edit something, add info, or ask a question…"
              className="flex-1 bg-stone-900 border border-stone-700 focus:border-teal-500 focus:ring-1 focus:ring-teal-500/20 text-stone-200 placeholder-stone-600 rounded-xl px-4 py-3 text-sm outline-none transition-all"
            />
            <button
              onClick={(e) => sendMessage(e as any)}
              disabled={isLoading || !input.trim()}
              className="px-4 py-3 bg-teal-500 hover:bg-teal-400 disabled:opacity-30 text-stone-950 rounded-xl transition-all active:scale-95"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
            </button>
          </div>
        </div>
      </div>

      {/* ── RIGHT: Extracted Profile Panel ─────────────────────────── */}
      <div className="w-[380px] flex-shrink-0 flex flex-col h-full bg-stone-950 overflow-hidden">
        <div className="px-5 py-3.5 border-b border-stone-800 flex-shrink-0">
          <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-teal-500">Extracted Profile</div>
          <div className="text-stone-500 text-[11px] mt-0.5">Hover any field to edit or remove</div>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4">

          {/* Scalar fields */}
          <div className="mb-6">
            {scalarFields.map(([key, val]) => (
              <EditableField
                key={key}
                label={FIELD_LABELS[key] || key.replace(/_/g, " ")}
                value={val}
                fieldKey={key}
                onSave={saveField}
                onDelete={deleteField}
              />
            ))}
          </div>

          {/* Array fields */}
          {arrayFields.map(([key, val]) => (
            <ArraySection
              key={key}
              title={FIELD_LABELS[key] || key.replace(/_/g, " ")}
              items={val as any[]}
              fieldKey={key}
              onSave={saveField}
              onDelete={deleteField}
            />
          ))}

          {/* Clarifying questions badge */}
          {questions.length > 0 && (
            <div className="mt-6 bg-teal-500/10 border border-teal-500/20 rounded-xl p-4">
              <div className="text-[10px] font-bold text-teal-400 uppercase tracking-wider mb-2">
                Questions for you
              </div>
              <ul className="space-y-1.5">
                {questions.map((q, i) => (
                  <li key={i} className="text-xs text-stone-400 leading-relaxed flex gap-2">
                    <span className="text-teal-500 mt-0.5">•</span> {q}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Bottom action */}
        <div className="p-4 border-t border-stone-800 flex-shrink-0">
          <button
            onClick={confirmAndHandoff}
            disabled={isConfirming}
            className="w-full py-3 bg-teal-500 hover:bg-teal-400 disabled:opacity-40 text-stone-950 text-sm font-semibold rounded-xl transition-all active:scale-[0.98]"
          >
            {isConfirming ? "Generating PM Context…" : "✓ Confirm & Send to PM"}
          </button>
        </div>
      </div>
    </div>
  );
}