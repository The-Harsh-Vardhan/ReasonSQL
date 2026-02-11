"use client";

import { useState, useEffect, useRef, useCallback, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import ProcessingDiagram from "./components/ProcessingDiagram";
import ReasoningCard from "./components/ReasoningCard";
import SystemStatus from "./components/SystemStatus";
import SchemaExplorer from "./components/SchemaExplorer";
import QuerySuggestions from "./components/QuerySuggestions";
import ResultsChart from "./components/ResultsChart";
import { useToast } from "./components/Toast";

// API Types
interface AgentAction {
  agent_name: string;
  summary: string;
  detail?: string;
}

interface ReasoningTrace {
  actions: AgentAction[];
  final_status: string;
  total_time_ms?: number;
  correction_attempts: number;
}

interface QueryResponse {
  success: boolean;
  answer: string;
  sql_used?: string;
  data_preview?: Record<string, unknown>[];
  row_count: number;
  is_meta_query: boolean;
  reasoning_trace?: ReasoningTrace;
  warnings: string[];
  error?: string;
}

const getApiBase = () => {
  const envUrl = process.env.NEXT_PUBLIC_API_URL;
  if (envUrl) return envUrl.replace(/\/+$/, "");
  if (typeof window !== "undefined" && window.location.hostname !== "localhost") return "/api";
  return "http://localhost:8000";
};

const API_BASE = getApiBase();

const buildApiUrl = (path: string) => {
  const base = API_BASE.replace(/\/+$/, "");
  const cleanPath = path.replace(/^\/+/, "");
  return `${base}/${cleanPath}`;
};

const DEMO_QUERIES = [
  { category: "Simple", query: "How many customers are from Brazil?", description: "Tests aggregate COUNT on Chinook customers" },
  { category: "Meta", query: "What tables exist in this database?", description: "Explore Chinook table schema" },
  { category: "Join", query: "Which 5 artists have the most tracks?", description: "Join Artists and Tracks tables" },
  { category: "Ambiguous", query: "Show me recent invoices", description: "Test ClarificationAgent with Chinook data" },
  { category: "Safety", query: "DROP TABLE customers", description: "Verify rule-based safety validation" },
];

// ── Persistence helpers ──
const HISTORY_KEY = "reasonsql_history";
const BOOKMARKS_KEY = "reasonsql_bookmarks";
const STATS_KEY = "reasonsql_stats";

interface HistoryEntry { query: string; success: boolean; time: number; timestamp: number; }
interface BookmarkEntry { query: string; label: string; timestamp: number; }
interface StatsData { totalQueries: number; successCount: number; totalTimeMs: number; queriesPerDay: Record<string, number>; }

function loadJSON<T>(key: string, fallback: T): T {
  if (typeof window === "undefined") return fallback;
  try { const s = localStorage.getItem(key); return s ? JSON.parse(s) : fallback; } catch { return fallback; }
}
function saveJSON<T>(key: string, data: T) {
  if (typeof window === "undefined") return;
  try { localStorage.setItem(key, JSON.stringify(data)); } catch { /* ignore */ }
}

// ── SQL Syntax Highlighting ──
function highlightSQL(sql: string): string {
  const keywords = /\b(SELECT|FROM|WHERE|JOIN|LEFT|RIGHT|INNER|OUTER|ON|AND|OR|NOT|IN|AS|ORDER|BY|GROUP|HAVING|LIMIT|OFFSET|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|TABLE|INTO|VALUES|SET|DISTINCT|COUNT|SUM|AVG|MIN|MAX|CASE|WHEN|THEN|ELSE|END|UNION|ALL|EXISTS|BETWEEN|LIKE|IS|NULL|ASC|DESC|TOP|WITH|CROSS|FULL)\b/gi;
  const functions = /\b(COUNT|SUM|AVG|MIN|MAX|COALESCE|NULLIF|CAST|CONVERT|LENGTH|UPPER|LOWER|TRIM|SUBSTRING|CONCAT|ROUND)\s*(?=\()/gi;
  const strings = /('[^']*')/g;
  const numbers = /\b(\d+\.?\d*)\b/g;

  let result = sql;
  result = result.replace(strings, '<span class="sql-string">$1</span>');
  result = result.replace(functions, '<span class="sql-function">$1</span>');
  result = result.replace(keywords, '<span class="sql-keyword">$1</span>');
  result = result.replace(numbers, '<span class="sql-number">$1</span>');
  return result;
}

// ── CSV export ──
function downloadCSV(data: Record<string, unknown>[], filename = "results.csv") {
  if (!data?.length) return;
  const headers = Object.keys(data[0]);
  const csv = [
    headers.join(","),
    ...data.map(row => headers.map(h => {
      const v = String(row[h] ?? "");
      return v.includes(",") || v.includes('"') || v.includes("\n") ? `"${v.replace(/"/g, '""')}"` : v;
    }).join(","))
  ].join("\n");
  const link = document.createElement("a");
  link.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
  link.download = filename;
  link.click();
}

// ── Copy hook ──
function useCopyFeedback() {
  const [copied, setCopied] = useState<string | null>(null);
  const copy = useCallback(async (text: string, id: string) => {
    await navigator.clipboard.writeText(text);
    setCopied(id);
    setTimeout(() => setCopied(null), 2000);
  }, []);
  return { copied, copy };
}

function HomeInner() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { addToast } = useToast();

  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<QueryResponse | null>(null);
  const [activeTab, setActiveTab] = useState<"result" | "reasoning">("result");
  const [demoMode, setDemoMode] = useState(true);
  const [demoIndex, setDemoIndex] = useState(0);
  const [simpleMode, setSimpleMode] = useState(false);
  const [queryHistory, setQueryHistory] = useState<HistoryEntry[]>([]);
  const [bookmarks, setBookmarks] = useState<BookmarkEntry[]>([]);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [elapsedMs, setElapsedMs] = useState(0);
  const [showAbout, setShowAbout] = useState(false);
  const [showVisuals, setShowVisuals] = useState(true);
  const inputRef = useRef<HTMLInputElement>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const { copied, copy } = useCopyFeedback();

  // ── Load persisted data on mount ──
  useEffect(() => {
    setQueryHistory(loadJSON(HISTORY_KEY, []));
    setBookmarks(loadJSON(BOOKMARKS_KEY, []));
    // Load query from URL
    const urlQuery = searchParams.get("q");
    if (urlQuery) {
      setQuery(urlQuery);
      setDemoMode(false);
    }
  }, [searchParams]);

  // ── Live timer ──
  useEffect(() => {
    if (loading) {
      setElapsedMs(0);
      const start = Date.now();
      timerRef.current = setInterval(() => setElapsedMs(Date.now() - start), 100);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [loading]);

  // ── Stats tracking ──
  const trackQuery = useCallback((success: boolean, timeMs: number) => {
    const stats = loadJSON<StatsData>(STATS_KEY, { totalQueries: 0, successCount: 0, totalTimeMs: 0, queriesPerDay: {} });
    stats.totalQueries++;
    if (success) stats.successCount++;
    stats.totalTimeMs += timeMs;
    const today = new Date().toISOString().split("T")[0];
    stats.queriesPerDay[today] = (stats.queriesPerDay[today] || 0) + 1;
    saveJSON(STATS_KEY, stats);
  }, []);

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!query.trim() || loading) return;

    setLoading(true);
    setResponse(null);

    // Shareable link
    const url = new URL(window.location.href);
    url.searchParams.set("q", query.trim());
    router.replace(url.pathname + url.search, { scroll: false });

    const startTime = Date.now();

    // Prepare history (last 5 messages)
    const history = queryHistory.slice(-5).map(entry => [
      { role: "user", content: entry.query },
      { role: "assistant", content: entry.success ? "Result returned successfully." : "Error occurred." } // Simplified for now
    ]).flat();

    try {
      const res = await fetch(buildApiUrl("query"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: query.trim(),
          history: history
        }),
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({ detail: res.statusText }));
        const errResp: QueryResponse = {
          success: false,
          answer: errorData.detail || `Server error: ${res.status} ${res.statusText}`,
          error: `HTTP ${res.status}: ${errorData.detail || res.statusText}`,
          row_count: 0, is_meta_query: false,
          reasoning_trace: { actions: [], final_status: "error", total_time_ms: 0, correction_attempts: 0 },
          warnings: res.status === 503 ? ["Backend database is not connected."] : [],
        };
        setResponse(errResp);
        addToast("Query failed", "error");
        trackQuery(false, Date.now() - startTime);
        return;
      }

      const data = await res.json();
      const normalizedData: QueryResponse = {
        ...data,
        reasoning_trace: { actions: [], final_status: "unknown", total_time_ms: 0, correction_attempts: 0, ...(data.reasoning_trace || {}) },
        row_count: data.row_count ?? 0,
        is_meta_query: data.is_meta_query ?? false,
        warnings: data.warnings || [],
      };
      setResponse(normalizedData);

      const timeMs = normalizedData.reasoning_trace?.total_time_ms || Date.now() - startTime;
      const newEntry: HistoryEntry = { query: query.trim(), success: normalizedData.success, time: timeMs, timestamp: Date.now() };
      setQueryHistory(prev => { const u = [...prev, newEntry].slice(-20); saveJSON(HISTORY_KEY, u); return u; });

      trackQuery(normalizedData.success, timeMs);
      addToast(normalizedData.success ? "Query completed" : "Query returned an error", normalizedData.success ? "success" : "error");

    } catch (err) {
      setResponse({
        success: false,
        answer: "Failed to connect to the backend API. The server may be starting up (Render free tier can take ~30s). Please try again.",
        error: String(err), row_count: 0, is_meta_query: false,
        reasoning_trace: { actions: [], final_status: "error", total_time_ms: 0, correction_attempts: 0 },
        warnings: [],
      });
      addToast("Connection failed", "error");
      trackQuery(false, Date.now() - startTime);
    } finally {
      setLoading(false);
    }
  };

  // ── Ctrl+Enter ──
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") { e.preventDefault(); handleSubmit(); }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, loading]);

  // ── Bookmarks ──
  const isBookmarked = bookmarks.some(b => b.query === query.trim());
  const toggleBookmark = () => {
    const q = query.trim();
    if (!q) return;
    let updated: BookmarkEntry[];
    if (isBookmarked) {
      updated = bookmarks.filter(b => b.query !== q);
      addToast("Bookmark removed", "info");
    } else {
      updated = [...bookmarks, { query: q, label: q.slice(0, 30), timestamp: Date.now() }];
      addToast("Query bookmarked!", "success");
    }
    setBookmarks(updated);
    saveJSON(BOOKMARKS_KEY, updated);
  };

  const runDemoQuery = (i: number) => { setDemoIndex(i); setQuery(DEMO_QUERIES[i].query); };
  const nextDemo = () => { if (demoIndex < DEMO_QUERIES.length - 1) runDemoQuery(demoIndex + 1); };

  const handleCopy = (text: string, id: string, label: string) => {
    copy(text, id);
    addToast(`${label} copied!`, "success");
  };

  const CopyBtn = ({ text, id, label = "Copy" }: { text: string; id: string; label?: string }) => (
    <button
      onClick={() => handleCopy(text, id, label)}
      className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs bg-white/5 hover:bg-white/10 text-gray-400 hover:text-white transition-all border border-white/10"
    >
      {copied === id ? (
        <><svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" /></svg><span className="text-emerald-400">Copied</span></>
      ) : (
        <><svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg><span>{label}</span></>
      )}
    </button>
  );

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-blue-950 to-emerald-950 flex bg-orbs bg-grid-pattern">
      {/* Mobile Hamburger */}
      <button
        onClick={() => setSidebarOpen(!sidebarOpen)}
        className="fixed top-4 left-4 z-50 lg:hidden p-2 rounded-xl glass-card text-white hover:bg-white/10 transition-colors"
        aria-label="Toggle sidebar"
      >
        <svg xmlns="http://www.w3.org/2000/svg" className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          {sidebarOpen
            ? <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            : <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />}
        </svg>
      </button>

      {sidebarOpen && <div className="fixed inset-0 bg-black/50 z-30 lg:hidden" onClick={() => setSidebarOpen(false)} />}

      {/* Sidebar */}
      <aside className={`w-72 glass-card border-r border-white/10 p-6 flex flex-col z-40 fixed lg:relative inset-y-0 left-0 transform transition-transform duration-300 ease-in-out ${sidebarOpen ? "translate-x-0" : "-translate-x-full"} lg:translate-x-0 overflow-y-auto`}>
        <h2 className="text-lg font-semibold text-white mb-6">Settings</h2>

        {/* Demo Mode */}
        <div className="mb-6">
          <label className="flex items-center gap-3 text-white cursor-pointer group">
            <div className="relative">
              <input type="checkbox" checked={demoMode} onChange={e => setDemoMode(e.target.checked)} className="sr-only peer" />
              <div className="w-10 h-6 bg-gray-700 rounded-full peer peer-checked:bg-gradient-to-r peer-checked:from-cyan-500 peer-checked:to-emerald-500 transition-all" />
              <div className="absolute left-1 top-1 w-4 h-4 bg-white rounded-full transition-transform peer-checked:translate-x-4" />
            </div>
            <span className="group-hover:text-cyan-300 transition-colors">Demo Mode</span>
          </label>
          {demoMode && <p className="text-gray-400 text-sm mt-2 ml-14">Query {demoIndex + 1}/{DEMO_QUERIES.length}</p>}
        </div>

        {/* Simple Mode */}
        <div className="mb-6">
          <label className="flex items-center gap-3 text-white cursor-pointer group">
            <div className="relative">
              <input type="checkbox" checked={simpleMode} onChange={e => setSimpleMode(e.target.checked)} className="sr-only peer" />
              <div className="w-10 h-6 bg-gray-700 rounded-full peer peer-checked:bg-gradient-to-r peer-checked:from-cyan-500 peer-checked:to-emerald-500 transition-all" />
              <div className="absolute left-1 top-1 w-4 h-4 bg-white rounded-full transition-transform peer-checked:translate-x-4" />
            </div>
            <span className="group-hover:text-cyan-300 transition-colors">Simple Mode</span>
          </label>
          <p className="text-gray-400 text-sm mt-2 ml-14">{simpleMode ? "Key agents only" : "Full trace"}</p>
        </div>

        <hr className="border-white/10 my-4" />

        {/* Demo Queries */}
        {demoMode && (
          <div className="mb-6">
            <h3 className="text-gray-400 text-sm mb-3 uppercase tracking-wider">Demo Queries</h3>
            <div className="space-y-2">
              {DEMO_QUERIES.map((dq, i) => (
                <button key={i} onClick={() => runDemoQuery(i)}
                  className={`w-full text-left px-3 py-2.5 rounded-xl text-sm transition-all duration-300 ${demoIndex === i
                    ? "bg-gradient-to-r from-cyan-500/20 to-emerald-500/20 text-cyan-300 border border-cyan-500/40 shadow-lg shadow-cyan-500/10"
                    : "bg-white/5 text-gray-300 hover:bg-white/10 hover:text-white border border-transparent"}`}
                >{dq.category}</button>
              ))}
            </div>
          </div>
        )}

        <hr className="border-white/10 my-4" />
        <SystemStatus />
        <hr className="border-white/10 my-4" />
        <SchemaExplorer />
        <hr className="border-white/10 my-4" />

        {/* Bookmarks */}
        {bookmarks.length > 0 && (
          <>
            <div className="mb-6">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-gray-400 text-sm uppercase tracking-wider">Saved Queries</h3>
                <button onClick={() => { setBookmarks([]); saveJSON(BOOKMARKS_KEY, []); addToast("Bookmarks cleared", "info"); }}
                  className="text-[10px] text-gray-600 hover:text-red-400 transition-colors">Clear</button>
              </div>
              <div className="space-y-1.5 max-h-32 overflow-y-auto">
                {bookmarks.slice(-5).reverse().map((b, i) => (
                  <button key={i} onClick={() => setQuery(b.query)}
                    className="w-full text-left text-xs px-3 py-2 rounded-lg bg-amber-500/10 text-amber-300 border border-amber-500/20 hover:bg-amber-500/20 transition-all truncate">
                    ★ {b.label}
                  </button>
                ))}
              </div>
            </div>
            <hr className="border-white/10 my-4" />
          </>
        )}

        {/* Quick Facts */}
        <div className="mb-6">
          <h3 className="text-gray-400 text-sm mb-3 uppercase tracking-wider">Quick Facts</h3>
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-gradient-to-br from-cyan-500/10 to-blue-500/10 rounded-xl p-3 border border-cyan-500/20">
              <div className="text-2xl font-bold bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent">12</div>
              <div className="text-xs text-gray-400">Agents</div>
            </div>
            <div className="bg-gradient-to-br from-emerald-500/10 to-teal-500/10 rounded-xl p-3 border border-emerald-500/20">
              <div className="text-2xl font-bold bg-gradient-to-r from-emerald-400 to-teal-400 bg-clip-text text-transparent">4-6</div>
              <div className="text-xs text-gray-400">LLM Calls</div>
            </div>
          </div>
        </div>

        {/* History */}
        {queryHistory.length > 0 && (
          <div className="mt-auto">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-gray-400 text-sm uppercase tracking-wider">Recent</h3>
              <button onClick={() => { setQueryHistory([]); saveJSON(HISTORY_KEY, []); }}
                className="text-[10px] text-gray-600 hover:text-red-400 transition-colors">Clear</button>
            </div>
            <div className="space-y-2">
              {queryHistory.slice(-5).reverse().map((h, i) => (
                <button key={i} onClick={() => setQuery(h.query)}
                  className="w-full text-left text-xs bg-white/5 rounded-lg p-3 border border-white/5 hover:bg-white/8 hover:border-white/10 transition-all">
                  <div className="flex items-center gap-2">
                    <span>{h.success ? "✅" : "❌"}</span>
                    <span className="text-gray-400 truncate flex-1">{h.query.slice(0, 25)}...</span>
                  </div>
                  <div className="text-gray-500 mt-1">{h.time.toFixed(0)}ms</div>
                </button>
              ))}
            </div>
          </div>
        )}
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Hero Header */}
        <header className="text-center py-10 lg:py-14 px-4">
          <h1 className="text-4xl lg:text-6xl font-extrabold text-white mb-4 tracking-tight">
            <span className="bg-gradient-to-r from-cyan-400 via-teal-400 to-emerald-400 bg-clip-text text-transparent glow-text">
              ReasonSQL
            </span>
          </h1>
          <p className="text-lg lg:text-xl text-gray-300 max-w-2xl mx-auto font-light">
            Natural Language → SQL with <span className="text-cyan-400 font-semibold">12 Specialized AI Agents</span>
          </p>
          <div className="flex justify-center gap-3 mt-6 text-xs flex-wrap">
            <div className="flex items-center gap-2 px-4 py-1.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 backdrop-blur-sm shadow-lg shadow-emerald-500/10">
              <svg xmlns="http://www.w3.org/2000/svg" className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" />
              </svg>
              <span className="font-bold uppercase tracking-widest">Dataset: Chinook</span>
            </div>
            <a
              href="https://reason-sql.vercel.app"
              target="_blank"
              rel="noopener noreferrer"
              className="px-4 py-1.5 rounded-full bg-cyan-500/10 text-cyan-300 border border-cyan-500/30 backdrop-blur-sm hover:bg-cyan-500/20 transition-all flex items-center gap-2"
            >
              <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
              Live at: reason-sql.vercel.app
            </a>
            <span className="px-4 py-1.5 rounded-full bg-cyan-500/10 text-cyan-300 border border-cyan-500/30 backdrop-blur-sm uppercase tracking-tighter hidden sm:inline">Quota-Optimized</span>
            <span className="px-4 py-1.5 rounded-full bg-cyan-500/10 text-cyan-300 border border-cyan-500/30 backdrop-blur-sm uppercase tracking-tighter hidden sm:inline">Safety-Validated</span>
          </div>

          {/* About / Architecture Toggle */}
          <button
            onClick={() => setShowAbout(!showAbout)}
            className="mt-4 text-xs text-gray-500 hover:text-cyan-400 transition-colors"
          >
            {showAbout ? "Hide Architecture ▲" : "How it works ▼"}
          </button>

          {showAbout && (
            <div className="mt-4 max-w-3xl mx-auto glass-card rounded-2xl p-6 text-left animate-fade-in">
              <h3 className="text-white font-semibold mb-3">Multi-Agent Architecture</h3>
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
                {[
                  { name: "Intent Analyzer", desc: "Classifies query type", color: "cyan" },
                  { name: "Schema Explorer", desc: "Finds relevant tables", color: "teal" },
                  { name: "SQL Generator", desc: "Writes optimized SQL", color: "emerald" },
                  { name: "Safety Validator", desc: "Blocks dangerous ops", color: "amber" },
                  { name: "FK Validator", desc: "Checks join integrity", color: "blue" },
                  { name: "Query Executor", desc: "Runs & formats results", color: "indigo" },
                  { name: "Self-Corrector", desc: "Fixes errors & retries", color: "purple" },
                  { name: "Response Synth", desc: "Natural language answer", color: "pink" },
                ].map((agent, i) => (
                  <div key={i} className={`rounded-lg p-2.5 bg-${agent.color}-500/10 border border-${agent.color}-500/20`}>
                    <div className="text-xs font-medium text-white">{agent.name}</div>
                    <div className="text-[10px] text-gray-400 mt-0.5">{agent.desc}</div>
                  </div>
                ))}
              </div>
              <div className="text-xs text-gray-400 leading-relaxed">
                Queries flow through a <span className="text-cyan-300">batch-optimized pipeline</span> that minimizes LLM calls
                while maximizing accuracy. The system uses <span className="text-emerald-300">Gemini</span> as the LLM backbone,
                with fallback chains and self-correction for reliability.
              </div>
            </div>
          )}
        </header>

        {/* Demo Banner */}
        {demoMode && (
          <div className="mx-4 lg:mx-8 mb-4 p-4 rounded-xl bg-gradient-to-r from-cyan-500/10 to-emerald-500/10 border border-cyan-500/20 backdrop-blur-sm">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-cyan-300 font-medium">Demo Mode | Query {demoIndex + 1}/5: {DEMO_QUERIES[demoIndex].category}</span>
                <p className="text-gray-400 text-sm mt-1">{DEMO_QUERIES[demoIndex].description}</p>
              </div>
              {demoIndex < DEMO_QUERIES.length - 1 && response && (
                <button onClick={nextDemo}
                  className="px-4 py-2 rounded-lg bg-gradient-to-r from-cyan-500/20 to-emerald-500/20 text-cyan-300 hover:from-cyan-500/30 hover:to-emerald-500/30 border border-cyan-500/30 transition-all">
                  Next →
                </button>
              )}
            </div>
          </div>
        )}

        <main className="flex-1 px-4 lg:px-8 pb-8">
          {/* Query Input */}
          <form onSubmit={handleSubmit} className="mb-4">
            <div className="flex gap-3">
              <div className="relative flex-1">
                <input
                  ref={inputRef}
                  type="text"
                  value={query}
                  onChange={e => setQuery(e.target.value)}
                  placeholder="Ask anything about your database... (Ctrl+Enter)"
                  className="w-full px-6 py-4 pr-12 rounded-xl glass-card text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50 text-lg input-glow transition-all"
                  disabled={loading}
                />
                {/* Bookmark button */}
                {query.trim() && (
                  <button type="button" onClick={toggleBookmark}
                    className={`absolute right-3 top-1/2 -translate-y-1/2 text-lg transition-all ${isBookmarked ? "text-amber-400 star-pop" : "text-gray-600 hover:text-amber-400"}`}
                    title={isBookmarked ? "Remove bookmark" : "Bookmark query"}>
                    {isBookmarked ? "★" : "☆"}
                  </button>
                )}
              </div>
              <button
                type="submit"
                disabled={loading || !query.trim()}
                className="px-8 py-4 rounded-xl btn-premium text-white font-semibold disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none">
                {loading ? (
                  <span className="flex items-center gap-2">
                    <span className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    <span className="timer-pulse">{(elapsedMs / 1000).toFixed(1)}s</span>
                  </span>
                ) : "Run"}
              </button>
            </div>
          </form>

          {/* Query Suggestions */}
          {!loading && !response && (
            <div className="mb-8">
              {/* Cold Start Notice */}
              {queryHistory.length === 0 && (
                <div className="mb-6 p-4 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-200 text-sm flex gap-3 items-start animate-fade-in">
                  <span className="text-xl">💡</span>
                  <div>
                    <strong>First query may take ~30s to warm up.</strong>
                    <p className="opacity-80 mt-1 leading-relaxed">
                      The free backend spins down after inactivity. Please be patient with the first request — subsequent queries will be instant!
                    </p>
                  </div>
                </div>
              )}
              <QuerySuggestions onSelect={q => { setQuery(q); inputRef.current?.focus(); }} />
            </div>
          )}

          {/* Loading */}
          {loading && (
            <div className="py-8">
              <ProcessingDiagram />
            </div>
          )}

          {/* Results */}
          {response && !loading && (
            <div className="glass-card rounded-2xl overflow-hidden border-gradient animate-fade-in">
              {/* Status + Metrics */}
              <div className="p-6 border-b border-white/10 bg-gradient-to-r from-transparent via-white/[0.02] to-transparent">
                <div className="flex items-center justify-between flex-wrap gap-4">
                  <div className="flex items-center gap-3">
                    <span className={`px-4 py-2 rounded-full text-sm font-medium ${response.success
                      ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                      : "bg-red-500/20 text-red-300 border border-red-500/30"}`}>
                      {response.success ? "Success" : "Error"}
                      {response.is_meta_query && " (Meta)"}
                    </span>
                    {/* Share button */}
                    <button
                      onClick={() => { navigator.clipboard.writeText(window.location.href); addToast("Link copied! Share it with anyone.", "info"); }}
                      className="px-3 py-2 rounded-full text-xs bg-white/5 text-gray-400 hover:text-white hover:bg-white/10 border border-white/10 transition-all"
                      title="Copy shareable link"
                    >
                      🔗 Share
                    </button>
                  </div>
                  <div className="flex gap-6 text-sm">
                    {[
                      { val: `${(response.reasoning_trace?.total_time_ms ?? 0).toFixed(0)}ms`, label: "Time" },
                      { val: response.row_count, label: "Rows" },
                      { val: response.reasoning_trace?.correction_attempts ?? 0, label: "Retries" },
                      { val: response.reasoning_trace?.actions?.length ?? 0, label: "Steps" },
                    ].map((m, i) => (
                      <div key={i} className="text-center">
                        <div className="text-white font-semibold text-lg">{m.val}</div>
                        <div className="text-gray-500 text-xs">{m.label}</div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Tabs */}
              <div className="flex border-b border-white/10">
                {(["result", "reasoning"] as const).map(tab => (
                  <button key={tab} onClick={() => setActiveTab(tab)}
                    className={`flex-1 py-4 text-center font-medium transition-all ${activeTab === tab
                      ? "text-cyan-400 border-b-2 border-cyan-400 bg-cyan-500/5"
                      : "text-gray-400 hover:text-gray-300 hover:bg-white/5"}`}>
                    {tab === "result" ? "Result" : `Reasoning (${response.reasoning_trace?.actions?.length ?? 0} steps)`}
                  </button>
                ))}
              </div>

              <div className="p-6">
                {activeTab === "result" && (
                  <div className="space-y-6">
                    {/* Answer */}
                    <div>
                      <div className="flex items-center justify-between mb-3">
                        <h3 className="text-lg font-semibold text-white">Answer</h3>
                        <CopyBtn text={response.answer} id="answer" label="Copy" />
                      </div>
                      <p className="text-gray-300 text-lg leading-relaxed bg-black/20 rounded-xl p-4 border border-white/5">
                        {response.answer}
                      </p>
                    </div>

                    {/* Generated SQL with syntax highlighting */}
                    {response.sql_used && !response.is_meta_query && (
                      <div>
                        <div className="flex items-center justify-between mb-3">
                          <h3 className="text-lg font-semibold text-white">Generated SQL</h3>
                          <CopyBtn text={response.sql_used} id="sql" label="Copy SQL" />
                        </div>
                        <pre className="bg-black/40 rounded-xl p-4 overflow-x-auto border border-emerald-500/20">
                          <code
                            className="text-sm font-mono"
                            dangerouslySetInnerHTML={{ __html: highlightSQL(response.sql_used) }}
                          />
                        </pre>
                      </div>
                    )}

                    {/* Data Visualization */}
                    {showVisuals && response.data_preview && response.data_preview.length > 0 && (
                      <ResultsChart data={response.data_preview} />
                    )}

                    {/* Data Preview + CSV export */}
                    {response.data_preview && response.data_preview.length > 0 && (
                      <div className="mt-8">
                        <div className="flex items-center justify-between mb-3">
                          <div className="flex items-center gap-4">
                            <h3 className="text-lg font-semibold text-white">Data Preview</h3>
                            <button
                              onClick={() => setShowVisuals(!showVisuals)}
                              className={`text-xs px-2 py-1 rounded-md border ${showVisuals ? "bg-cyan-500/20 border-cyan-500/30 text-cyan-300" : "bg-white/5 border-white/10 text-gray-400 hover:text-white"} transition-all`}
                            >
                              {showVisuals ? "Hide Chart" : "Show Chart"}
                            </button>
                          </div>
                          <button
                            onClick={() => { downloadCSV(response.data_preview!, "query_results.csv"); addToast("CSV downloaded!", "success"); }}
                            className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs bg-white/5 hover:bg-white/10 text-gray-400 hover:text-white transition-all border border-white/10">
                            <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                            </svg>
                            CSV
                          </button>
                        </div>
                        <div className="overflow-x-auto rounded-xl border border-white/10">
                          <table className="w-full text-sm">
                            <thead className="bg-gradient-to-r from-cyan-500/10 to-emerald-500/10">
                              <tr>
                                {Object.keys(response.data_preview[0]).map(key => (
                                  <th key={key} className="px-4 py-3 text-left font-semibold text-cyan-300 border-b border-white/10">{key}</th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {response.data_preview.slice(0, 10).map((row, i) => (
                                <tr key={i} className="border-b border-white/5 hover:bg-white/5 transition-colors">
                                  {Object.values(row).map((val, j) => (
                                    <td key={j} className="px-4 py-3 text-gray-300">{String(val)}</td>
                                  ))}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {activeTab === "reasoning" && (
                  <div className="space-y-2">
                    <div className="flex items-center gap-3 mb-6 pb-4 border-b border-white/10">
                      <h3 className="text-xl font-semibold text-white">How I figured it out</h3>
                      <span className="text-gray-500 text-sm">({response.reasoning_trace?.actions?.length ?? 0} steps)</span>
                    </div>

                    {/* Pipeline visualization */}
                    {response.reasoning_trace?.actions && response.reasoning_trace.actions.length > 0 && (
                      <div className="mb-6 overflow-x-auto pb-2">
                        <div className="flex items-center gap-1 min-w-max px-2">
                          {response.reasoning_trace.actions
                            .filter(a => !simpleMode || a.agent_name.includes("BATCH") || a.agent_name.includes("Safety") || a.agent_name.includes("Schema"))
                            .map((action, i, arr) => {
                              const name = action.agent_name.replace(/([A-Z])/g, ' $1').replace(/_/g, ' ').trim().split(' ').slice(0, 2).join(' ');
                              return (
                                <div key={i} className="flex items-center gap-1">
                                  <div className="px-2.5 py-1 rounded-lg bg-gradient-to-r from-cyan-500/15 to-emerald-500/15 border border-cyan-500/20 text-[10px] text-cyan-300 font-medium whitespace-nowrap">{name}</div>
                                  {i < arr.length - 1 && <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4 text-gray-600 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" /></svg>}
                                </div>
                              );
                            })}
                        </div>
                      </div>
                    )}

                    <div className="pl-4">
                      {(response.reasoning_trace?.actions || [])
                        .filter(a => !simpleMode || a.agent_name.includes("BATCH") || a.agent_name.includes("Safety") || a.agent_name.includes("Schema"))
                        .map((action, i, arr) => (
                          <ReasoningCard key={i} action={action} index={i} totalSteps={arr.length} simpleMode={simpleMode} />
                        ))}
                    </div>

                    {simpleMode && (
                      <p className="text-gray-500 text-sm text-center py-4 bg-white/5 rounded-xl">
                        Simple Mode: Showing key agents only. Toggle off for full trace.
                      </p>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}
        </main>

        {/* Footer */}
        <footer className="text-center py-6 text-gray-500 text-sm border-t border-white/10 bg-black/20">
          <div className="flex items-center justify-center gap-4 flex-wrap">
            <span className="bg-gradient-to-r from-cyan-400 to-emerald-400 bg-clip-text text-transparent font-medium">Built with Next.js</span>
            <span>•</span>
            <span>12 Agents • FastAPI Backend</span>
            <span>•</span>
            <a href="/dashboard" className="text-cyan-400 hover:text-cyan-300 transition-colors">Dashboard</a>
            <span className="hidden lg:inline">• Ctrl+Enter to submit</span>
          </div>
        </footer>
      </div>
    </div>
  );
}

export default function Home() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-gradient-to-br from-slate-950 via-blue-950 to-emerald-950 flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-cyan-400/30 border-t-cyan-400 rounded-full animate-spin" />
      </div>
    }>
      <HomeInner />
    </Suspense>
  );
}
