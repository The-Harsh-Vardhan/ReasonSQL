"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import ProcessingDiagram from "./components/ProcessingDiagram";
import ReasoningCard from "./components/ReasoningCard";
import SystemStatus from "./components/SystemStatus";
import SchemaExplorer from "./components/SchemaExplorer";
import QuerySuggestions from "./components/QuerySuggestions";

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

// Use relative /api path on Vercel (proxied via rewrites), or direct URL for local dev
const getApiBase = () => {
  const envUrl = process.env.NEXT_PUBLIC_API_URL;
  if (envUrl) {
    return envUrl.replace(/\/+$/, "");
  }
  if (typeof window !== "undefined" && window.location.hostname !== "localhost") {
    return "/api";
  }
  return "http://localhost:8000";
};

const API_BASE = getApiBase();

const buildApiUrl = (path: string) => {
  const base = API_BASE.replace(/\/+$/, "");
  const cleanPath = path.replace(/^\/+/, "");
  return `${base}/${cleanPath}`;
};

// Demo Mode Queries
const DEMO_QUERIES = [
  { category: "Simple", query: "How many customers are from Brazil?", description: "Tests COUNT with WHERE" },
  { category: "Meta", query: "What tables exist in this database?", description: "Schema introspection" },
  { category: "Join", query: "Which 5 artists have the most tracks?", description: "Multi-table join" },
  { category: "Ambiguous", query: "Show me recent invoices", description: "Clarification test" },
  { category: "Safety", query: "DROP TABLE customers", description: "Safety validation" },
];

// History localStorage key
const HISTORY_KEY = "reasonsql_history";

interface HistoryEntry {
  query: string;
  success: boolean;
  time: number;
  timestamp: number;
}

function loadHistory(): HistoryEntry[] {
  if (typeof window === "undefined") return [];
  try {
    const stored = localStorage.getItem(HISTORY_KEY);
    return stored ? JSON.parse(stored) : [];
  } catch {
    return [];
  }
}

function saveHistory(history: HistoryEntry[]) {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(history.slice(-20)));
  } catch { /* ignore */ }
}

// CSV export helper
function downloadCSV(data: Record<string, unknown>[], filename = "results.csv") {
  if (!data || data.length === 0) return;
  const headers = Object.keys(data[0]);
  const csvContent = [
    headers.join(","),
    ...data.map((row) =>
      headers.map((h) => {
        const val = String(row[h] ?? "");
        return val.includes(",") || val.includes('"') || val.includes("\n") ? `"${val.replace(/"/g, '""')}"` : val;
      }).join(",")
    ),
  ].join("\n");

  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  link.click();
  URL.revokeObjectURL(link.href);
}

// Copy helper with visual feedback
function useCopyFeedback() {
  const [copied, setCopied] = useState<string | null>(null);
  const copy = useCallback(async (text: string, id: string) => {
    await navigator.clipboard.writeText(text);
    setCopied(id);
    setTimeout(() => setCopied(null), 2000);
  }, []);
  return { copied, copy };
}

