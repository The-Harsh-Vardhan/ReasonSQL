"use client";

import { useState } from "react";
import ProcessingDiagram from "./components/ProcessingDiagram";
import ReasoningCard from "./components/ReasoningCard";

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
  reasoning_trace: ReasoningTrace;
  warnings: string[];
  error?: string;
}

const API_BASE = "http://localhost:8000";

// Demo Mode Queries
const DEMO_QUERIES = [
  { category: "Simple", query: "How many customers are from Brazil?", description: "Tests COUNT with WHERE" },
  { category: "Meta", query: "What tables exist in this database?", description: "Schema introspection" },
  { category: "Join", query: "Which 5 artists have the most tracks?", description: "Multi-table join" },
  { category: "Ambiguous", query: "Show me recent invoices", description: "Clarification test" },
  { category: "Safety", query: "DROP TABLE customers", description: "Safety validation" },
];

export default function Home() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<QueryResponse | null>(null);
  const [activeTab, setActiveTab] = useState<"result" | "reasoning">("result");

  const [demoMode, setDemoMode] = useState(true);
  const [demoIndex, setDemoIndex] = useState(0);
  const [simpleMode, setSimpleMode] = useState(false);
  const [queryHistory, setQueryHistory] = useState<{ query: string; success: boolean; time: number }[]>([]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setResponse(null);

    const startTime = Date.now();

    try {
      const res = await fetch(`${API_BASE}/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: query.trim() }),
      });
      const data = await res.json();
      setResponse(data);

      setQueryHistory(prev => [...prev.slice(-4), {
        query: query.trim(),
        success: data.success,
        time: data.reasoning_trace?.total_time_ms || Date.now() - startTime
      }]);

    } catch (err) {
      setResponse({
        success: false,
        answer: "Failed to connect to API. Is FastAPI running on port 8000?",
        error: String(err),
        row_count: 0,
        is_meta_query: false,
        reasoning_trace: { actions: [], final_status: "error", correction_attempts: 0 },
        warnings: [],
      });
    } finally {
      setLoading(false);
    }
  };

  const runDemoQuery = (index: number) => {
    setDemoIndex(index);
    setQuery(DEMO_QUERIES[index].query);
  };

  const nextDemo = () => {
    if (demoIndex < DEMO_QUERIES.length - 1) {
      runDemoQuery(demoIndex + 1);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-blue-950 to-emerald-950 flex bg-orbs bg-grid-pattern">
      {/* Sidebar */}
      <aside className="w-72 glass-card border-r border-white/10 p-6 flex flex-col">
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
            <h3 className="text-gray-400 text-sm mb-3 uppercase tracking-wider">Recent</h3>
            <div className="space-y-2">
              {queryHistory.slice(-3).reverse().map((h, i) => (
                <div key={i} className="text-xs bg-white/5 rounded-lg p-3 border border-white/5">
                  <div className="flex items-center gap-2">
                    <span>{h.success ? "✅" : "❌"}</span>
                    <span className="text-gray-400 truncate flex-1">{h.query.slice(0, 20)}...</span>
                  </div>
                  <div className="text-gray-500 mt-1">{h.time.toFixed(0)}ms</div>
                </div>
              ))}
            </div>
          </div>
        )}
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col">
        {/* Hero Header */}
        <header className="text-center py-16 px-4">
          <h1 className="text-6xl font-extrabold text-white mb-4 tracking-tight">
            <span className="bg-gradient-to-r from-cyan-400 via-teal-400 to-emerald-400 bg-clip-text text-transparent glow-text">
              ReasonSQL
            </span>
          </h1>
          <p className="text-xl text-gray-300 max-w-2xl mx-auto font-light">
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
          <div className="mx-8 mb-4 p-4 rounded-xl bg-gradient-to-r from-cyan-500/10 to-emerald-500/10 border border-cyan-500/20 backdrop-blur-sm">
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
        <main className="flex-1 px-8 pb-8">
          {/* Query Input */}
          <form onSubmit={handleSubmit} className="mb-8">
            <div className="flex gap-3">
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Ask anything about your database..."
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
                      <div className="text-white font-semibold text-lg">{response.reasoning_trace.total_time_ms?.toFixed(0) || 0}ms</div>
                      <div className="text-gray-500 text-xs">Time</div>
                    </div>
                    <div className="text-center">
                      <div className="text-white font-semibold text-lg">{response.row_count}</div>
                      <div className="text-gray-500 text-xs">Rows</div>
                    </div>
                    <div className="text-center">
                      <div className="text-white font-semibold text-lg">{response.reasoning_trace.correction_attempts}</div>
                      <div className="text-gray-500 text-xs">Retries</div>
                    </div>
                    <div className="text-center">
                      <div className="text-white font-semibold text-lg">{response.reasoning_trace.actions.length}</div>
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
                  Reasoning ({response.reasoning_trace.actions.length} steps)
                </button>
              </div>

              {/* Tab Content */}
              <div className="p-6">
                {activeTab === "result" && (
                  <div className="space-y-6">
                    <div>
                      <h3 className="text-lg font-semibold text-white mb-3">Answer</h3>
                      <p className="text-gray-300 text-lg leading-relaxed bg-black/20 rounded-xl p-4 border border-white/5">
                        {response.answer}
                      </p>
                    </div>

                    {response.sql_used && !response.is_meta_query && (
                      <div>
                        <h3 className="text-lg font-semibold text-white mb-3">Generated SQL</h3>
                        <pre className="bg-black/40 rounded-xl p-4 overflow-x-auto border border-emerald-500/20">
                          <code className="text-emerald-400 text-sm font-mono">{response.sql_used}</code>
                        </pre>
                      </div>
                    )}

                    {response.data_preview && response.data_preview.length > 0 && (
                      <div>
                        <h3 className="text-lg font-semibold text-white mb-3">Data Preview</h3>
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
                      <span className="text-gray-500 text-sm">({response.reasoning_trace.actions.length} steps)</span>
                    </div>

                    {/* Reasoning Steps */}
                    <div className="pl-4">
                      {response.reasoning_trace.actions
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
          {demoMode && <span className="ml-2 text-cyan-400">| Demo Mode</span>}
          {simpleMode && <span className="ml-2 text-emerald-400">| Simple Mode</span>}
        </footer>
      </div>
    </div>
  );
}
