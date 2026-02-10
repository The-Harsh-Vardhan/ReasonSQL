"use client";

import { useState, useEffect } from "react";
import Link from "next/link";

interface StatsData {
    totalQueries: number;
    successCount: number;
    totalTimeMs: number;
    queriesPerDay: Record<string, number>;
}

interface HistoryEntry {
    query: string;
    success: boolean;
    time: number;
    timestamp: number;
}

function loadJSON<T>(key: string, fallback: T): T {
    if (typeof window === "undefined") return fallback;
    try { const s = localStorage.getItem(key); return s ? JSON.parse(s) : fallback; } catch { return fallback; }
}

export default function DashboardPage() {
    const [stats, setStats] = useState<StatsData | null>(null);
    const [history, setHistory] = useState<HistoryEntry[]>([]);

    useEffect(() => {
        setStats(loadJSON("reasonsql_stats", { totalQueries: 0, successCount: 0, totalTimeMs: 0, queriesPerDay: {} }));
        setHistory(loadJSON("reasonsql_history", []));
    }, []);

    if (!stats) return null;

    const successRate = stats.totalQueries > 0 ? Math.round((stats.successCount / stats.totalQueries) * 100) : 0;
    const avgTime = stats.totalQueries > 0 ? Math.round(stats.totalTimeMs / stats.totalQueries) : 0;

    // Last 7 days chart data
    const last7Days = Array.from({ length: 7 }, (_, i) => {
        const d = new Date();
        d.setDate(d.getDate() - (6 - i));
        return d.toISOString().split("T")[0];
    });
    const maxDayCount = Math.max(1, ...last7Days.map(d => stats.queriesPerDay[d] || 0));

    // Most used queries
    const queryCounts: Record<string, number> = {};
    history.forEach(h => { queryCounts[h.query] = (queryCounts[h.query] || 0) + 1; });
    const topQueries = Object.entries(queryCounts).sort((a, b) => b[1] - a[1]).slice(0, 5);

    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-950 via-blue-950 to-emerald-950 bg-orbs bg-grid-pattern">
            {/* Header */}
            <header className="border-b border-white/10 backdrop-blur-xl bg-black/20">
                <div className="max-w-5xl mx-auto px-6 py-5 flex items-center justify-between">
                    <div className="flex items-center gap-4">
                        <Link href="/" className="text-gray-400 hover:text-white transition-colors">
                            ← Back
                        </Link>
                        <h1 className="text-xl font-bold bg-gradient-to-r from-cyan-400 to-emerald-400 bg-clip-text text-transparent">
                            Analytics Dashboard
                        </h1>
                    </div>
                    <span className="text-xs text-gray-500">Local stats (stored in browser)</span>
                </div>
            </header>

            <main className="max-w-5xl mx-auto px-6 py-8 space-y-8">
                {/* KPI Cards */}
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                    {[
                        { label: "Total Queries", value: stats.totalQueries, color: "cyan", icon: "📊" },
                        { label: "Success Rate", value: `${successRate}%`, color: "emerald", icon: "✅" },
                        { label: "Avg Time", value: `${avgTime}ms`, color: "amber", icon: "⚡" },
                        { label: "Sessions", value: Object.keys(stats.queriesPerDay).length, color: "purple", icon: "📅" },
                    ].map((kpi, i) => (
                        <div key={i} className={`glass-card rounded-2xl p-5 border border-${kpi.color}-500/20 bg-gradient-to-br from-${kpi.color}-500/10 to-transparent`}>
                            <div className="flex items-center justify-between mb-2">
                                <span className="text-2xl">{kpi.icon}</span>
                            </div>
                            <div className={`text-3xl font-bold bg-gradient-to-r from-${kpi.color}-400 to-${kpi.color}-300 bg-clip-text text-transparent`}>
                                {kpi.value}
                            </div>
                            <div className="text-xs text-gray-400 mt-1">{kpi.label}</div>
                        </div>
                    ))}
                </div>

                {/* Chart: Queries per Day */}
                <div className="glass-card rounded-2xl p-6 border border-white/10">
                    <h2 className="text-lg font-semibold text-white mb-4">Queries — Last 7 Days</h2>
                    <div className="flex items-end gap-3 h-40">
                        {last7Days.map((day, i) => {
                            const count = stats.queriesPerDay[day] || 0;
                            const height = maxDayCount > 0 ? (count / maxDayCount) * 100 : 0;
                            return (
                                <div key={i} className="flex-1 flex flex-col items-center gap-2">
                                    <span className="text-xs text-gray-400">{count}</span>
                                    <div className="w-full rounded-t-lg bg-gradient-to-t from-cyan-500/50 to-emerald-500/50 transition-all duration-500"
                                        style={{ height: `${Math.max(height, 4)}%` }} />
                                    <span className="text-[10px] text-gray-500">{day.slice(5)}</span>
                                </div>
                            );
                        })}
                    </div>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    {/* Success Rate Ring */}
                    <div className="glass-card rounded-2xl p-6 border border-white/10">
                        <h2 className="text-lg font-semibold text-white mb-4">Success Rate</h2>
                        <div className="flex items-center justify-center">
                            <div className="relative w-40 h-40">
                                <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
                                    <circle cx="50" cy="50" r="40" stroke="#1e293b" strokeWidth="8" fill="none" />
                                    <circle cx="50" cy="50" r="40"
                                        stroke="url(#grad)" strokeWidth="8" fill="none"
                                        strokeDasharray={`${successRate * 2.51} ${251 - successRate * 2.51}`}
                                        strokeLinecap="round"
                                        className="transition-all duration-1000" />
                                    <defs>
                                        <linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="0%">
                                            <stop offset="0%" stopColor="#06b6d4" />
                                            <stop offset="100%" stopColor="#10b981" />
                                        </linearGradient>
                                    </defs>
                                </svg>
                                <div className="absolute inset-0 flex flex-col items-center justify-center">
                                    <span className="text-3xl font-bold text-white">{successRate}%</span>
                                    <span className="text-xs text-gray-400">success</span>
                                </div>
                            </div>
                        </div>
                        <div className="flex justify-center gap-6 mt-4 text-sm">
                            <div className="text-center">
                                <div className="text-emerald-400 font-semibold">{stats.successCount}</div>
                                <div className="text-xs text-gray-500">Success</div>
                            </div>
                            <div className="text-center">
                                <div className="text-red-400 font-semibold">{stats.totalQueries - stats.successCount}</div>
                                <div className="text-xs text-gray-500">Failed</div>
                            </div>
                        </div>
                    </div>

                    {/* Top Queries */}
                    <div className="glass-card rounded-2xl p-6 border border-white/10">
                        <h2 className="text-lg font-semibold text-white mb-4">Most Used Queries</h2>
                        {topQueries.length === 0 ? (
                            <p className="text-gray-500 text-sm text-center py-8">No queries yet. Run some queries to see your top picks!</p>
                        ) : (
                            <div className="space-y-3">
                                {topQueries.map(([q, count], i) => (
                                    <div key={i} className="flex items-center gap-3">
                                        <span className="text-xs text-gray-500 w-5">{i + 1}.</span>
                                        <div className="flex-1 min-w-0">
                                            <div className="text-sm text-gray-300 truncate">{q}</div>
                                            <div className="h-1.5 mt-1 rounded-full bg-white/5 overflow-hidden">
                                                <div className="h-full rounded-full bg-gradient-to-r from-cyan-500 to-emerald-500 transition-all"
                                                    style={{ width: `${(count / topQueries[0][1]) * 100}%` }} />
                                            </div>
                                        </div>
                                        <span className="text-xs text-cyan-400 font-medium">{count}×</span>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>

                {/* Recent Query Log */}
                <div className="glass-card rounded-2xl p-6 border border-white/10">
                    <h2 className="text-lg font-semibold text-white mb-4">Recent Query Log</h2>
                    {history.length === 0 ? (
                        <p className="text-gray-500 text-sm text-center py-8">No queries run yet.</p>
                    ) : (
                        <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                                <thead>
                                    <tr className="border-b border-white/10">
                                        <th className="text-left py-2 px-3 text-gray-400 font-medium">Query</th>
                                        <th className="text-center py-2 px-3 text-gray-400 font-medium">Status</th>
                                        <th className="text-right py-2 px-3 text-gray-400 font-medium">Time</th>
                                        <th className="text-right py-2 px-3 text-gray-400 font-medium">When</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {history.slice(-10).reverse().map((h, i) => (
                                        <tr key={i} className="border-b border-white/5 hover:bg-white/5 transition-colors">
                                            <td className="py-2.5 px-3 text-gray-300 max-w-xs truncate">{h.query}</td>
                                            <td className="py-2.5 px-3 text-center">
                                                <span className={`px-2 py-0.5 rounded-full text-xs ${h.success ? "bg-emerald-500/20 text-emerald-300" : "bg-red-500/20 text-red-300"}`}>
                                                    {h.success ? "OK" : "Fail"}
                                                </span>
                                            </td>
                                            <td className="py-2.5 px-3 text-right text-gray-400">{h.time.toFixed(0)}ms</td>
                                            <td className="py-2.5 px-3 text-right text-gray-500 text-xs">
                                                {new Date(h.timestamp).toLocaleTimeString()}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>
            </main>
        </div>
    );
}
