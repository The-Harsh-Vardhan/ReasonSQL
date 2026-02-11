"use client";

import { useState, useRef, useCallback } from "react";
import { useToast } from "./Toast";

interface CsvUploadModalProps {
    open: boolean;
    onClose: () => void;
    apiBase: string;
}

export default function CsvUploadModal({ open, onClose, apiBase }: CsvUploadModalProps) {
    const { addToast } = useToast();
    const [dragActive, setDragActive] = useState(false);
    const [file, setFile] = useState<File | null>(null);
    const [uploading, setUploading] = useState(false);
    const [result, setResult] = useState<{ table: string; rows: number } | null>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const reset = useCallback(() => {
        setFile(null);
        setResult(null);
        setDragActive(false);
    }, []);

    const handleClose = () => {
        reset();
        onClose();
    };

    const handleDrag = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        if (e.type === "dragenter" || e.type === "dragover") {
            setDragActive(true);
        } else if (e.type === "dragleave") {
            setDragActive(false);
        }
    };

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setDragActive(false);
        const droppedFile = e.dataTransfer.files?.[0];
        if (droppedFile?.name.endsWith(".csv")) {
            setFile(droppedFile);
            setResult(null);
        } else {
            addToast("Only .csv files are supported", "error");
        }
    };

    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        const selected = e.target.files?.[0];
        if (selected) {
            setFile(selected);
            setResult(null);
        }
    };

    const handleUpload = async () => {
        if (!file) return;
        setUploading(true);
        setResult(null);

        try {
            const formData = new FormData();
            formData.append("file", file);

            const base = apiBase.replace(/\/+$/, "");
            const res = await fetch(`${base}/upload`, {
                method: "POST",
                body: formData,
            });

            if (!res.ok) {
                const err = await res.json().catch(() => ({ detail: "Upload failed" }));
                throw new Error(err.detail || `HTTP ${res.status}`);
            }

            const data = await res.json();
            setResult({ table: data.table, rows: data.rows_inserted });
            addToast(`Table "${data.table}" created with ${data.rows_inserted} rows`, "success");
        } catch (err) {
            const msg = err instanceof Error ? err.message : "Upload failed";
            addToast(msg, "error");
        } finally {
            setUploading(false);
        }
    };

    const formatSize = (bytes: number) => {
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    };

    if (!open) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
            {/* Backdrop */}
            <div
                className="absolute inset-0 bg-black/60 backdrop-blur-sm"
                onClick={handleClose}
            />

            {/* Modal */}
            <div className="relative w-full max-w-lg mx-4 rounded-2xl border border-white/10 bg-slate-900/95 backdrop-blur-xl shadow-2xl shadow-cyan-500/10 animate-fade-in">
                {/* Header */}
                <div className="flex items-center justify-between px-6 py-4 border-b border-white/10">
                    <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-500 to-emerald-500 flex items-center justify-center">
                            <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                            </svg>
                        </div>
                        <div>
                            <h2 className="text-white font-semibold">Upload CSV</h2>
                            <p className="text-gray-400 text-xs">Create a new table from your data</p>
                        </div>
                    </div>
                    <button
                        onClick={handleClose}
                        className="p-2 rounded-lg hover:bg-white/10 text-gray-400 hover:text-white transition-colors"
                    >
                        <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>

                {/* Body */}
                <div className="p-6">
                    {/* Drop zone */}
                    <div
                        onDragEnter={handleDrag}
                        onDragLeave={handleDrag}
                        onDragOver={handleDrag}
                        onDrop={handleDrop}
                        onClick={() => fileInputRef.current?.click()}
                        className={`relative cursor-pointer rounded-xl border-2 border-dashed p-8 text-center transition-all duration-300
              ${dragActive
                                ? "border-cyan-400 bg-cyan-500/10 scale-[1.02]"
                                : file
                                    ? "border-emerald-500/40 bg-emerald-500/5"
                                    : "border-white/20 bg-white/5 hover:border-cyan-400/40 hover:bg-cyan-500/5"
                            }`}
                    >
                        <input
                            ref={fileInputRef}
                            type="file"
                            accept=".csv"
                            onChange={handleFileSelect}
                            className="hidden"
                        />

                        {file ? (
                            <div className="space-y-2">
                                <div className="w-12 h-12 mx-auto rounded-xl bg-emerald-500/20 flex items-center justify-center">
                                    <svg xmlns="http://www.w3.org/2000/svg" className="w-6 h-6 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                    </svg>
                                </div>
                                <p className="text-white font-medium">{file.name}</p>
                                <p className="text-gray-400 text-sm">{formatSize(file.size)}</p>
                                <button
                                    onClick={(e) => { e.stopPropagation(); reset(); }}
                                    className="text-xs text-gray-500 hover:text-red-400 transition-colors mt-1"
                                >
                                    Remove
                                </button>
                            </div>
                        ) : (
                            <div className="space-y-3">
                                <div className="w-12 h-12 mx-auto rounded-xl bg-white/10 flex items-center justify-center">
                                    <svg xmlns="http://www.w3.org/2000/svg" className="w-6 h-6 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                                        <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                                    </svg>
                                </div>
                                <div>
                                    <p className="text-white font-medium">Drop your CSV file here</p>
                                    <p className="text-gray-400 text-sm mt-1">or click to browse</p>
                                </div>
                                <p className="text-gray-600 text-xs">.csv files only</p>
                            </div>
                        )}
                    </div>

                    {/* Success result */}
                    {result && (
                        <div className="mt-4 p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 animate-fade-in">
                            <div className="flex items-center gap-3">
                                <div className="w-8 h-8 rounded-full bg-emerald-500/20 flex items-center justify-center flex-shrink-0">
                                    <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                                        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                                    </svg>
                                </div>
                                <div>
                                    <p className="text-emerald-300 font-medium text-sm">Table created successfully!</p>
                                    <p className="text-gray-400 text-xs mt-0.5">
                                        <span className="text-white font-mono">{result.table}</span> — {result.rows} rows inserted
                                    </p>
                                </div>
                            </div>
                            <p className="text-gray-500 text-xs mt-3 ml-11">
                                Try querying: &quot;Show me data from {result.table}&quot;
                            </p>
                        </div>
                    )}

                    {/* Info note */}
                    <div className="mt-4 flex items-start gap-2 text-xs text-gray-500">
                        <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        <span>Column types are auto-detected. The table name is derived from the filename. You can query it immediately after upload.</span>
                    </div>
                </div>

                {/* Footer */}
                <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-white/10">
                    <button
                        onClick={handleClose}
                        className="px-4 py-2 rounded-xl text-sm text-gray-400 hover:text-white hover:bg-white/10 transition-all"
                    >
                        {result ? "Done" : "Cancel"}
                    </button>
                    {!result && (
                        <button
                            onClick={handleUpload}
                            disabled={!file || uploading}
                            className={`px-5 py-2 rounded-xl text-sm font-medium transition-all duration-300
                ${!file || uploading
                                    ? "bg-white/5 text-gray-600 cursor-not-allowed"
                                    : "bg-gradient-to-r from-cyan-500 to-emerald-500 text-white hover:shadow-lg hover:shadow-cyan-500/25 hover:scale-[1.02]"
                                }`}
                        >
                            {uploading ? (
                                <span className="flex items-center gap-2">
                                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                    Uploading...
                                </span>
                            ) : (
                                "Upload & Create Table"
                            )}
                        </button>
                    )}
                </div>
            </div>
        </div>
    );
}
