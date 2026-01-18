"use client";

import { useState } from "react";

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
  { category: "🔢 Simple", query: "How many customers are from Brazil?", description: "Tests COUNT with WHERE" },
  { category: "📋 Meta", query: "What tables exist in this database?", description: "Schema introspection" },
  { category: "🔗 Join", query: "Which 5 artists have the most tracks?", description: "Multi-table join" },
  { category: "❓ Ambiguous", query: "Show me recent invoices", description: "Clarification test" },
  { category: "🛡️ Safety", query: "DROP TABLE customers", description: "Safety validation" },
];

export default function Home() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<QueryResponse | null>(null);
  const [activeTab, setActiveTab] = useState<"result" | "reasoning">("result");

  // Feature parity with Streamlit
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

      // Add to history
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
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 flex">
      {/* Sidebar */}
      <aside className="w-72 bg-black/30 border-r border-white/10 p-6 flex flex-col">
        <h2 className="text-xl font-bold text-white mb-6">⚙️ Settings</h2>

        {/* Demo Mode */}
        <div className="mb-6">
          <label className="flex items-center gap-3 text-white cursor-pointer">
            <input
              type="checkbox"
              checked={demoMode}
              onChange={(e) => setDemoMode(e.target.checked)}
              className="w-5 h-5 rounded bg-white/10 border-white/20"
            />
            <span>🎮 Demo Mode</span>
          </label>
          {demoMode && (
            <p className="text-gray-400 text-sm mt-2 ml-8">
              Query {demoIndex + 1}/{DEMO_QUERIES.length}
            </p>
          )}
        </div>

        {/* Simple Mode */}
        <div className="mb-6">
          <label className="flex items-center gap-3 text-white cursor-pointer">
            <input
              type="checkbox"
              checked={simpleMode}
              onChange={(e) => setSimpleMode(e.target.checked)}
              className="w-5 h-5 rounded bg-white/10 border-white/20"
            />
            <span>🎯 Simple Mode</span>
          </label>
          <p className="text-gray-400 text-sm mt-2 ml-8">
            {simpleMode ? "Key agents only" : "Full trace"}
          </p>
        </div>

        <hr className="border-white/10 my-4" />

        {/* Demo Queries */}
        {demoMode && (
          <div className="mb-6">
            <h3 className="text-gray-400 text-sm mb-3">Demo Queries</h3>
            <div className="space-y-2">
              {DEMO_QUERIES.map((dq, i) => (
                <button
                  key={i}
                  onClick={() => runDemoQuery(i)}
                  className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${demoIndex === i
                      ? "bg-purple-500/30 text-purple-300 border border-purple-500/50"
                      : "bg-white/5 text-gray-300 hover:bg-white/10"
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
          <h3 className="text-gray-400 text-sm mb-3">⚡ Quick Facts</h3>
          <div className="grid grid-cols-2 gap-2 text-center">
            <div className="bg-white/5 rounded-lg p-3">
              <div className="text-2xl font-bold text-white">12</div>
              <div className="text-xs text-gray-400">Agents</div>
            </div>
            <div className="bg-white/5 rounded-lg p-3">
              <div className="text-2xl font-bold text-white">4-6</div>
              <div className="text-xs text-gray-400">LLM Calls</div>
            </div>
          </div>
        </div>

        {/* History */}
        {queryHistory.length > 0 && (
          <div className="mt-auto">
            <h3 className="text-gray-400 text-sm mb-3">📜 Recent</h3>
            <div className="space-y-2">
              {queryHistory.slice(-3).reverse().map((h, i) => (
                <div key={i} className="text-xs bg-white/5 rounded p-2">
                  <div className="flex items-center gap-2">
                    <span>{h.success ? "✅" : "❌"}</span>
                    <span className="text-gray-400 truncate">{h.query.slice(0, 20)}...</span>
                  </div>
                  <div className="text-gray-500 mt-1">⏱️ {h.time.toFixed(0)}ms</div>
                </div>
              ))}
            </div>
          </div>
        )}
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col">
        {/* Hero Header */}
        <header className="text-center py-12 px-4">
          <h1 className="text-4xl font-bold text-white mb-3">
            <span className="bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">
              ReasonSQL
            </span>
          </h1>
          <p className="text-lg text-gray-300">
            Natural Language → SQL with 12 Specialized AI Agents
          </p>
          <div className="flex justify-center gap-3 mt-4 text-xs">
            <span className="px-3 py-1 rounded-full bg-purple-500/20 text-purple-300 border border-purple-500/30">
              ✨ Quota-Optimized
            </span>
            <span className="px-3 py-1 rounded-full bg-green-500/20 text-green-300 border border-green-500/30">
              🛡️ Safety-Validated
            </span>
            <span className="px-3 py-1 rounded-full bg-blue-500/20 text-blue-300 border border-blue-500/30">
              🔄 Self-Correcting
            </span>
          </div>
        </header>

        {/* Demo Banner */}
        {demoMode && (
          <div className="mx-8 mb-4 p-4 rounded-xl bg-blue-500/10 border border-blue-500/30">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-blue-300 font-medium">
                  🎮 Demo Mode Active | Query {demoIndex + 1}/5: {DEMO_QUERIES[demoIndex].category}
                </span>
                <p className="text-gray-400 text-sm mt-1">{DEMO_QUERIES[demoIndex].description}</p>
              </div>
              {demoIndex < DEMO_QUERIES.length - 1 && response && (
                <button
                  onClick={nextDemo}
                  className="px-4 py-2 rounded-lg bg-blue-500/20 text-blue-300 hover:bg-blue-500/30"
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
          <form onSubmit={handleSubmit} className="mb-6">
            <div className="flex gap-2">
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Ask anything about your database..."
                className="flex-1 px-6 py-4 rounded-xl bg-white/10 border border-white/20 text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500 text-lg"
                disabled={loading}
              />
              <button
                type="submit"
                disabled={loading || !query.trim()}
                className="px-8 py-4 rounded-xl bg-gradient-to-r from-purple-500 to-pink-500 text-white font-semibold hover:from-purple-600 hover:to-pink-600 disabled:opacity-50 transition-all"
              >
                {loading ? "🔄" : "🚀"} Run
              </button>
            </div>
          </form>

          {/* Loading */}
          {loading && (
            <div className="text-center py-12">
              <div className="inline-block animate-spin rounded-full h-12 w-12 border-4 border-purple-500 border-t-transparent"></div>
              <p className="text-gray-400 mt-4">Processing through agent pipeline...</p>
            </div>
          )}

          {/* Results */}
          {response && !loading && (
            <div className="bg-white/5 rounded-2xl border border-white/10 overflow-hidden">
              {/* Status + Metrics */}
              <div className="p-6 border-b border-white/10">
                <div className="flex items-center justify-between flex-wrap gap-4">
                  <span
                    className={`px-4 py-2 rounded-full text-sm font-medium ${response.success
                        ? "bg-green-500/20 text-green-300 border border-green-500/30"
                        : "bg-red-500/20 text-red-300 border border-red-500/30"
                      }`}
                  >
                    {response.success ? "✅ Success" : "❌ Error"}
                    {response.is_meta_query && " (Meta Query)"}
                  </span>
                  <div className="flex gap-6 text-sm">
                    <div className="text-center">
                      <div className="text-white font-semibold">⏱️ {response.reasoning_trace.total_time_ms?.toFixed(0) || 0}ms</div>
                      <div className="text-gray-500 text-xs">Time</div>
                    </div>
                    <div className="text-center">
                      <div className="text-white font-semibold">📋 {response.row_count}</div>
                      <div className="text-gray-500 text-xs">Rows</div>
                    </div>
                    <div className="text-center">
                      <div className="text-white font-semibold">🔄 {response.reasoning_trace.correction_attempts}</div>
                      <div className="text-gray-500 text-xs">Retries</div>
                    </div>
                    <div className="text-center">
                      <div className="text-white font-semibold">📦 {response.reasoning_trace.actions.length}</div>
                      <div className="text-gray-500 text-xs">Steps</div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Tabs */}
              <div className="flex border-b border-white/10">
                <button
                  onClick={() => setActiveTab("result")}
                  className={`flex-1 py-4 text-center font-medium transition-colors ${activeTab === "result"
                      ? "text-purple-400 border-b-2 border-purple-400"
                      : "text-gray-400 hover:text-gray-300"
                    }`}
                >
                  📦 Result
                </button>
                <button
                  onClick={() => setActiveTab("reasoning")}
                  className={`flex-1 py-4 text-center font-medium transition-colors ${activeTab === "reasoning"
                      ? "text-purple-400 border-b-2 border-purple-400"
                      : "text-gray-400 hover:text-gray-300"
                    }`}
                >
                  🧠 Reasoning ({response.reasoning_trace.actions.length} steps)
                </button>
              </div>

              {/* Tab Content */}
              <div className="p-6">
                {activeTab === "result" && (
                  <div className="space-y-6">
                    <div>
                      <h3 className="text-lg font-semibold text-white mb-3">Answer</h3>
                      <p className="text-gray-300 text-lg leading-relaxed">{response.answer}</p>
                    </div>

                    {response.sql_used && !response.is_meta_query && (
                      <div>
                        <h3 className="text-lg font-semibold text-white mb-3">Generated SQL</h3>
                        <pre className="bg-black/30 rounded-lg p-4 overflow-x-auto">
                          <code className="text-green-400 text-sm">{response.sql_used}</code>
                        </pre>
                      </div>
                    )}

                    {response.data_preview && response.data_preview.length > 0 && (
                      <div>
                        <h3 className="text-lg font-semibold text-white mb-3">Data Preview</h3>
                        <div className="overflow-x-auto">
                          <table className="w-full text-sm">
                            <thead className="text-gray-400 border-b border-white/10">
                              <tr>
                                {Object.keys(response.data_preview[0]).map((key) => (
                                  <th key={key} className="px-4 py-3 text-left font-medium">{key}</th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {response.data_preview.slice(0, 10).map((row, i) => (
                                <tr key={i} className="border-b border-white/5">
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
                  <div className="space-y-4">
                    {response.reasoning_trace.actions
                      .filter(a => !simpleMode || a.agent_name.includes("BATCH") || a.agent_name.includes("Safety") || a.agent_name.includes("Schema"))
                      .map((action, i) => (
                        <div key={i} className="bg-black/20 rounded-lg p-4 border border-white/5">
                          <div className="flex items-center gap-3 mb-2">
                            <span className="text-2xl">{action.agent_name.includes("BATCH") ? "🧠" : "📦"}</span>
                            <span className="font-semibold text-white">{action.agent_name}</span>
                            {action.agent_name.includes("BATCH") && (
                              <span className="text-xs px-2 py-1 rounded bg-blue-500/20 text-blue-300">LLM</span>
                            )}
                          </div>
                          <p className="text-gray-400 text-sm">{action.summary}</p>
                          {action.detail && !simpleMode && (
                            <p className="text-gray-500 text-xs mt-2 font-mono">{action.detail}</p>
                          )}
                        </div>
                      ))}
                    {simpleMode && (
                      <p className="text-gray-500 text-sm text-center py-4">
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
        <footer className="text-center py-6 text-gray-500 text-sm border-t border-white/10">
          Built with Next.js • 12 Agents • FastAPI Backend
          {demoMode && <span className="ml-2">| 🎮 Demo Mode</span>}
          {simpleMode && <span className="ml-2">| 🎯 Simple Mode</span>}
        </footer>
      </div>
    </div>
  );
}
