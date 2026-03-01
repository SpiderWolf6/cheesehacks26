"use client";

import { useState, useRef, useEffect, useCallback } from "react";

const API_BASE = "http://136.119.39.142:8000";

type Theme = "dark" | "light";
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

// ─────────────────────────────────────────────────────────────────────────────
// THEME TOKENS
// ─────────────────────────────────────────────────────────────────────────────

type ThemeTokens = {
  pageBg: string;
  surfaceBg: string;
  surfaceBg2: string;
  inputBg: string;
  border: string;
  borderSubtle: string;
  textPrimary: string;
  textSecondary: string;
  textMuted: string;
  textFaint: string;
  scrollbarThumb: string;
  bubbleUser: string;
  bubbleUserText: string;
  bubbleAssistant: string;
  bubbleAssistantBorder: string;
  bubbleAssistantText: string;
  inputBorder: string;
  inputText: string;
  inputPlaceholder: string;
  copyBtn: string;
  copyBtnHover: string;
  copyBtnText: string;
  timelineLine: string;
  timelineNodePending: string;
  timelineNodePendingBorder: string;
  timelineNodePendingText: string;
  agentCardIdle: string;
  agentCardIdleBorder: string;
  agentCardDone: string;
  agentCardDoneBorder: string;
  dotIdle: string;
  pollingDot: string;
  pollingText: string;
  skeletonText: string;
  toggleBg: string;
  toggleBorder: string;
  toggleText: string;
};

const dark: ThemeTokens = {
  pageBg: "bg-stone-950",
  surfaceBg: "bg-stone-900",
  surfaceBg2: "bg-stone-900/40",
  inputBg: "bg-stone-900",
  border: "border-stone-800",
  borderSubtle: "border-stone-800/50",
  textPrimary: "text-stone-100",
  textSecondary: "text-stone-300",
  textMuted: "text-stone-500",
  textFaint: "text-stone-600",
  scrollbarThumb: "#44403c",
  bubbleUser: "bg-stone-800",
  bubbleUserText: "text-stone-100",
  bubbleAssistant: "bg-stone-900",
  bubbleAssistantBorder: "border-stone-800",
  bubbleAssistantText: "text-stone-300",
  inputBorder: "border-stone-700",
  inputText: "text-stone-200",
  inputPlaceholder: "placeholder-stone-600",
  copyBtn: "bg-stone-800",
  copyBtnHover: "hover:bg-stone-700",
  copyBtnText: "text-stone-300",
  timelineLine: "bg-stone-800",
  timelineNodePending: "bg-stone-900",
  timelineNodePendingBorder: "border-stone-700",
  timelineNodePendingText: "text-stone-600",
  agentCardIdle: "bg-stone-900/30",
  agentCardIdleBorder: "border-stone-800",
  agentCardDone: "bg-stone-900/40",
  agentCardDoneBorder: "border-stone-700",
  dotIdle: "bg-stone-600",
  pollingDot: "bg-stone-700",
  pollingText: "text-stone-700",
  skeletonText: "text-stone-500",
  toggleBg: "bg-stone-800",
  toggleBorder: "border-stone-700",
  toggleText: "text-stone-400",
};

const light: ThemeTokens = {
  pageBg: "bg-stone-50",
  surfaceBg: "bg-white",
  surfaceBg2: "bg-stone-100",
  inputBg: "bg-white",
  border: "border-stone-200",
  borderSubtle: "border-stone-200",
  textPrimary: "text-stone-900",
  textSecondary: "text-stone-700",
  textMuted: "text-stone-500",
  textFaint: "text-stone-400",
  scrollbarThumb: "#d6d3d1",
  bubbleUser: "bg-teal-600",
  bubbleUserText: "text-white",
  bubbleAssistant: "bg-white",
  bubbleAssistantBorder: "border-stone-200",
  bubbleAssistantText: "text-stone-700",
  inputBorder: "border-stone-300",
  inputText: "text-stone-800",
  inputPlaceholder: "placeholder-stone-400",
  copyBtn: "bg-stone-100",
  copyBtnHover: "hover:bg-stone-200",
  copyBtnText: "text-stone-600",
  timelineLine: "bg-stone-200",
  timelineNodePending: "bg-white",
  timelineNodePendingBorder: "border-stone-300",
  timelineNodePendingText: "text-stone-400",
  agentCardIdle: "bg-stone-50",
  agentCardIdleBorder: "border-stone-200",
  agentCardDone: "bg-stone-100",
  agentCardDoneBorder: "border-stone-200",
  dotIdle: "bg-stone-400",
  pollingDot: "bg-stone-300",
  pollingText: "text-stone-400",
  skeletonText: "text-stone-400",
  toggleBg: "bg-white",
  toggleBorder: "border-stone-300",
  toggleText: "text-stone-500",
};

// ─────────────────────────────────────────────────────────────────────────────
// THEME TOGGLE
// ─────────────────────────────────────────────────────────────────────────────