export default function Home() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<QueryResponse | null>(null);
  const [activeTab, setActiveTab] = useState<"result" | "reasoning">("result");

  const [demoMode, setDemoMode] = useState(true);
  const [demoIndex, setDemoIndex] = useState(0);
  const [simpleMode, setSimpleMode] = useState(false);
  const [queryHistory, setQueryHistory] = useState<HistoryEntry[]>([]);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const inputRef = useRef<HTMLInputElement>(null);
  const { copied, copy } = useCopyFeedback();

  // Load history from localStorage on mount
  useEffect(() => {
    setQueryHistory(loadHistory());
  }, []);

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setResponse(null);

    const startTime = Date.now();

    try {
      const res = await fetch(buildApiUrl("query"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: query.trim() }),
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({ detail: res.statusText }));
        setResponse({
          success: false,
          answer: errorData.detail || `Server error: ${res.status} ${res.statusText}`,
          error: `HTTP ${res.status}: ${errorData.detail || res.statusText}`,
          row_count: 0,
          is_meta_query: false,
          reasoning_trace: { actions: [], final_status: "error", total_time_ms: 0, correction_attempts: 0 },
          warnings: res.status === 503 ? ["Backend database is not connected. Please check server configuration."] : [],
        });
        return;
      }

      const data = await res.json();
      const normalizedData: QueryResponse = {
        ...data,
        reasoning_trace: {
          actions: [],
          final_status: "unknown",
          total_time_ms: 0,
          correction_attempts: 0,
          ...(data.reasoning_trace || {}),
        },
        row_count: data.row_count ?? 0,
        is_meta_query: data.is_meta_query ?? false,
        warnings: data.warnings || [],
      };
      setResponse(normalizedData);

      const newEntry: HistoryEntry = {
        query: query.trim(),
        success: normalizedData.success,
        time: normalizedData.reasoning_trace?.total_time_ms || Date.now() - startTime,
        timestamp: Date.now(),
      };
      setQueryHistory((prev) => {
        const updated = [...prev, newEntry].slice(-20);
        saveHistory(updated);
        return updated;
      });

    } catch (err) {
      setResponse({
        success: false,
        answer: "Failed to connect to the backend API. The server may be starting up (Render free tier can take ~30s). Please try again in a moment.",
        error: String(err),
        row_count: 0,
        is_meta_query: false,
        reasoning_trace: { actions: [], final_status: "error", total_time_ms: 0, correction_attempts: 0 },
        warnings: [],
      });
    } finally {
      setLoading(false);
    }
  };

  // Ctrl+Enter keyboard shortcut
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
        e.preventDefault();
        handleSubmit();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, loading]);

  const runDemoQuery = (index: number) => {
    setDemoIndex(index);
    setQuery(DEMO_QUERIES[index].query);
  };

  const nextDemo = () => {
    if (demoIndex < DEMO_QUERIES.length - 1) {
      runDemoQuery(demoIndex + 1);
    }
  };

  // Copy button component
  const CopyButton = ({ text, id, label = "Copy" }: { text: string; id: string; label?: string }) => (
    <button
      onClick={() => copy(text, id)}
      className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs bg-white/5 hover:bg-white/10 text-gray-400 hover:text-white transition-all border border-white/10"
      title={label}
    >
      {copied === id ? (
        <>
          <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
          </svg>
          <span className="text-emerald-400">Copied</span>
        </>
      ) : (
        <>
          <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
          </svg>
          <span>{label}</span>
        </>
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
          {sidebarOpen ? (
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          ) : (
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
          )}
        </svg>
      </button>

      {/* Sidebar Overlay on mobile */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-30 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside className={`
        w-72 glass-card border-r border-white/10 p-6 flex flex-col z-40
        fixed lg:relative inset-y-0 left-0 transform transition-transform duration-300 ease-in-out
        ${sidebarOpen ? "translate-x-0" : "-translate-x-full"}
        lg:translate-x-0 overflow-y-auto
      `}>
        <h2 className="text-lg font-semibold text-white mb-6">Settings</h2>

        {/* Demo Mode */}
        <div className="mb-6">
          <label className="flex items-center gap-3 text-white cursor-pointer group">
            <div className="relative">
              <input
                type="checkbox"
                checked={demoMode}
                onChange={(e) => setDemoMode(e.target.checked)}
                className="sr-only peer"
              />
              <div className="w-10 h-6 bg-gray-700 rounded-full peer peer-checked:bg-gradient-to-r peer-checked:from-cyan-500 peer-checked:to-emerald-500 transition-all"></div>
              <div className="absolute left-1 top-1 w-4 h-4 bg-white rounded-full transition-transform peer-checked:translate-x-4"></div>
            </div>
            <span className="group-hover:text-cyan-300 transition-colors">Demo Mode</span>
          </label>
          {demoMode && (
            <p className="text-gray-400 text-sm mt-2 ml-14">
              Query {demoIndex + 1}/{DEMO_QUERIES.length}
            </p>
          )}
        </div>

        {/* Simple Mode */}
        <div className="mb-6">
          <label className="flex items-center gap-3 text-white cursor-pointer group">
            <div className="relative">
              <input
                type="checkbox"
                checked={simpleMode}
                onChange={(e) => setSimpleMode(e.target.checked)}
                className="sr-only peer"
              />
              <div className="w-10 h-6 bg-gray-700 rounded-full peer peer-checked:bg-gradient-to-r peer-checked:from-cyan-500 peer-checked:to-emerald-500 transition-all"></div>
              <div className="absolute left-1 top-1 w-4 h-4 bg-white rounded-full transition-transform peer-checked:translate-x-4"></div>
            </div>
            <span className="group-hover:text-cyan-300 transition-colors">Simple Mode</span>
          </label>
          <p className="text-gray-400 text-sm mt-2 ml-14">
            {simpleMode ? "Key agents only" : "Full trace"}
          </p>
        </div>

        <hr className="border-white/10 my-4" />

        {/* Demo Queries */}
        {demoMode && (
          <div className="mb-6">
            <h3 className="text-gray-400 text-sm mb-3 uppercase tracking-wider">Demo Queries</h3>
            <div className="space-y-2">
              {DEMO_QUERIES.map((dq, i) => (
                <button
                  key={i}
                  onClick={() => runDemoQuery(i)}
                  className={`w-full text-left px-3 py-2.5 rounded-xl text-sm transition-all duration-300 ${demoIndex === i
                    ? "bg-gradient-to-r from-cyan-500/20 to-emerald-500/20 text-cyan-300 border border-cyan-500/40 shadow-lg shadow-cyan-500/10"
                    : "bg-white/5 text-gray-300 hover:bg-white/10 hover:text-white border border-transparent"
                    }`}
                >
                  {dq.category}
                </button>
              ))}
            </div>
          </div>
        )}

        <hr className="border-white/10 my-4" />

        {/* System Status */}
        <SystemStatus />

        <hr className="border-white/10 my-4" />

        {/* Schema Explorer */}
        <SchemaExplorer />

        <hr className="border-white/10 my-4" />

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
              <button
                onClick={() => { setQueryHistory([]); saveHistory([]); }}
                className="text-[10px] text-gray-600 hover:text-red-400 transition-colors"
              >
                Clear
              </button>
            </div>
            <div className="space-y-2">
              {queryHistory.slice(-5).reverse().map((h, i) => (
                <button
                  key={i}
                  onClick={() => setQuery(h.query)}
                  className="w-full text-left text-xs bg-white/5 rounded-lg p-3 border border-white/5 hover:bg-white/8 hover:border-white/10 transition-all"
                >
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
        <header className="text-center py-12 lg:py-16 px-4">
          <h1 className="text-4xl lg:text-6xl font-extrabold text-white mb-4 tracking-tight">
            <span className="bg-gradient-to-r from-cyan-400 via-teal-400 to-emerald-400 bg-clip-text text-transparent glow-text">
              ReasonSQL
            </span>
          </h1>
          <p className="text-lg lg:text-xl text-gray-300 max-w-2xl mx-auto font-light">
            Natural Language → SQL with <span className="text-cyan-400 font-semibold">12 Specialized AI Agents</span>
          </p>
          <div className="flex justify-center gap-3 mt-6 text-xs flex-wrap">
            <span className="px-4 py-1.5 rounded-full bg-cyan-500/10 text-cyan-300 border border-cyan-500/30 backdrop-blur-sm">
              Quota-Optimized
            </span>
            <span className="px-4 py-1.5 rounded-full bg-emerald-500/10 text-emerald-300 border border-emerald-500/30 backdrop-blur-sm">
              Safety-Validated
            </span>
            <span className="px-4 py-1.5 rounded-full bg-teal-500/10 text-teal-300 border border-teal-500/30 backdrop-blur-sm">
              Self-Correcting
            </span>
          </div>
        </header>

        {/* Demo Banner */}
        {demoMode && (
          <div className="mx-4 lg:mx-8 mb-4 p-4 rounded-xl bg-gradient-to-r from-cyan-500/10 to-emerald-500/10 border border-cyan-500/20 backdrop-blur-sm">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-cyan-300 font-medium">
                  Demo Mode | Query {demoIndex + 1}/5: {DEMO_QUERIES[demoIndex].category}
                </span>
                <p className="text-gray-400 text-sm mt-1">{DEMO_QUERIES[demoIndex].description}</p>
              </div>
              {demoIndex < DEMO_QUERIES.length - 1 && response && (
                <button
                  onClick={nextDemo}
                  className="px-4 py-2 rounded-lg bg-gradient-to-r from-cyan-500/20 to-emerald-500/20 text-cyan-300 hover:from-cyan-500/30 hover:to-emerald-500/30 border border-cyan-500/30 transition-all"
                >
                  Next →
                </button>
              )}
            </div>
          </div>
        )}

        {/* Main Content Area */}
        <main className="flex-1 px-4 lg:px-8 pb-8">
          {/* Query Input */}
          <form onSubmit={handleSubmit} className="mb-4">
            <div className="flex gap-3">
              <input
                ref={inputRef}
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Ask anything about your database... (Ctrl+Enter to submit)"
                className="flex-1 px-6 py-4 rounded-xl glass-card text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-500/50 text-lg input-glow transition-all"
                disabled={loading}
              />
              <button
                type="submit"
                disabled={loading || !query.trim()}
                className="px-8 py-4 rounded-xl btn-premium text-white font-semibold disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none">
                {loading ? (
                  <span className="flex items-center gap-2">
                    <span className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
                    Processing
                  </span>
                ) : (
                  <span>Run</span>
                )}
              </button>
            </div>
          </form>

          {/* Query Suggestions */}
          {!loading && !response && (
            <div className="mb-8">
              <QuerySuggestions onSelect={(q) => { setQuery(q); inputRef.current?.focus(); }} />
            </div>
          )}

          {/* Loading - Processing Diagram */}
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
                  <span
                    className={`px-4 py-2 rounded-full text-sm font-medium ${response.success
                      ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                      : "bg-red-500/20 text-red-300 border border-red-500/30"
                      }`}
                  >
                    {response.success ? "Success" : "Error"}
                    {response.is_meta_query && " (Meta Query)"}
                  </span>
                  <div className="flex gap-8 text-sm">
                    <div className="text-center">
                      <div className="text-white font-semibold text-lg">{(response.reasoning_trace?.total_time_ms ?? 0).toFixed(0)}ms</div>
                      <div className="text-gray-500 text-xs">Time</div>
                    </div>
                    <div className="text-center">
                      <div className="text-white font-semibold text-lg">{response.row_count}</div>
                      <div className="text-gray-500 text-xs">Rows</div>
                    </div>
                    <div className="text-center">
                      <div className="text-white font-semibold text-lg">{response.reasoning_trace?.correction_attempts ?? 0}</div>
                      <div className="text-gray-500 text-xs">Retries</div>
                    </div>
                    <div className="text-center">
                      <div className="text-white font-semibold text-lg">{response.reasoning_trace?.actions?.length ?? 0}</div>
                      <div className="text-gray-500 text-xs">Steps</div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Tabs */}
              <div className="flex border-b border-white/10">
                <button
                  onClick={() => setActiveTab("result")}
                  className={`flex-1 py-4 text-center font-medium transition-all ${activeTab === "result"
                    ? "text-cyan-400 border-b-2 border-cyan-400 bg-cyan-500/5"
                    : "text-gray-400 hover:text-gray-300 hover:bg-white/5"
                    }`}
                >
                  Result
                </button>
                <button
                  onClick={() => setActiveTab("reasoning")}
                  className={`flex-1 py-4 text-center font-medium transition-all ${activeTab === "reasoning"
                    ? "text-cyan-400 border-b-2 border-cyan-400 bg-cyan-500/5"
                    : "text-gray-400 hover:text-gray-300 hover:bg-white/5"
                    }`}
                >
                  Reasoning ({response.reasoning_trace?.actions?.length ?? 0} steps)
                </button>
              </div>

              {/* Tab Content */}
              <div className="p-6">
                {activeTab === "result" && (
                  <div className="space-y-6">
                    {/* Answer */}
                    <div>
                      <div className="flex items-center justify-between mb-3">
                        <h3 className="text-lg font-semibold text-white">Answer</h3>
                        <CopyButton text={response.answer} id="answer" label="Copy" />
                      </div>
                      <p className="text-gray-300 text-lg leading-relaxed bg-black/20 rounded-xl p-4 border border-white/5">
                        {response.answer}
                      </p>
                    </div>

                    {/* Generated SQL */}
                    {response.sql_used && !response.is_meta_query && (
                      <div>
                        <div className="flex items-center justify-between mb-3">
                          <h3 className="text-lg font-semibold text-white">Generated SQL</h3>
                          <CopyButton text={response.sql_used} id="sql" label="Copy SQL" />
                        </div>
                        <pre className="bg-black/40 rounded-xl p-4 overflow-x-auto border border-emerald-500/20">
                          <code className="text-emerald-400 text-sm font-mono">{response.sql_used}</code>
                        </pre>
                      </div>
                    )}

                    {/* Data Preview */}
                    {response.data_preview && response.data_preview.length > 0 && (
                      <div>
                        <div className="flex items-center justify-between mb-3">
                          <h3 className="text-lg font-semibold text-white">Data Preview</h3>
                          <button
                            onClick={() => downloadCSV(response.data_preview!, "query_results.csv")}
                            className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs bg-white/5 hover:bg-white/10 text-gray-400 hover:text-white transition-all border border-white/10"
                          >
                            <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                            </svg>
                            <span>CSV</span>
                          </button>
                        </div>
                        <div className="overflow-x-auto rounded-xl border border-white/10">
                          <table className="w-full text-sm">
                            <thead className="bg-gradient-to-r from-cyan-500/10 to-emerald-500/10">
                              <tr>
                                {Object.keys(response.data_preview[0]).map((key) => (
                                  <th key={key} className="px-4 py-3 text-left font-semibold text-cyan-300 border-b border-white/10">
                                    {key}
                                  </th>
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
                    {/* Header */}
                    <div className="flex items-center gap-3 mb-6 pb-4 border-b border-white/10">
                      <h3 className="text-xl font-semibold text-white">How I figured it out</h3>
                      <span className="text-gray-500 text-sm">({response.reasoning_trace?.actions?.length ?? 0} steps)</span>
                    </div>

                    {/* Agent Pipeline Visualization */}
                    {response.reasoning_trace?.actions && response.reasoning_trace.actions.length > 0 && (
                      <div className="mb-6 overflow-x-auto pb-2">
                        <div className="flex items-center gap-1 min-w-max px-2">
                          {response.reasoning_trace.actions
                            .filter(a => !simpleMode || a.agent_name.includes("BATCH") || a.agent_name.includes("Safety") || a.agent_name.includes("Schema"))
                            .map((action, i, arr) => {
                              const name = action.agent_name.replace(/([A-Z])/g, ' $1').replace(/_/g, ' ').trim().split(' ').slice(0, 2).join(' ');
                              const isLast = i === arr.length - 1;
                              return (
                                <div key={i} className="flex items-center gap-1">
                                  <div className="px-2.5 py-1 rounded-lg bg-gradient-to-r from-cyan-500/15 to-emerald-500/15 border border-cyan-500/20 text-[10px] text-cyan-300 font-medium whitespace-nowrap">
                                    {name}
                                  </div>
                                  {!isLast && (
                                    <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4 text-gray-600 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                      <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                                    </svg>
                                  )}
                                </div>
                              );
                            })}
                        </div>
                      </div>
                    )}

                    {/* Reasoning Steps */}
                    <div className="pl-4">
                      {(response.reasoning_trace?.actions || [])
                        .filter(a => !simpleMode || a.agent_name.includes("BATCH") || a.agent_name.includes("Safety") || a.agent_name.includes("Schema"))
                        .map((action, i, arr) => (
                          <ReasoningCard
                            key={i}
                            action={action}
                            index={i}
                            totalSteps={arr.length}
                            simpleMode={simpleMode}
                          />
                        ))}
                    </div>

                    {simpleMode && (
                      <p className="text-gray-500 text-sm text-center py-4 bg-white/5 rounded-xl">
                        Simple Mode: Showing key agents only. Disable to see full trace.
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
          <span className="bg-gradient-to-r from-cyan-400 to-emerald-400 bg-clip-text text-transparent font-medium">
            Built with Next.js
          </span>
          {" • 12 Agents • FastAPI Backend"}
          <span className="hidden lg:inline"> • Ctrl+Enter to submit</span>
          {demoMode && <span className="ml-2 text-cyan-400">| Demo Mode</span>}
          {simpleMode && <span className="ml-2 text-emerald-400">| Simple Mode</span>}
        </footer>
      </div>
    </div>
  );
}
