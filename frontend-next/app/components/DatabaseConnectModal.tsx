"use client";

import { useState } from "react";

interface RegisteredDB {
  id: string;
  name: string;
  type: "postgres" | "sqlite";
  connected: boolean;
}

interface DatabaseConnectModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConnected: (db: RegisteredDB) => void;
  apiBase: string;
}

type FormState = "idle" | "loading" | "success" | "error";

export default function DatabaseConnectModal({
  isOpen,
  onClose,
  onConnected,
  apiBase,
}: DatabaseConnectModalProps) {
  const [dbType, setDbType] = useState<"postgres" | "sqlite">("postgres");
  const [dbId, setDbId] = useState("");
  const [connString, setConnString] = useState("");
  const [filePath, setFilePath] = useState("");
  const [formState, setFormState] = useState<FormState>("idle");
  const [errorMsg, setErrorMsg] = useState("");

  if (!isOpen) return null;

  const reset = () => {
    setDbId("");
    setConnString("");
    setFilePath("");
    setFormState("idle");
    setErrorMsg("");
  };

  const handleClose = () => {
    reset();
    onClose();
  };

  const handleSubmit = async () => {
    if (!dbId.trim()) {
      setErrorMsg("Database ID is required");
      return;
    }
    if (dbType === "postgres" && !connString.trim()) {
      setErrorMsg("Connection string is required for PostgreSQL");
      return;
    }
    if (dbType === "sqlite" && !filePath.trim()) {
      setErrorMsg("File path is required for SQLite");
      return;
    }

    setFormState("loading");
    setErrorMsg("");

    try {
      const body: Record<string, string> = {
        id: dbId.trim(),
        type: dbType,
      };
      if (dbType === "postgres") body.connection_string = connString.trim();
      if (dbType === "sqlite") body.file_path = filePath.trim();

      const res = await fetch(`${apiBase}/databases`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || `HTTP ${res.status}`);
      }

      setFormState("success");
      onConnected({
        id: data.id,
        name: dbId.trim(),
        type: dbType,
        connected: data.connected,
      });

      setTimeout(() => {
        handleClose();
      }, 1500);
    } catch (err: unknown) {
      setFormState("error");
      setErrorMsg(err instanceof Error ? err.message : "Failed to connect");
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={handleClose} />

      {/* Modal */}
      <div className="relative z-10 w-full max-w-lg mx-4 bg-gradient-to-br from-slate-900 to-slate-800 border border-white/15 rounded-2xl p-6 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500/20 to-purple-500/20 border border-indigo-500/30 flex items-center justify-center text-lg">
              🗄️
            </div>
            <div>
              <h2 className="text-base font-semibold text-white">Connect a Database</h2>
              <p className="text-xs text-gray-500">PostgreSQL or SQLite</p>
            </div>
          </div>
          <button onClick={handleClose} className="text-gray-500 hover:text-white transition-colors">
            ✕
          </button>
        </div>

        {/* DB Type toggle */}
        <div className="flex gap-2 mb-5 p-1 bg-white/5 rounded-xl border border-white/10">
          {(["postgres", "sqlite"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setDbType(t)}
              className={`flex-1 py-2 text-sm rounded-lg transition-all ${
                dbType === t
                  ? "bg-gradient-to-r from-indigo-500/30 to-purple-500/30 text-white border border-indigo-500/30"
                  : "text-gray-500 hover:text-gray-300"
              }`}
            >
              {t === "postgres" ? "🐘 PostgreSQL" : "📁 SQLite"}
            </button>
          ))}
        </div>

        {/* Fields */}
        <div className="space-y-4 mb-5">
          {/* DB ID */}
          <div>
            <label className="block text-xs text-gray-400 mb-1.5">
              Database ID <span className="text-red-400">*</span>
            </label>
            <input
              id="db-id-input"
              value={dbId}
              onChange={(e) => setDbId(e.target.value)}
              placeholder='e.g. "northwind", "my_db"'
              className="w-full bg-black/30 border border-white/15 rounded-xl px-4 py-2.5 text-sm text-white placeholder:text-gray-600 focus:outline-none focus:border-indigo-500/50"
            />
            <p className="text-xs text-gray-600 mt-1">Used to switch between databases in the query bar</p>
          </div>

          {dbType === "postgres" ? (
            <div>
              <label className="block text-xs text-gray-400 mb-1.5">
                PostgreSQL Connection String <span className="text-red-400">*</span>
              </label>
              <input
                id="db-conn-string-input"
                value={connString}
                onChange={(e) => setConnString(e.target.value)}
                placeholder="postgresql://user:password@host:5432/dbname"
                type="password"
                className="w-full bg-black/30 border border-white/15 rounded-xl px-4 py-2.5 text-sm text-white placeholder:text-gray-600 focus:outline-none focus:border-indigo-500/50 font-mono"
              />
              <p className="text-xs text-gray-600 mt-1">
                Supports: Supabase, Neon, Render Postgres, local Postgres
              </p>
            </div>
          ) : (
            <div>
              <label className="block text-xs text-gray-400 mb-1.5">
                SQLite File Path <span className="text-red-400">*</span>
              </label>
              <input
                id="db-file-path-input"
                value={filePath}
                onChange={(e) => setFilePath(e.target.value)}
                placeholder="./data/mydb.db"
                className="w-full bg-black/30 border border-white/15 rounded-xl px-4 py-2.5 text-sm text-white placeholder:text-gray-600 focus:outline-none focus:border-indigo-500/50 font-mono"
              />
            </div>
          )}
        </div>

        {/* Error */}
        {errorMsg && (
          <div className="mb-4 px-3 py-2 bg-red-500/10 border border-red-500/20 rounded-lg text-sm text-red-400">
            ⚠️ {errorMsg}
          </div>
        )}

        {/* Success */}
        {formState === "success" && (
          <div className="mb-4 px-3 py-2 bg-emerald-500/10 border border-emerald-500/20 rounded-lg text-sm text-emerald-400">
            ✅ Database connected successfully!
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-3 justify-end">
          <button
            onClick={handleClose}
            className="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors rounded-xl hover:bg-white/5"
          >
            Cancel
          </button>
          <button
            id="db-connect-submit"
            onClick={handleSubmit}
            disabled={formState === "loading" || formState === "success"}
            className="px-5 py-2 text-sm font-medium rounded-xl bg-gradient-to-r from-indigo-500 to-purple-500 text-white hover:from-indigo-400 hover:to-purple-400 disabled:opacity-40 disabled:cursor-not-allowed transition-all flex items-center gap-2"
          >
            {formState === "loading" ? (
              <>
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Connecting…
              </>
            ) : (
              "Connect Database"
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
