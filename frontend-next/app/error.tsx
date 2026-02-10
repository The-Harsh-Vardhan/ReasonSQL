"use client";

import { useEffect } from "react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Log the error to console for debugging
    console.error("Application Error:", error);
  }, [error]);

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-8">
      <div className="max-w-md w-full bg-slate-900 rounded-xl p-8 border border-red-500/30">
        <h2 className="text-2xl font-bold text-red-400 mb-4">
          Something went wrong!
        </h2>
        <p className="text-gray-400 mb-4">
          An error occurred while loading the application.
        </p>
        <div className="bg-black/40 rounded-lg p-4 mb-6 overflow-x-auto">
          <code className="text-red-300 text-sm font-mono break-words">
            {error.message}
          </code>
        </div>
        {error.digest && (
          <p className="text-gray-500 text-xs mb-4">
            Error ID: {error.digest}
          </p>
        )}
        <button
          onClick={reset}
          className="w-full px-4 py-3 bg-gradient-to-r from-cyan-500 to-emerald-500 text-white font-semibold rounded-lg hover:from-cyan-400 hover:to-emerald-400 transition-all"
        >
          Try Again
        </button>
      </div>
    </div>
  );
}
