"use client";

import { useState, useEffect, useCallback } from "react";

interface HealthData {
    status: string;
    version: string;
    llm_provider: string | null;
    database_connected: boolean;
    db_type: string | null;
    db_name: string | null;
    dataset_name: string | null;
    table_count: number;
    tables: string[];
}

// Reuse the same API base logic from page.tsx
const getApiBase = () => {
    const envUrl = process.env.NEXT_PUBLIC_API_URL;
    if (envUrl) return envUrl.replace(/\/+$/, "");
    if (typeof window !== "undefined" && window.location.hostname !== "localhost") return "/api";
    return "http://localhost:8000";
};

const buildApiUrl = (path: string) => {
    const base = getApiBase().replace(/\/+$/, "");
    const cleanPath = path.replace(/^\/+/, "");
    return `${base}/${cleanPath}`;
};

type ConnectionState = "checking" | "connected" | "disconnected";

export default function SystemStatus() {
    const [apiStatus, setApiStatus] = useState<ConnectionState>("checking");
    const [dbStatus, setDbStatus] = useState<ConnectionState>("checking");
    const [health, setHealth] = useState<HealthData | null>(null);
    const [lastChecked, setLastChecked] = useState<string>("");
    const [showTables, setShowTables] = useState(false);

    const checkHealth = useCallback(async () => {
        setApiStatus("checking");
        setDbStatus("checking");
        try {
            const res = await fetch(buildApiUrl("health"), { signal: AbortSignal.timeout(15000) });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data: HealthData = await res.json();

            setApiStatus("connected");
            setDbStatus(data.database_connected ? "connected" : "disconnected");
            setHealth(data);
        } catch {
            setApiStatus("disconnected");
            setDbStatus("disconnected");
            setHealth(null);
        }
        setLastChecked(new Date().toLocaleTimeString());
    }, []);

    useEffect(() => {
        checkHealth();
    }, [checkHealth]);

    const StatusDot = ({ state }: { state: ConnectionState }) => (
        <span
            className={`inline-block w-2.5 h-2.5 rounded-full flex-shrink-0 ${state === "connected"
                ? "bg-emerald-400 status-dot-pulse"
                : state === "disconnected"
                    ? "bg-red-400"
                    : "bg-yellow-400 animate-pulse"
                }`}
        />
    );

    const statusLabel = (state: ConnectionState) =>
        state === "connected" ? "Connected" : state === "disconnected" ? "Offline" : "Checking…";

    const statusColor = (state: ConnectionState) =>
        state === "connected" ? "text-emerald-400" : state === "disconnected" ? "text-red-400" : "text-yellow-400";

    return (
        <div className="mb-6">
            <div className="flex items-center justify-between mb-3">
                <h3 className="text-gray-400 text-sm uppercase tracking-wider">System Status</h3>
                <button
                    onClick={checkHealth}
                    title="Refresh status"
                    className="text-gray-500 hover:text-cyan-400 transition-colors p-1 rounded-lg hover:bg-white/5"
                >
                    <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                </button>
            </div>

            {/* Connection Status Rows */}
            <div className="space-y-2.5 mb-3">
                {/* API (Render) */}
                <div className="flex items-center gap-2.5 px-3 py-2 rounded-xl bg-white/5 border border-white/5">
                    <StatusDot state={apiStatus} />
                    <div className="flex-1 min-w-0">
                        <div className="text-xs text-gray-300 font-medium">API (Render)</div>
                    </div>
                    <span className={`text-xs font-medium ${statusColor(apiStatus)}`}>{statusLabel(apiStatus)}</span>
                </div>

                {/* Database (Supabase) */}
                <div className="flex items-center gap-2.5 px-3 py-2 rounded-xl bg-white/5 border border-white/5">
                    <StatusDot state={dbStatus} />
                    <div className="flex-1 min-w-0">
                        <div className="text-xs text-gray-300 font-medium">Database</div>
                    </div>
                    <span className={`text-xs font-medium ${statusColor(dbStatus)}`}>{statusLabel(dbStatus)}</span>
                </div>
            </div>

            {/* DB Info Card */}
            {health && health.database_connected && (
                <div className="rounded-xl bg-gradient-to-br from-indigo-500/10 to-purple-500/10 border border-indigo-500/20 p-3 space-y-2">
                    {/* DB Type Badge */}
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <span
                                className={`px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider ${health.db_type === "postgresql"
                                    ? "bg-blue-500/20 text-blue-300 border border-blue-500/30"
                                    : "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                                    }`}
                            >
                                {health.db_type === "postgresql" ? "PostgreSQL" : "SQLite"}
                            </span>
                            <span className="text-gray-400 text-[10px]">{health.version}</span>
                        </div>
                        {health.dataset_name && (
                            <span className="px-2 py-0.5 rounded-md text-[9px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 uppercase tracking-tighter">
                                {health.dataset_name}
                            </span>
                        )}
                    </div>

                    {/* DB Name */}
                    <div>
                        <div className="text-[10px] text-gray-500 uppercase tracking-wider">
                            {health.dataset_name ? "Dataset Source" : "Database"}
                        </div>
                        <div className="text-xs text-gray-300 truncate" title={health.db_name || ""}>
                            {health.dataset_name || health.db_name || "Unknown"}
                        </div>
                    </div>

                    {/* Table Count + toggle */}
                    <div>
                        <button
                            onClick={() => setShowTables(!showTables)}
                            className="flex items-center gap-1.5 text-[10px] text-gray-500 hover:text-cyan-400 transition-colors uppercase tracking-wider"
                        >
                            <span>{health.table_count} Tables</span>
                            <svg
                                xmlns="http://www.w3.org/2000/svg"
                                className={`w-3 h-3 transition-transform ${showTables ? "rotate-180" : ""}`}
                                fill="none"
                                viewBox="0 0 24 24"
                                stroke="currentColor"
                                strokeWidth={2}
                            >
                                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                            </svg>
                        </button>

                        {showTables && health.tables.length > 0 && (
                            <div className="mt-1.5 max-h-28 overflow-y-auto space-y-0.5 pr-1">
                                {health.tables.map((table) => (
                                    <div key={table} className="text-[11px] text-gray-400 px-2 py-1 rounded-md bg-black/20 font-mono">
                                        {table}
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* Last checked */}
            {lastChecked && (
                <div className="text-[10px] text-gray-600 mt-2 text-right">
                    Checked: {lastChecked}
                </div>
            )}
        </div>
    );
}
