"use client";

import { useState, useRef, useEffect, useCallback } from "react";

const API_BASE = "http://localhost:8000";

type Message = { role: "user" | "assistant"; content: string };
type Requirements = Record<string, any>;

const ALL_KEYS = [
  "organization.name","organization.mission","organization.target_audience",
  "organization.tone","organization.website_goals","pages",
  "features.donation_form","features.recurring_donations","features.volunteer_signup",
  "features.event_calendar","features.newsletter_signup","features.blog",
  "features.multilanguage","features.ada_compliance","features.other",
  "design.brand_colors","design.has_existing_logo","technical.has_domain",
  "technical.domain_name","technical.integrations","technical.timeline","technical.budget",
];

const KEY_LABELS: Record<string, string> = {
  "organization.name": "Org Name", "organization.mission": "Mission",
  "organization.target_audience": "Target Audience", "organization.tone": "Brand Tone",
  "organization.website_goals": "Website Goals", "pages": "Pages/Programs",
  "features.donation_form": "Donation Form", "features.recurring_donations": "Recurring Donations",
  "features.volunteer_signup": "Volunteer Signup", "features.event_calendar": "Event Calendar",
  "features.newsletter_signup": "Newsletter", "features.blog": "Blog/News",
  "features.multilanguage": "Multi-language", "features.ada_compliance": "ADA Compliance",
  "features.other": "Other Features", "design.brand_colors": "Brand Colors",
  "design.has_existing_logo": "Logo", "technical.has_domain": "Domain",
  "technical.domain_name": "Domain Name", "technical.integrations": "Integrations",
  "technical.timeline": "Timeline", "technical.budget": "Budget",
};

const SECTION_LABELS: Record<string, string> = {
  organization: "Organization", pages: "Pages", features: "Features",
  design: "Design", technical: "Technical",
};

function formatValue(val: any): string {
  if (val === null || val === undefined) return "—";
  if (typeof val === "boolean") return val ? "Yes" : "No";
  if (Array.isArray(val)) return val.join(", ");
  return String(val);
}