function ThemeToggle({ theme, onToggle, t }: { theme: Theme; onToggle: () => void; t: ThemeTokens }) {
  return (
    <button
      onClick={onToggle}
      className={`w-8 h-8 rounded-lg flex items-center justify-center border transition-all ${t.toggleBg} ${t.toggleBorder} ${t.toggleText} hover:border-teal-500 hover:text-teal-500`}
      title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
    >
      {theme === "dark" ? (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364-6.364l-.707.707M6.343 17.657l-.707.707M17.657 17.657l-.707-.707M6.343 6.343l-.707-.707M12 8a4 4 0 100 8 4 4 0 000-8z" />
        </svg>
      ) : (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z" />
        </svg>
      )}
    </button>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// FIELD LABELS
// ─────────────────────────────────────────────────────────────────────────────

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

function formatValue(val: any): string {
  if (val === null || val === undefined || val === "") return "—";
  if (Array.isArray(val)) {
    if (val.length === 0) return "—";
    if (typeof val[0] === "object") return JSON.stringify(val);
    return val.join(", ");
  }
  return String(val);
}

// ─────────────────────────────────────────────────────────────────────────────
// EDITABLE FIELD
// ─────────────────────────────────────────────────────────────────────────────

function EditableField({
  label, value, fieldKey, onSave, onDelete, t,
}: {
  label: string; value: any; fieldKey: string;
  onSave: (k: string, v: string) => void;
  onDelete: (k: string) => void;
  t: ThemeTokens;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(typeof value === "string" ? value : JSON.stringify(value));
  const displayVal = formatValue(value);
  if (displayVal === "—" && !editing) return null;

  return (
    <div className={`group flex items-start gap-3 py-2.5 border-b ${t.borderSubtle} last:border-0`}>
      <div className="flex-1 min-w-0">
        <div className={`text-[11px] font-medium ${t.textMuted} uppercase tracking-wider mb-0.5`}>{label}</div>
        {editing ? (
          <textarea value={draft} onChange={(e) => setDraft(e.target.value)} rows={2}
            className={`w-full ${t.inputBg} border ${t.inputBorder} rounded-lg px-3 py-2 text-sm ${t.inputText} focus:border-teal-500 focus:ring-1 focus:ring-teal-500/30 outline-none resize-y`} />
        ) : (
          <div className={`text-sm ${t.textSecondary} leading-relaxed`}>{displayVal}</div>
        )}
      </div>
      <div className="flex items-center gap-1 pt-3 opacity-0 group-hover:opacity-100 transition-opacity">
        {editing ? (
          <>
            <button onClick={() => { onSave(fieldKey, draft); setEditing(false); }} className="p-1 text-teal-500 hover:text-teal-400" title="Save">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
            </button>
            <button onClick={() => setEditing(false)} className={`p-1 ${t.textMuted}`} title="Cancel">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
            </button>
          </>
        ) : (
          <>
            <button onClick={() => { setDraft(typeof value === "string" ? value : JSON.stringify(value)); setEditing(true); }} className={`p-1 ${t.textFaint} hover:text-teal-500`} title="Edit">
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" /></svg>
            </button>
            <button onClick={() => onDelete(fieldKey)} className={`p-1 ${t.textFaint} hover:text-red-500`} title="Remove">
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
            </button>
          </>
        )}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// ARRAY SECTION
// ─────────────────────────────────────────────────────────────────────────────

function ArraySection({
  title, items, fieldKey, onSave, onDelete, t,
}: {
  title: string; items: any[]; fieldKey: string;
  onSave: (k: string, v: string) => void;
  onDelete: (k: string) => void;
  t: ThemeTokens;
}) {
  if (!items || items.length === 0) return null;
  return (
    <div className="mb-4">
      <div className="flex items-center justify-between mb-2">
        <h4 className="text-[11px] font-bold text-teal-500 uppercase tracking-wider">{title}</h4>
        <button onClick={() => onDelete(fieldKey)} className={`${t.textFaint} hover:text-red-500 p-1`} title="Remove all">
          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
        </button>
      </div>
      <div className="space-y-1.5">
        {items.map((item: any, i: number) => (
          <div key={i} className={`${t.surfaceBg2} border ${t.border} rounded-lg px-3 py-2 text-sm`}>
            {typeof item === "string" ? (
              <span className={t.textSecondary}>{item}</span>
            ) : (
              <div>
                <span className={`${t.textPrimary} font-medium`}>{item.name || item.label || item.page_name}</span>
                {(item.description || item.value || item.role || item.reason) && (
                  <span className={`${t.textMuted} ml-1.5`}>— {item.description || item.value || item.role || item.reason}</span>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// SPRINT TIMELINE
// ─────────────────────────────────────────────────────────────────────────────

function SprintTimeline({
  sprints, currentSprint, totalSprints, isPlanning, t,
}: {
  sprints: SprintInfo[]; currentSprint: number; totalSprints: number; isPlanning: boolean; t: ThemeTokens;
}) {
  const nodes = isPlanning || sprints.length === 0
    ? Array.from({ length: totalSprints || 4 }, (_, i) => ({ number: i + 1, name: `Sprint ${i + 1}`, status: "pending" as const }))
    : sprints;

  return (
    <div className="relative flex items-center justify-between px-6 py-5">
      <div className={`absolute left-6 right-6 top-1/2 -translate-y-1/2 h-px ${t.timelineLine}`} />
      {nodes.map((sprint, i) => {
        const isDone = sprint.status === "completed";
        const isActive = sprint.status === "in_progress" || sprint.number === currentSprint;
        return (
          <div key={i} className="relative flex flex-col items-center gap-2 z-10">
            <div className={`w-9 h-9 rounded-full border-2 flex items-center justify-center transition-all duration-500
              ${isDone ? "bg-teal-500 border-teal-500 shadow-[0_0_12px_rgba(20,184,166,0.3)]"
                : isActive ? `${t.pageBg} border-teal-400 shadow-[0_0_14px_rgba(45,212,191,0.2)]`
                : `${t.timelineNodePending} ${t.timelineNodePendingBorder}`}`}>
              {isDone ? (
                <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" /></svg>
              ) : isActive ? (
                <div className="w-2 h-2 rounded-full bg-teal-400 animate-pulse" />
              ) : (
                <span className={`text-[11px] font-semibold ${t.timelineNodePendingText}`}>{sprint.number}</span>
              )}
            </div>
            <div className="text-center">
              <div className={`text-[10px] font-semibold uppercase tracking-wider whitespace-nowrap
                ${isDone ? "text-teal-500" : isActive ? t.textPrimary : t.textFaint}`}>
                {isPlanning && sprint.status === "pending" ? "—" : sprint.name}
              </div>
              <div className={`text-[9px] mt-0.5 uppercase tracking-wider
                ${isDone ? "text-teal-400" : isActive ? "text-teal-500" : t.textFaint}`}>
                {isDone ? "Done" : isActive ? "Active" : "Queued"}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// AGENT CARD
// ─────────────────────────────────────────────────────────────────────────────

type AgentRole = "pm" | "backend" | "frontend" | "qa";

const AGENT_META: Record<AgentRole, { label: string; abbr: string; color: string; jiraRole: string }> = {
  pm:       { label: "Product Manager",    abbr: "PM", color: "violet", jiraRole: "" },
  backend:  { label: "Backend Engineer",   abbr: "BE", color: "amber",  jiraRole: "backend" },
  frontend: { label: "Frontend Engineer",  abbr: "FE", color: "sky",    jiraRole: "frontend" },
  qa:       { label: "Integration Tester", abbr: "QA", color: "rose",   jiraRole: "tester" },
};

type AgentColorSet = { ring: string; bg: string; label: string; dot: string; badgeBg: string; badgeText: string; avatarBg: string; avatarText: string };

const agentColorsDark: Record<string, AgentColorSet> = {
  violet: { ring: "border-violet-500/40", bg: "bg-violet-500/10", label: "text-violet-400", dot: "bg-violet-400", badgeBg: "bg-violet-500/20", badgeText: "text-violet-300", avatarBg: "bg-violet-500/15", avatarText: "text-violet-400" },
  amber:  { ring: "border-amber-500/40",  bg: "bg-amber-500/10",  label: "text-amber-400",  dot: "bg-amber-400",  badgeBg: "bg-amber-500/20",  badgeText: "text-amber-300",  avatarBg: "bg-amber-500/15",  avatarText: "text-amber-400" },
  sky:    { ring: "border-sky-500/40",    bg: "bg-sky-500/10",    label: "text-sky-400",    dot: "bg-sky-400",    badgeBg: "bg-sky-500/20",    badgeText: "text-sky-300",    avatarBg: "bg-sky-500/15",    avatarText: "text-sky-400" },
  rose:   { ring: "border-rose-500/40",   bg: "bg-rose-500/10",   label: "text-rose-400",   dot: "bg-rose-400",   badgeBg: "bg-rose-500/20",   badgeText: "text-rose-300",   avatarBg: "bg-rose-500/15",   avatarText: "text-rose-400" },
};

const agentColorsLight: Record<string, AgentColorSet> = {
  violet: { ring: "border-violet-300", bg: "bg-violet-50", label: "text-violet-600", dot: "bg-violet-500", badgeBg: "bg-violet-100", badgeText: "text-violet-700", avatarBg: "bg-violet-100", avatarText: "text-violet-600" },
  amber:  { ring: "border-amber-300",  bg: "bg-amber-50",  label: "text-amber-600",  dot: "bg-amber-500",  badgeBg: "bg-amber-100",  badgeText: "text-amber-700",  avatarBg: "bg-amber-100",  avatarText: "text-amber-600" },
  sky:    { ring: "border-sky-300",    bg: "bg-sky-50",    label: "text-sky-600",    dot: "bg-sky-500",    badgeBg: "bg-sky-100",    badgeText: "text-sky-700",    avatarBg: "bg-sky-100",    avatarText: "text-sky-600" },
  rose:   { ring: "border-rose-300",   bg: "bg-rose-50",   label: "text-rose-600",   dot: "bg-rose-500",   badgeBg: "bg-rose-100",   badgeText: "text-rose-700",   avatarBg: "bg-rose-100",   avatarText: "text-rose-600" },
};

function AgentCard({ role, pipelineStatus, issue, theme, t }: {
  role: AgentRole; pipelineStatus: PipelineStatus | null;
  issue: JiraIssue | undefined; theme: Theme; t: ThemeTokens;
}) {
  const meta = AGENT_META[role];
  const c = (theme === "dark" ? agentColorsDark : agentColorsLight)[meta.color];
  const isPM = role === "pm";

  const getPMState = () => {
    if (!pipelineStatus) return { label: "Initialising…", sublabel: "Starting up", isDone: false, isWorking: true };
    if (pipelineStatus.is_planning) return { label: "Thinking…", sublabel: "Generating sprint plan", isDone: false, isWorking: true };
    const { current_sprint, total_sprints, sprints } = pipelineStatus;
    const cur = sprints.find((s) => s.number === current_sprint);
    if (cur?.status === "in_progress") return { label: "Waiting for team…", sublabel: `Sprint ${current_sprint} in progress`, isDone: false, isWorking: false };
    if (cur?.status === "completed" && current_sprint < total_sprints) return { label: "Reviewing sprint…", sublabel: `Reviewing Sprint ${current_sprint}`, isDone: false, isWorking: true };
    if (current_sprint >= total_sprints && sprints.every((s) => s.status === "completed")) return { label: "All sprints done", sublabel: "Pipeline complete", isDone: true, isWorking: false };
    return { label: "Standby", sublabel: "Waiting for next sprint", isDone: false, isWorking: false };
  };

  const getAgentState = () => {
    if (!issue) return { label: "Waiting for task…", sublabel: "Idle", isDone: false, isWorking: false };
    const isDone = issue.status.toLowerCase() === "done";
    return { label: issue.title, sublabel: isDone ? "Done" : issue.status, isDone, isWorking: !isDone };
  };

  const state = isPM ? getPMState() : getAgentState();
  const { isDone, isWorking } = state;

  return (
    <div className={`relative rounded-2xl border p-5 flex flex-col gap-4 overflow-hidden transition-all duration-300
      ${isDone ? `${t.agentCardDone} ${t.agentCardDoneBorder}` : isWorking ? `${c.ring} ${c.bg}` : `${t.agentCardIdle} ${t.agentCardIdleBorder}`}`}>

      {/* Header row */}
      <div className="flex items-center justify-between">
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center font-bold text-sm
          ${isDone ? `${t.surfaceBg2} ${t.textMuted}` : isWorking ? `${c.avatarBg} ${c.avatarText}` : `${t.surfaceBg2} ${t.textFaint}`}`}>
          {meta.abbr}
        </div>
        <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-semibold uppercase tracking-wider
          ${isDone ? "bg-teal-500/15 text-teal-600" : isWorking ? `${c.badgeBg} ${c.badgeText}` : `${t.surfaceBg2} ${t.textMuted}`}`}>
          {isDone ? (
            <><svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" /></svg>Done</>
          ) : isWorking ? (
            <><div className={`w-1.5 h-1.5 rounded-full ${c.dot} animate-pulse`} />Working</>
          ) : (
            <><div className={`w-1.5 h-1.5 rounded-full ${t.dotIdle}`} />Idle</>
          )}
        </div>
      </div>

      {/* Content */}
      <div>
        <div className={`text-[10px] font-semibold uppercase tracking-widest mb-0.5 ${isWorking ? c.label : t.textFaint}`}>
          {meta.label}
        </div>
        <div className={`text-sm font-medium leading-snug ${isDone ? t.textMuted : isWorking ? t.textPrimary : t.textMuted}`}>
          {state.label}
        </div>
        {state.sublabel && <div className={`text-[11px] ${t.textFaint} mt-1`}>{state.sublabel}</div>}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// PIPELINE SCREEN
// ─────────────────────────────────────────────────────────────────────────────

function PipelineScreen({ sessionId, orgName, theme, onToggleTheme, t }: {
  sessionId: string; orgName: string; theme: Theme; onToggleTheme: () => void; t: ThemeTokens;
}) {
  const [pipelineStatus, setPipelineStatus] = useState<PipelineStatus | null>(null);
  const [jiraIssues, setJiraIssues] = useState<JiraIssue[]>([]);

  useEffect(() => {
    let alive = true;
    const poll = async () => {
      try {
        const [sRes, iRes] = await Promise.all([
          fetch(`${API_BASE}/pipeline/status/${sessionId}`),
          fetch(`${API_BASE}/jira/sprint-issues`),
        ]);
        const s = await sRes.json();
        const ii = await iRes.json();
        if (alive && !s.error) setPipelineStatus(s);
        if (alive && !ii.error) setJiraIssues(ii.issues || []);
      } catch { /* retry next tick */ }
    };
    poll();
    const id = setInterval(poll, 5000);
    return () => { alive = false; clearInterval(id); };
  }, [sessionId]);

  const issueFor = (jiraRole: string) => jiraRole ? jiraIssues.find((i) => i.role === jiraRole) : undefined;
  const allDone = pipelineStatus && !pipelineStatus.is_planning && pipelineStatus.total_sprints > 0
    && pipelineStatus.current_sprint >= pipelineStatus.total_sprints
    && pipelineStatus.sprints.every((s) => s.status === "completed");

  return (
    <div className={`min-h-screen ${t.pageBg} flex flex-col`} style={{ fontFamily: "'DM Sans', system-ui, sans-serif" }}>
      <style>{`@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&display=swap');`}</style>

      {/* Header */}
      <header className={`flex items-center justify-between px-8 py-4 border-b ${t.border}`}>
        <div>
          <div className="text-teal-500 text-[10px] font-bold tracking-[0.3em] uppercase mb-0.5">AgileGPT</div>
          <h1 className={`${t.textPrimary} text-sm font-semibold`}>{orgName} — Pipeline Running</h1>
        </div>
        <div className="flex items-center gap-3">
          {allDone ? (
            <div className="flex items-center gap-2 px-3 py-1.5 bg-teal-500/15 border border-teal-500/30 rounded-lg">
              <div className="w-2 h-2 rounded-full bg-teal-400" />
              <span className="text-teal-600 text-xs font-semibold">All sprints complete</span>
            </div>
          ) : (
            <div className={`flex items-center gap-2 px-3 py-1.5 ${t.surfaceBg2} border ${t.border} rounded-lg`}>
              <div className="w-2 h-2 rounded-full bg-teal-400 animate-pulse" />
              <span className={`${t.textMuted} text-xs font-medium`}>
                {pipelineStatus?.is_planning ? "Planning sprints…"
                  : `Sprint ${pipelineStatus?.current_sprint ?? "—"} of ${pipelineStatus?.total_sprints ?? "—"}`}
              </span>
            </div>
          )}
          <ThemeToggle theme={theme} onToggle={onToggleTheme} t={t} />
        </div>
      </header>

      {/* Timeline */}
      <div className={`border-b ${t.border} ${t.surfaceBg2}`}>
        {pipelineStatus ? (
          <SprintTimeline sprints={pipelineStatus.sprints} currentSprint={pipelineStatus.current_sprint}
            totalSprints={pipelineStatus.total_sprints} isPlanning={pipelineStatus.is_planning} t={t} />
        ) : (
          <div className="flex items-center justify-center gap-3 py-8">
            <div className="w-4 h-4 border-2 border-teal-400 border-t-transparent rounded-full animate-spin" />
            <span className={`${t.skeletonText} text-sm`}>Fetching pipeline status…</span>
          </div>
        )}
      </div>

      {/* Agent cards */}
      <div className="flex-1 p-8">
        <div className="max-w-3xl mx-auto">
          <div className={`text-[10px] font-bold ${t.textFaint} uppercase tracking-widest mb-5`}>Agent Activity</div>
          <div className="grid grid-cols-2 gap-4">
            {(["pm", "backend", "frontend", "qa"] as AgentRole[]).map((role) => (
              <AgentCard key={role} role={role} pipelineStatus={pipelineStatus}
                issue={issueFor(AGENT_META[role].jiraRole)} theme={theme} t={t} />
            ))}
          </div>
          <div className={`flex items-center justify-center gap-2 mt-8 ${t.pollingText} text-[11px]`}>
            <div className={`w-1.5 h-1.5 rounded-full ${t.pollingDot} animate-pulse`} />
            Refreshing every 5 seconds
          </div>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// MAIN COMPONENT
// ─────────────────────────────────────────────────────────────────────────────

export default function NonprofitExtractor() {
  const [theme, setTheme] = useState<Theme>("light");
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

  // Restore persisted theme on mount
  useEffect(() => {
    try {
      const saved = localStorage.getItem("agilegpt-theme") as Theme | null;
      if (saved === "light" || saved === "dark") setTheme(saved);
    } catch { /* SSR / private browsing */ }
  }, []);

  const toggleTheme = useCallback(() => {
    setTheme((prev) => {
      const next: Theme = prev === "dark" ? "light" : "dark";
      try { localStorage.setItem("agilegpt-theme", next); } catch { /* ignore */ }
      return next;
    });
  }, []);

  const t = theme === "dark" ? dark : light;

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  // ── Handlers ────────────────────────────────────────────────────────

  const startExtraction = async (file: File) => {
    setPhase("processing"); setIsLoading(true);
    try {
      const form = new FormData();
      form.append("annual_report", file);
      const res = await fetch(`${API_BASE}/session/new`, { method: "POST", body: form });
      const data = await res.json();
      if (data.error) { alert(data.error); setPhase("upload"); return; }
      setSessionId(data.session_id);
      setProfile(data.profile);
      setQuestions(data.questions || []);
      setMessages([{ role: "assistant", content: data.greeting }]);
      setPhase("review");
    } catch { alert("Failed to process the report. Please try again."); setPhase("upload"); }
    finally { setIsLoading(false); }
  };

  const sendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || !sessionId || isLoading) return;
    const msg = input.trim(); setInput("");
    setMessages((p) => [...p, { role: "user", content: msg }]);
    setIsLoading(true);
    try {
      const res = await fetch(`${API_BASE}/session/chat`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, message: msg }),
      });
      const data = await res.json();
      if (data.reply) setMessages((p) => [...p, { role: "assistant", content: data.reply }]);
    } catch { /* ignore */ }
    finally { setIsLoading(false); }
  };

  const saveField = async (key: string, value: string) => {
    let parsed: any = value;
    try { const a = JSON.parse(value); if (typeof a === "object") parsed = a; } catch { /* string */ }
    setProfile((p) => ({ ...p, [key]: parsed }));
    if (sessionId) try {
      await fetch(`${API_BASE}/session/${sessionId}/profile`, {
        method: "PATCH", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ [key]: parsed }),
      });
    } catch { /* ignore */ }
  };

  const deleteField = async (key: string) => {
    setProfile((p) => { const u = { ...p }; delete u[key]; return u; });
    if (sessionId) try {
      await fetch(`${API_BASE}/session/${sessionId}/profile`, {
        method: "PATCH", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ [key]: null }),
      });
    } catch { /* ignore */ }
  };

  const confirmAndHandoff = async () => {
    if (!sessionId) return;
    setIsConfirming(true);
    try {
      const res = await fetch(`${API_BASE}/session/${sessionId}/confirm`, { method: "POST" });
      const data = await res.json();
      if (data.pm_context) { setPmContext(data.pm_context); setPhase("pipeline"); }
    } catch { /* ignore */ }
    finally { setIsConfirming(false); }
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault(); setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file?.type === "application/pdf") setUploadedFile(file);
  }, []);

  // ═══════════════════════════════════════════════════════════════════
  // RENDER
  // ═══════════════════════════════════════════════════════════════════

  const fonts = `@import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=DM+Sans:wght@300;400;500;600;700&display=swap');`;

  // ── PIPELINE ─────────────────────────────────────────────────────────

  if (phase === "pipeline" && sessionId) {
    return <PipelineScreen sessionId={sessionId} orgName={profile.org_name || "Nonprofit"}
      theme={theme} onToggleTheme={toggleTheme} t={t} />;
  }

  // ── UPLOAD ────────────────────────────────────────────────────────────

  if (phase === "upload") return (
    <div className={`min-h-screen ${t.pageBg} flex items-center justify-center p-8 relative`}
      style={{ fontFamily: "'DM Sans', system-ui, sans-serif" }}>
      <style>{fonts}</style>
      <div className="absolute top-4 right-4"><ThemeToggle theme={theme} onToggle={toggleTheme} t={t} /></div>

      <div className="w-[min(88vw,52rem)]">
        <div className="mb-12">
          <div className="flex items-center justify-start gap-3 mb-5">
            <img
              src="/aa_logo_icon.png"
              alt="AgileGPT logo icon"
              className="w-14 h-auto object-contain shrink-0"
            />
            <img
              src="/aa_logo_text.png"
              alt="AgileGPT"
              className="w-64 h-auto object-contain"
            />
          </div>
          <h1 style={{ fontFamily: "'Instrument Serif', serif" }} className={`text-6xl md:text-7xl ${t.textPrimary} leading-[1.05] mb-6`}>
            Nonprofit <em className="text-teal-500">AI Development Team</em>
          </h1>
          <p className={`${t.textMuted} text-lg leading-relaxed max-w-xl`}>
            Upload an annual report. We'll extract everything we can about the organization and prepare it for the project manager.
          </p>
        </div>

        <div
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`border-2 border-dashed rounded-xl p-12 md:p-14 min-h-[18rem] flex items-center justify-center cursor-pointer transition-all mb-6
            ${dragOver ? "border-teal-400 bg-teal-400/5"
              : uploadedFile ? "border-emerald-400 bg-emerald-400/5"
              : `${t.border} ${t.surfaceBg2} hover:border-teal-400/60`}`}>
          <input ref={fileInputRef} type="file" accept=".pdf" className="hidden"
            onChange={(e) => setUploadedFile(e.target.files?.[0] ?? null)} />
          {uploadedFile ? (
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-emerald-500/15 flex items-center justify-center">
                <svg className="w-5 h-5 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <div>
                <p className="text-emerald-500 font-medium text-sm">{uploadedFile.name}</p>
                <p className={`${t.textFaint} text-xs mt-0.5`}>{(uploadedFile.size / 1024).toFixed(0)} KB</p>
              </div>
            </div>
          ) : (
            <div className="text-center">
              <div className={`w-12 h-12 rounded-xl ${t.surfaceBg} border ${t.border} flex items-center justify-center mx-auto mb-3`}>
                <svg className={`w-6 h-6 ${t.textFaint}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
              </div>
              <p className={`${t.textSecondary} text-sm font-medium`}>Drop annual report here</p>
              <p className={`${t.textFaint} text-xs mt-1`}>PDF format</p>
            </div>
          )}
        </div>

        <button onClick={() => uploadedFile && startExtraction(uploadedFile)} disabled={!uploadedFile}
          className="w-full py-5 rounded-xl font-semibold text-lg transition-all bg-teal-500 text-white hover:bg-teal-400 disabled:opacity-30 disabled:cursor-not-allowed active:scale-[0.98]">
          Extract & Analyse →
        </button>
      </div>
    </div>
  );

  // ── PROCESSING ────────────────────────────────────────────────────────

  if (phase === "processing") return (
    <div className={`min-h-screen ${t.pageBg} flex items-center justify-center relative`}
      style={{ fontFamily: "'DM Sans', system-ui, sans-serif" }}>
      <style>{fonts}</style>
      <div className="absolute top-4 right-4"><ThemeToggle theme={theme} onToggle={toggleTheme} t={t} /></div>
      <div className="text-center">
        <div className="w-12 h-12 border-2 border-teal-400 border-t-transparent rounded-full animate-spin mx-auto mb-6" />
        <p className={`${t.textSecondary} font-medium`}>Reading annual report…</p>
        <p className={`${t.textMuted} text-sm mt-1`}>Extracting organization details</p>
      </div>
    </div>
  );

  // ── DONE ──────────────────────────────────────────────────────────────

  if (phase === "done" && pmContext) return (
    <div className={`min-h-screen ${t.pageBg} flex items-center justify-center p-8 relative`}
      style={{ fontFamily: "'DM Sans', system-ui, sans-serif" }}>
      <style>{fonts}</style>
      <div className="absolute top-4 right-4"><ThemeToggle theme={theme} onToggle={toggleTheme} t={t} /></div>
      <div className="w-full max-w-2xl">
        <div className="mb-8 text-center">
          <div className="w-14 h-14 rounded-full bg-emerald-500/15 flex items-center justify-center mx-auto mb-4">
            <svg className="w-7 h-7 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <h2 style={{ fontFamily: "'Instrument Serif', serif" }} className={`text-2xl ${t.textPrimary} mb-2`}>Ready for the PM</h2>
          <p className={`${t.textMuted} text-sm`}>This context block will be sent to the Product Manager agent.</p>
        </div>
        <div className={`${t.surfaceBg} border ${t.border} rounded-xl p-6 mb-6`}>
          <div className="text-[10px] font-bold text-teal-500 uppercase tracking-wider mb-3">PM Context</div>
          <div className={`text-sm ${t.textSecondary} leading-relaxed whitespace-pre-wrap`}>{pmContext}</div>
        </div>
        <div className="flex gap-3">
          <button onClick={() => navigator.clipboard.writeText(pmContext)}
            className={`flex-1 py-3 ${t.copyBtn} ${t.copyBtnHover} ${t.copyBtnText} text-sm font-medium rounded-xl transition-colors`}>
            Copy to Clipboard
          </button>
          <button onClick={() => {
            const blob = new Blob([pmContext], { type: "text/plain" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a"); a.href = url;
            a.download = `${profile.org_name || "nonprofit"}-pm-context.txt`; a.click();
          }} className="flex-1 py-3 bg-teal-500 hover:bg-teal-400 text-white text-sm font-semibold rounded-xl transition-colors">
            Download .txt
          </button>
        </div>
        <button onClick={() => { setPhase("upload"); setProfile({}); setPmContext(null); setMessages([]); setSessionId(null); }}
          className={`w-full mt-3 py-2.5 ${t.textFaint} text-xs transition-colors`}>
          Start over with a new report
        </button>
      </div>
    </div>
  );

  // ── REVIEW ────────────────────────────────────────────────────────────

  const scalarFields = Object.entries(profile).filter(([_, v]) =>
    typeof v === "string" || typeof v === "number" || typeof v === "boolean" || v === null);
  const arrayFields = Object.entries(profile).filter(([_, v]) => Array.isArray(v) && v.length > 0);

  return (
    <div className={`flex h-screen ${t.pageBg} overflow-hidden`} style={{ fontFamily: "'DM Sans', system-ui, sans-serif" }}>
      <style>{`
        ${fonts}
        * { box-sizing: border-box; }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: ${t.scrollbarThumb}; border-radius: 2px; }
      `}</style>

      {/* ── LEFT: Chat ──────────────────────────────────────────────── */}
      <div className={`flex flex-col h-full flex-1 min-w-0 border-r ${t.border}`}>
        <header className={`flex items-center justify-between px-5 py-3.5 border-b ${t.border} ${t.pageBg} flex-shrink-0`}>
          <div>
            <div className={`${t.textPrimary} text-sm font-semibold`}>{profile.org_name || "Review Findings"}</div>
            <div className={`${t.textFaint} text-[11px] mt-0.5`}>Review, edit, or add to the extracted data</div>
          </div>
          <div className="flex items-center gap-2">
            <ThemeToggle theme={theme} onToggle={toggleTheme} t={t} />
            <button onClick={confirmAndHandoff} disabled={isConfirming || isLoading}
              className="flex items-center gap-1.5 px-4 py-2 bg-teal-500 hover:bg-teal-400 disabled:opacity-40 text-white text-xs font-semibold rounded-lg transition-all active:scale-95">
              {isConfirming
                ? <><div className="w-3 h-3 border border-white/50 border-t-transparent rounded-full animate-spin" /> Confirming…</>
                : "Confirm & Send to PM →"}
            </button>
          </div>
        </header>

        <div className="flex-1 overflow-y-auto px-5 py-6 space-y-4">
          {messages.map((msg, i) => (
            <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
              {msg.role === "assistant" && (
                <div className="w-7 h-7 rounded-full bg-teal-500/20 border border-teal-500/30 flex items-center justify-center flex-shrink-0 mt-0.5 mr-2.5">
                  <span className="text-teal-500 text-xs font-bold">A</span>
                </div>
              )}
              <div className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap ${
                msg.role === "user"
                  ? `${t.bubbleUser} ${t.bubbleUserText} rounded-br-sm`
                  : `${t.bubbleAssistant} border ${t.bubbleAssistantBorder} ${t.bubbleAssistantText} rounded-bl-sm`}`}>
                {msg.content}
              </div>
            </div>
          ))}

          {isLoading && (
            <div className="flex justify-start">
              <div className="w-7 h-7 rounded-full bg-teal-500/20 border border-teal-500/30 flex items-center justify-center flex-shrink-0 mt-0.5 mr-2.5">
                <span className="text-teal-500 text-xs font-bold">A</span>
              </div>
              <div className={`${t.bubbleAssistant} border ${t.bubbleAssistantBorder} rounded-2xl rounded-bl-sm px-4 py-3 flex gap-1 items-center`}>
                {[0, 1, 2].map((i) => (
                  <div key={i} className={`w-1.5 h-1.5 ${t.dotIdle} rounded-full animate-bounce`}
                    style={{ animationDelay: `${i * 0.15}s` }} />
                ))}
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className={`px-5 py-4 border-t ${t.border} ${t.pageBg} flex-shrink-0`}>
          <div className="flex gap-2">
            <input value={input} onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(e as any); } }}
              disabled={isLoading} placeholder="Edit something, add info, or ask a question…"
              className={`flex-1 ${t.inputBg} border ${t.inputBorder} focus:border-teal-500 focus:ring-1 focus:ring-teal-500/20 ${t.inputText} ${t.inputPlaceholder} rounded-xl px-4 py-3 text-sm outline-none transition-all`} />
            <button onClick={(e) => sendMessage(e as any)} disabled={isLoading || !input.trim()}
              className="px-4 py-3 bg-teal-500 hover:bg-teal-400 disabled:opacity-30 text-white rounded-xl transition-all active:scale-95">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
            </button>
          </div>
        </div>
      </div>

      {/* ── RIGHT: Profile Panel ─────────────────────────────────────── */}
      <div className={`w-[380px] flex-shrink-0 flex flex-col h-full ${t.pageBg} overflow-hidden`}>
        <div className={`px-5 py-3.5 border-b ${t.border} flex-shrink-0`}>
          <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-teal-500">Extracted Profile</div>
          <div className={`${t.textFaint} text-[11px] mt-0.5`}>Hover any field to edit or remove</div>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          <div className="mb-6">
            {scalarFields.map(([key, val]) => (
              <EditableField key={key} label={FIELD_LABELS[key] || key.replace(/_/g, " ")}
                value={val} fieldKey={key} onSave={saveField} onDelete={deleteField} t={t} />
            ))}
          </div>
          {arrayFields.map(([key, val]) => (
            <ArraySection key={key} title={FIELD_LABELS[key] || key.replace(/_/g, " ")}
              items={val as any[]} fieldKey={key} onSave={saveField} onDelete={deleteField} t={t} />
          ))}
          {questions.length > 0 && (
            <div className="mt-6 bg-teal-500/10 border border-teal-500/20 rounded-xl p-4">
              <div className="text-[10px] font-bold text-teal-500 uppercase tracking-wider mb-2">Questions for you</div>
              <ul className="space-y-1.5">
                {questions.map((q, i) => (
                  <li key={i} className={`text-xs ${t.textMuted} leading-relaxed flex gap-2`}>
                    <span className="text-teal-500 mt-0.5">•</span> {q}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <div className={`p-4 border-t ${t.border} flex-shrink-0`}>
          <button onClick={confirmAndHandoff} disabled={isConfirming}
            className="w-full py-3 bg-teal-500 hover:bg-teal-400 disabled:opacity-40 text-white text-sm font-semibold rounded-xl transition-all active:scale-[0.98]">
            {isConfirming ? "Generating PM Context…" : "✓ Confirm & Send to PM"}
          </button>
        </div>
      </div>
    </div>
  );
}