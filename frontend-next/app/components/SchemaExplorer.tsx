"use client";

import { useState, useEffect, useCallback } from "react";

interface TableColumn {
    name: string;
    type: string;
}

interface TableInfo {
    name: string;
    columns: TableColumn[];
    row_count: number | null;
}

interface SchemaData {
    database_id: string;
    tables: TableInfo[];
}

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

export default function SchemaExplorer() {
    const [schema, setSchema] = useState<SchemaData | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [expandedTable, setExpandedTable] = useState<string | null>(null);
    const [isOpen, setIsOpen] = useState(false);

    const fetchSchema = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await fetch(buildApiUrl("databases/default/schema"), {
                signal: AbortSignal.timeout(20000),
            });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data: SchemaData = await res.json();
            setSchema(data);
        } catch (err) {
            setError(String(err));
        }
        setLoading(false);
    }, []);

    useEffect(() => {
        if (isOpen && !schema && !loading) {
            fetchSchema();
        }
    }, [isOpen, schema, loading, fetchSchema]);

    const typeColor = (type: string) => {
        const t = type.toLowerCase();
        if (t.includes("int") || t.includes("numeric") || t.includes("real") || t.includes("float")) return "text-blue-400";
        if (t.includes("char") || t.includes("text") || t.includes("varchar")) return "text-emerald-400";
        if (t.includes("date") || t.includes("time")) return "text-amber-400";
        if (t.includes("bool")) return "text-purple-400";
        return "text-gray-400";
    };

    return (
        <div className="mb-6">
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="flex items-center justify-between w-full text-left mb-3"
            >
                <h3 className="text-gray-400 text-sm uppercase tracking-wider">Schema Explorer</h3>
                <svg
                    xmlns="http://www.w3.org/2000/svg"
                    className={`w-4 h-4 text-gray-500 transition-transform ${isOpen ? "rotate-180" : ""}`}
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2}
                >
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                </svg>
            </button>

            {isOpen && (
                <div className="space-y-1.5 max-h-64 overflow-y-auto pr-1">
                    {loading && (
                        <div className="text-xs text-gray-500 py-3 text-center">
                            <span className="inline-block w-4 h-4 border-2 border-gray-600 border-t-cyan-400 rounded-full animate-spin mr-2" />
                            Loading schema...
                        </div>
                    )}

                    {error && (
                        <div className="text-xs text-red-400 py-2 px-3 bg-red-500/10 rounded-lg border border-red-500/20">
                            {error}
                        </div>
                    )}

                    {schema && schema.tables.map((table) => (
                        <div key={table.name} className="rounded-lg border border-white/5 overflow-hidden">
                            <button
                                onClick={() => setExpandedTable(expandedTable === table.name ? null : table.name)}
                                className="w-full flex items-center gap-2 px-3 py-2 bg-white/5 hover:bg-white/8 transition-colors text-left"
                            >
                                {/* Table icon */}
                                <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5 text-cyan-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                                </svg>
                                <span className="text-xs text-gray-200 font-mono flex-1 truncate">{table.name}</span>
                                <span className="text-[10px] text-gray-500">{table.columns.length} cols</span>
                                {table.row_count !== null && (
                                    <span className="text-[10px] text-gray-600">{table.row_count} rows</span>
                                )}
                                <svg
                                    xmlns="http://www.w3.org/2000/svg"
                                    className={`w-3 h-3 text-gray-600 transition-transform ${expandedTable === table.name ? "rotate-180" : ""}`}
                                    fill="none"
                                    viewBox="0 0 24 24"
                                    stroke="currentColor"
                                    strokeWidth={2}
                                >
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                                </svg>
                            </button>

                            {expandedTable === table.name && (
                                <div className="bg-black/20 px-3 py-1.5 space-y-0.5">
                                    {table.columns.map((col) => (
                                        <div key={col.name} className="flex items-center gap-2 py-0.5">
                                            <span className="text-[11px] text-gray-300 font-mono flex-1 truncate">{col.name}</span>
                                            <span className={`text-[10px] font-mono ${typeColor(col.type)}`}>{col.type}</span>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
