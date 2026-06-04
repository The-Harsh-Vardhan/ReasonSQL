"use client";

import { useState, useRef, useCallback } from "react";
import { useToast } from "./Toast";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface TableResult {
  table: string;
  columns: string[];
  rows_processed: number;
  rows_inserted: number;
}

interface UploadResult {
  file_type: "csv" | "excel" | "sqlite";
  tables: TableResult[];
}

interface FileUploadModalProps {
  open: boolean;
  onClose: () => void;
  apiBase: string;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SUPPORTED_EXTENSIONS = [".csv", ".xlsx", ".xls", ".db", ".sqlite"];
const ACCEPT_ATTR = SUPPORTED_EXTENSIONS.join(",");

type FileType = "csv" | "excel" | "sqlite" | null;

function detectFileType(filename: string): FileType {
  const lower = filename.toLowerCase();
  if (lower.endsWith(".csv")) return "csv";
  if (lower.endsWith(".xlsx") || lower.endsWith(".xls")) return "excel";
  if (lower.endsWith(".db") || lower.endsWith(".sqlite")) return "sqlite";
  return null;
}

function isSupported(filename: string): boolean {
  return detectFileType(filename) !== null;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function FileTypeBadge({ type }: { type: FileType }) {
  if (!type) return null;
  const config: Record<NonNullable<FileType>, { label: string; color: string; icon: React.ReactNode }> = {
    csv: {
      label: "CSV",
      color: "bg-emerald-500/20 text-emerald-300 border-emerald-500/30",
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      ),
    },
    excel: {
      label: "Excel",
      color: "bg-green-500/20 text-green-300 border-green-500/30",
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
        </svg>
      ),
    },
    sqlite: {
      label: "SQLite DB",
      color: "bg-violet-500/20 text-violet-300 border-violet-500/30",
      icon: (
        <svg xmlns="http://www.w3.org/2000/svg" className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4" />
        </svg>
      ),
    },
  };
  const c = config[type];
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border ${c.color}`}>
      {c.icon}
      {c.label}
    </span>
  );
}

function TableResultRow({ t, isOnly }: { t: TableResult; isOnly: boolean }) {
  return (
    <div className={`flex items-center justify-between gap-3 ${!isOnly ? "py-2 border-b border-white/5 last:border-b-0" : ""}`}>
      <div className="flex items-center gap-2 min-w-0">
        <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
        </svg>
        <span className="text-white font-mono text-sm truncate">{t.table}</span>
      </div>
      <span className="text-gray-400 text-xs flex-shrink-0">
        {t.rows_inserted.toLocaleString()} rows
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function FileUploadModal({ open, onClose, apiBase }: FileUploadModalProps) {
  const { addToast } = useToast();
  const [dragActive, setDragActive] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [fileType, setFileType] = useState<FileType>(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<UploadResult | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // ── Helpers ──────────────────────────────────────────────────────────────

  const reset = useCallback(() => {
    setFile(null);
    setFileType(null);
    setResult(null);
    setDragActive(false);
  }, []);

  const handleClose = () => {
    reset();
    onClose();
  };

  const selectFile = (f: File) => {
    const type = detectFileType(f.name);
    if (!type) {
      addToast(`Unsupported file type. Use: ${SUPPORTED_EXTENSIONS.join(", ")}`, "error");
      return;
    }
    setFile(f);
    setFileType(type);
    setResult(null);
  };

  // ── Drag & drop ──────────────────────────────────────────────────────────

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") setDragActive(true);
    else if (e.type === "dragleave") setDragActive(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    const dropped = e.dataTransfer.files?.[0];
    if (dropped) selectFile(dropped);
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (selected) selectFile(selected);
    // Reset input so same file can be re-selected
    e.target.value = "";
  };

  // ── Upload ────────────────────────────────────────────────────────────────

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

      const data: UploadResult = await res.json();
      setResult(data);

      const tableCount = data.tables.length;
      const totalRows = data.tables.reduce((s, t) => s + t.rows_inserted, 0);
      const msg =
        tableCount === 1
          ? `Table "${data.tables[0].table}" created with ${totalRows.toLocaleString()} rows`
          : `${tableCount} tables imported (${totalRows.toLocaleString()} total rows)`;
      addToast(msg, "success");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Upload failed";
      addToast(msg, "error");
    } finally {
      setUploading(false);
    }
  };

  // ── Formatting ────────────────────────────────────────────────────────────

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  // ── Render ────────────────────────────────────────────────────────────────

  if (!open) return null;

  const dropzoneClass = [
    "relative cursor-pointer rounded-xl border-2 border-dashed p-8 text-center transition-all duration-300",
    dragActive
      ? "border-cyan-400 bg-cyan-500/10 scale-[1.02]"
      : file
        ? "border-emerald-500/40 bg-emerald-500/5"
        : "border-white/20 bg-white/5 hover:border-cyan-400/40 hover:bg-cyan-500/5",
  ].join(" ");

  const exampleQuery =
    result && result.tables.length > 0
      ? `Show me data from ${result.tables[0].table}`
      : "";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={handleClose} />

      {/* Modal */}
      <div className="relative w-full max-w-lg mx-4 rounded-2xl border border-white/10 bg-slate-900/95 backdrop-blur-xl shadow-2xl shadow-violet-500/10 animate-fade-in">

        {/* ── Header ── */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/10">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-violet-500 to-cyan-500 flex items-center justify-center shadow-lg shadow-violet-500/25">
              <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
              </svg>
            </div>
            <div>
              <h2 className="text-white font-semibold">Upload Data File</h2>
              <p className="text-gray-400 text-xs">CSV · Excel · SQLite Database</p>
            </div>
          </div>
          <button
            onClick={handleClose}
            className="p-2 rounded-lg hover:bg-white/10 text-gray-400 hover:text-white transition-colors"
            aria-label="Close"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* ── Body ── */}
        <div className="p-6">

          {/* Drop zone */}
          <div
            id="file-upload-dropzone"
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={dropzoneClass}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept={ACCEPT_ATTR}
              onChange={handleFileSelect}
              className="hidden"
              id="file-upload-input"
            />

            {file ? (
              /* File selected state */
              <div className="space-y-3">
                <div className="w-13 h-13 mx-auto rounded-xl bg-emerald-500/20 flex items-center justify-center w-14 h-14">
                  {fileType === "sqlite" ? (
                    <svg xmlns="http://www.w3.org/2000/svg" className="w-7 h-7 text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4" />
                    </svg>
                  ) : (
                    <svg xmlns="http://www.w3.org/2000/svg" className="w-7 h-7 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                  )}
                </div>
                <div className="flex items-center justify-center gap-2 flex-wrap">
                  <p className="text-white font-medium">{file.name}</p>
                  <FileTypeBadge type={fileType} />
                </div>
                <p className="text-gray-400 text-sm">{formatSize(file.size)}</p>
                <button
                  onClick={(e) => { e.stopPropagation(); reset(); }}
                  className="text-xs text-gray-500 hover:text-red-400 transition-colors mt-1 underline underline-offset-2"
                >
                  Remove
                </button>
              </div>
            ) : (
              /* Empty state */
              <div className="space-y-4">
                {/* Icons for all 3 types */}
                <div className="flex items-center justify-center gap-3">
                  {(["csv", "excel", "sqlite"] as const).map((type) => {
                    const icons = {
                      csv: { color: "bg-emerald-500/15 text-emerald-400", title: "CSV",
                        path: "M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" },
                      excel: { color: "bg-green-500/15 text-green-400", title: "Excel",
                        path: "M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" },
                      sqlite: { color: "bg-violet-500/15 text-violet-400", title: "SQLite",
                        path: "M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4" },
                    };
                    const icon = icons[type];
                    return (
                      <div key={type} className="flex flex-col items-center gap-1.5">
                        <div className={`w-10 h-10 rounded-xl ${icon.color} flex items-center justify-center`}>
                          <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                            <path strokeLinecap="round" strokeLinejoin="round" d={icon.path} />
                          </svg>
                        </div>
                        <span className="text-[10px] text-gray-500">{icon.title}</span>
                      </div>
                    );
                  })}
                </div>
                <div>
                  <p className="text-white font-medium">Drop your file here</p>
                  <p className="text-gray-400 text-sm mt-1">or click to browse</p>
                </div>
                <p className="text-gray-600 text-xs">
                  .csv · .xlsx · .xls · .db · .sqlite
                </p>
              </div>
            )}
          </div>

          {/* ── Success result ── */}
          {result && (
            <div className="mt-4 p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 animate-fade-in">
              <div className="flex items-center gap-2 mb-3">
                <div className="w-7 h-7 rounded-full bg-emerald-500/20 flex items-center justify-center flex-shrink-0">
                  <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <p className="text-emerald-300 font-medium text-sm">
                  {result.tables.length === 1
                    ? "Table created successfully!"
                    : `${result.tables.length} tables imported!`}
                </p>
                <FileTypeBadge type={result.file_type} />
              </div>

              {/* Table list */}
              <div className={`${result.tables.length > 1 ? "space-y-0 divide-y divide-white/5" : ""}`}>
                {result.tables.map((t) => (
                  <TableResultRow key={t.table} t={t} isOnly={result.tables.length === 1} />
                ))}
              </div>

              {/* Query hint */}
              {exampleQuery && (
                <p className="text-gray-500 text-xs mt-3 pl-1">
                  Try: <span className="text-cyan-400 font-mono">&quot;{exampleQuery}&quot;</span>
                </p>
              )}
            </div>
          )}

          {/* ── Info note ── */}
          <div className="mt-4 flex items-start gap-2 text-xs text-gray-500">
            <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span>
              Column types are auto-detected. Table names come from the file name (SQLite: all tables are imported). Max 50 MB.
            </span>
          </div>
        </div>

        {/* ── Footer ── */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-white/10">
          <button
            id="file-upload-cancel"
            onClick={handleClose}
            className="px-4 py-2 rounded-xl text-sm text-gray-400 hover:text-white hover:bg-white/10 transition-all"
          >
            {result ? "Done" : "Cancel"}
          </button>
          {!result && (
            <button
              id="file-upload-submit"
              onClick={handleUpload}
              disabled={!file || uploading}
              className={`px-5 py-2 rounded-xl text-sm font-medium transition-all duration-300 ${
                !file || uploading
                  ? "bg-white/5 text-gray-600 cursor-not-allowed"
                  : "bg-gradient-to-r from-violet-500 to-cyan-500 text-white hover:shadow-lg hover:shadow-violet-500/25 hover:scale-[1.02]"
              }`}
            >
              {uploading ? (
                <span className="flex items-center gap-2">
                  <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Uploading…
                </span>
              ) : (
                "Upload & Import"
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