function ReqSection({ title, data }: { title: string; data: Record<string, any> }) {
  return (
    <div className="mb-6">
      <h3 className="text-[10px] font-bold uppercase tracking-[0.2em] text-amber-500 mb-3">{title}</h3>
      <div className="space-y-2">
        {Object.entries(data).map(([k, v]) => {
          if (v === null || v === "" || (Array.isArray(v) && v.length === 0)) return null;
          return (
            <div key={k} className="grid grid-cols-[140px_1fr] gap-3 text-sm">
              <span className="text-slate-400 capitalize">{k.replace(/_/g, " ")}</span>
              <span className="text-slate-100 leading-snug">{formatValue(v)}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function ConsultantChat() {
  const [phase, setPhase] = useState<"landing" | "uploading" | "chat">("landing");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isExtracting, setIsExtracting] = useState(false);
  const [requirements, setRequirements] = useState<Requirements | null>(null);
  const [foundKeys, setFoundKeys] = useState<string[]>([]);
  const [missingKeys, setMissingKeys] = useState<string[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [showProgress, setShowProgress] = useState(true);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const startSession = async (file?: File | null) => {
    setPhase("uploading");
    setIsLoading(true);
    setRequirements(null);
    setMessages([]);

    try {
      let res: Response;
      if (file) {
        const form = new FormData();
        form.append("annual_report", file);
        res = await fetch(`${API_BASE}/consultant/session/new`, { method: "POST", body: form });
      } else {
        res = await fetch(`${API_BASE}/consultant/session/new`, { method: "POST" });
      }
      const data = await res.json();
      if (data.session_id && data.greeting) {
        setSessionId(data.session_id);
        setMessages([{ role: "assistant", content: data.greeting }]);
        setFoundKeys(data.found_keys ?? []);
        setMissingKeys(data.missing_keys ?? ALL_KEYS);
        setPhase("chat");
      }
    } catch (err) {
      console.error(err);
      setPhase("landing");
    } finally {
      setIsLoading(false);
    }
  };

  const sendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || !sessionId || isLoading) return;
    const userMessage = input.trim();
    setInput("");
    setMessages((p) => [...p, { role: "user", content: userMessage }]);
    setIsLoading(true);
    try {
      const res = await fetch(`${API_BASE}/consultant/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, message: userMessage }),
      });
      const data = await res.json();
      if (data.reply) setMessages((p) => [...p, { role: "assistant", content: data.reply }]);
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  const generateBrief = async () => {
    if (!sessionId) return;
    setIsExtracting(true);
    try {
      const res = await fetch(`${API_BASE}/consultant/session/${sessionId}/summary`);
      const data = await res.json();
      if (data.requirements) setRequirements(data.requirements);
    } catch (err) {
      console.error(err);
    } finally {
      setIsExtracting(false);
    }
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file?.type === "application/pdf") setUploadedFile(file);
  }, []);

  const filledCount = foundKeys.length;
  const totalCount = ALL_KEYS.length;
  const progressPct = Math.round((filledCount / totalCount) * 100);

  // ── LANDING ──────────────────────────────────────────────────────────────
  if (phase === "landing") {
    return (
      <div className="min-h-screen bg-[#0d0f14] flex items-center justify-center p-8"
        style={{ fontFamily: "'DM Sans', system-ui, sans-serif" }}>
        <style>{`
          @import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:wght@300;400;500;600&display=swap');
          * { box-sizing: border-box; }
        `}</style>

        <div className="w-full max-w-lg">
          {/* Wordmark */}
          <div className="mb-12">
            <div className="text-amber-400 text-xs font-semibold tracking-[0.3em] uppercase mb-2">AgileGPT</div>
            <h1 style={{ fontFamily: "'DM Serif Display', serif" }}
              className="text-4xl text-white leading-tight">
              Nonprofit Website<br /><em className="text-amber-400">Consultant</em>
            </h1>
            <p className="text-slate-400 mt-3 text-sm leading-relaxed max-w-sm">
              Upload your annual report and we'll pre-fill everything we can — then guide you through the rest in a short conversation.
            </p>
          </div>

          {/* Drop zone */}
          <div
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`relative border-2 border-dashed rounded-xl p-8 cursor-pointer transition-all duration-200 mb-4 ${
              dragOver
                ? "border-amber-400 bg-amber-400/5"
                : uploadedFile
                ? "border-emerald-500 bg-emerald-500/5"
                : "border-slate-700 bg-slate-800/40 hover:border-slate-500 hover:bg-slate-800/60"
            }`}
          >
            <input ref={fileInputRef} type="file" accept=".pdf" className="hidden"
              onChange={(e) => setUploadedFile(e.target.files?.[0] ?? null)} />

            {uploadedFile ? (
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 rounded-lg bg-emerald-500/20 flex items-center justify-center flex-shrink-0">
                  <svg className="w-5 h-5 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <div>
                  <p className="text-emerald-400 font-medium text-sm">{uploadedFile.name}</p>
                  <p className="text-slate-500 text-xs mt-0.5">{(uploadedFile.size / 1024).toFixed(0)} KB · Click to change</p>
                </div>
              </div>
            ) : (
              <div className="text-center">
                <div className="w-10 h-10 rounded-lg bg-slate-700 flex items-center justify-center mx-auto mb-3">
                  <svg className="w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                  </svg>
                </div>
                <p className="text-slate-300 text-sm font-medium">Drop your annual report here</p>
                <p className="text-slate-500 text-xs mt-1">PDF · Optional but recommended</p>
              </div>
            )}
          </div>

          {/* CTA buttons */}
          <div className="space-y-3">
            <button
              onClick={() => startSession(uploadedFile)}
              className="w-full py-3.5 rounded-xl font-semibold text-sm transition-all duration-200 bg-amber-400 text-slate-900 hover:bg-amber-300 active:scale-[0.98]"
            >
              {uploadedFile ? "Analyse Report & Start →" : "Start Without Report →"}
            </button>
            {uploadedFile && (
              <button onClick={() => setUploadedFile(null)}
                className="w-full py-2.5 rounded-xl text-sm text-slate-500 hover:text-slate-300 transition-colors">
                Clear file
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }

  // ── UPLOADING ────────────────────────────────────────────────────────────
  if (phase === "uploading") {
    return (
      <div className="min-h-screen bg-[#0d0f14] flex items-center justify-center"
        style={{ fontFamily: "'DM Sans', system-ui, sans-serif" }}>
        <style>{`@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:wght@300;400;500;600&display=swap');`}</style>
        <div className="text-center">
          <div className="w-12 h-12 border-2 border-amber-400 border-t-transparent rounded-full animate-spin mx-auto mb-6" />
          <p className="text-slate-300 font-medium">
            {uploadedFile ? "Reading your annual report…" : "Starting session…"}
          </p>
          <p className="text-slate-600 text-sm mt-1">Running RAG extraction across 22 fields</p>
        </div>
      </div>
    );
  }

  // ── CHAT ─────────────────────────────────────────────────────────────────
  const reqSections = requirements
    ? Object.entries(requirements).filter(([, v]) => v && typeof v === "object" && !Array.isArray(v))
    : [];

  return (
    <div className="flex h-screen bg-[#0d0f14] overflow-hidden"
      style={{ fontFamily: "'DM Sans', system-ui, sans-serif" }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:wght@300;400;500;600&display=swap');
        * { box-sizing: border-box; }
        ::-webkit-scrollbar { width: 4px; } ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #334155; border-radius: 2px; }
      `}</style>

      {/* ── LEFT SIDEBAR: Progress ─────────────────────────────────────── */}
      {(foundKeys.length > 0 || missingKeys.length > 0) && showProgress && (
        <aside className="w-56 flex-shrink-0 bg-[#111318] border-r border-slate-800 flex flex-col overflow-hidden">
          <div className="p-4 border-b border-slate-800">
            <div className="flex items-center justify-between mb-1">
              <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-slate-500">Coverage</span>
              <span className="text-amber-400 text-xs font-semibold">{progressPct}%</span>
            </div>
            <div className="h-1 bg-slate-800 rounded-full overflow-hidden">
              <div className="h-full bg-amber-400 rounded-full transition-all duration-500"
                style={{ width: `${progressPct}%` }} />
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-3 space-y-1">
            {ALL_KEYS.map((key) => {
              const found = foundKeys.includes(key);
              const missing = missingKeys.includes(key);
              return (
                <div key={key} className="flex items-center gap-2 py-0.5">
                  <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                    found ? "bg-emerald-400" : missing ? "bg-amber-500" : "bg-slate-700"
                  }`} />
                  <span className={`text-[11px] leading-tight ${
                    found ? "text-emerald-400" : missing ? "text-amber-400" : "text-slate-600"
                  }`}>{KEY_LABELS[key] ?? key}</span>
                </div>
              );
            })}
          </div>

          <div className="p-3 border-t border-slate-800 space-y-1 text-[10px] text-slate-600">
            <div className="flex items-center gap-1.5"><div className="w-1.5 h-1.5 rounded-full bg-emerald-400" /> From report</div>
            <div className="flex items-center gap-1.5"><div className="w-1.5 h-1.5 rounded-full bg-amber-500" /> Needs input</div>
          </div>
        </aside>
      )}

      {/* ── MAIN CHAT ──────────────────────────────────────────────────── */}
      <div className={`flex flex-col h-full flex-1 min-w-0 ${requirements ? "border-r border-slate-800" : ""}`}>

        {/* Header */}
        <header className="flex items-center justify-between px-5 py-3.5 border-b border-slate-800 bg-[#111318] flex-shrink-0">
          <div className="flex items-center gap-3">
            <button onClick={() => setPhase("landing")}
              className="text-slate-600 hover:text-slate-300 transition-colors">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </button>
            <div>
              <div className="text-white text-sm font-semibold leading-none">
                {uploadedFile ? uploadedFile.name.replace(".pdf", "") : "New Session"}
              </div>
              <div className="text-slate-600 text-[11px] mt-0.5">
                {sessionId?.substring(0, 8)}… · {messages.length} messages
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {(foundKeys.length > 0 || missingKeys.length > 0) && (
              <button onClick={() => setShowProgress((p) => !p)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                  showProgress ? "bg-slate-800 text-slate-300" : "bg-slate-800/50 text-slate-500 hover:text-slate-300"
                }`}>
                {showProgress ? "Hide" : "Show"} Progress
              </button>
            )}
            <button onClick={generateBrief} disabled={isExtracting || isLoading}
              className="flex items-center gap-1.5 px-3.5 py-1.5 bg-amber-400 hover:bg-amber-300 disabled:opacity-40 text-slate-900 text-xs font-semibold rounded-lg transition-all active:scale-95">
              {isExtracting ? (
                <><div className="w-3 h-3 border border-slate-900 border-t-transparent rounded-full animate-spin" /> Extracting…</>
              ) : (
                <><svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg> Generate Brief</>
              )}
            </button>
          </div>
        </header>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-5 py-6 space-y-5">
          {messages.map((msg, i) => (
            <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
              {msg.role === "assistant" && (
                <div className="w-7 h-7 rounded-full bg-amber-400/20 border border-amber-400/30 flex items-center justify-center flex-shrink-0 mt-0.5 mr-2.5">
                  <span className="text-amber-400 text-xs font-bold">A</span>
                </div>
              )}
              <div className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap ${
                msg.role === "user"
                  ? "bg-slate-700 text-slate-100 rounded-br-sm"
                  : "bg-[#1a1d24] border border-slate-800 text-slate-200 rounded-bl-sm"
              }`}>
                {msg.content}
              </div>
            </div>
          ))}

          {isLoading && (
            <div className="flex justify-start">
              <div className="w-7 h-7 rounded-full bg-amber-400/20 border border-amber-400/30 flex items-center justify-center flex-shrink-0 mt-0.5 mr-2.5">
                <span className="text-amber-400 text-xs font-bold">A</span>
              </div>
              <div className="bg-[#1a1d24] border border-slate-800 rounded-2xl rounded-bl-sm px-4 py-3 flex gap-1 items-center">
                {[0, 1, 2].map((i) => (
                  <div key={i} className="w-1.5 h-1.5 bg-slate-500 rounded-full animate-bounce"
                    style={{ animationDelay: `${i * 0.15}s` }} />
                ))}
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <form onSubmit={sendMessage}
          className="px-5 py-4 border-t border-slate-800 bg-[#111318] flex-shrink-0">
          <div className="flex gap-2">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={isLoading}
              placeholder="Reply to the consultant…"
              className="flex-1 bg-[#1a1d24] border border-slate-700 focus:border-amber-400/50 focus:ring-1 focus:ring-amber-400/20 text-slate-200 placeholder-slate-600 rounded-xl px-4 py-3 text-sm outline-none transition-all"
            />
            <button type="submit" disabled={isLoading || !input.trim()}
              className="px-4 py-3 bg-amber-400 hover:bg-amber-300 disabled:opacity-30 text-slate-900 rounded-xl transition-all active:scale-95">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
            </button>
          </div>
        </form>
      </div>

      {/* ── REQUIREMENTS BRIEF ────────────────────────────────────────── */}
      {requirements && (
        <div className="w-96 flex-shrink-0 flex flex-col h-full bg-[#111318] overflow-hidden">
          <div className="flex items-center justify-between px-5 py-3.5 border-b border-slate-800">
            <div>
              <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-amber-500">Output</div>
              <div className="text-white text-sm font-semibold mt-0.5">Requirements Brief</div>
            </div>
            <button onClick={() => setRequirements(null)}
              className="text-slate-600 hover:text-slate-300 transition-colors p-1">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-5">
            {reqSections.map(([section, data]) => (
              <ReqSection key={section} title={SECTION_LABELS[section] ?? section}
                data={data as Record<string, any>} />
            ))}

            {/* Pages list */}
            {Array.isArray(requirements.pages) && requirements.pages.length > 0 && (
              <div className="mb-6">
                <h3 className="text-[10px] font-bold uppercase tracking-[0.2em] text-amber-500 mb-3">Pages</h3>
                <div className="flex flex-wrap gap-1.5">
                  {requirements.pages.map((p: any, i: number) => (
                    <span key={i} className="px-2.5 py-1 bg-slate-800 text-slate-300 rounded-lg text-xs">
                      {typeof p === "string" ? p : p.name ?? JSON.stringify(p)}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Raw JSON toggle */}
            <details className="mt-4">
              <summary className="text-[10px] font-bold uppercase tracking-[0.2em] text-slate-600 cursor-pointer hover:text-slate-400 transition-colors">
                Raw JSON
              </summary>
              <pre className="mt-3 text-[10px] text-slate-500 bg-slate-900 rounded-lg p-3 overflow-x-auto leading-relaxed">
                {JSON.stringify(requirements, null, 2)}
              </pre>
            </details>
          </div>

          <div className="p-4 border-t border-slate-800">
            <button
              onClick={() => {
                const blob = new Blob([JSON.stringify(requirements, null, 2)], { type: "application/json" });
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url; a.download = "website-brief.json"; a.click();
              }}
              className="w-full py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium rounded-lg transition-colors flex items-center justify-center gap-2"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              Download website-brief.json
            </button>
          </div>
        </div>
      )}
    </div>
  );
}