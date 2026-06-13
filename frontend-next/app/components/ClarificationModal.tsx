"use client";

import { useState } from "react";

interface ClarificationModalProps {
  isOpen: boolean;
  questions: string[];
  originalQuery: string;
  onSubmit: (clarification: string) => void;
  onDismiss: () => void;
}

export default function ClarificationModal({
  isOpen,
  questions,
  originalQuery,
  onSubmit,
  onDismiss,
}: ClarificationModalProps) {
  const [text, setText] = useState("");

  if (!isOpen) return null;

  const handleSubmit = () => {
    const val = text.trim();
    if (!val) return;
    onSubmit(val);
    setText("");
  };

  // Extract questions from the answer text (the LLM returns them as markdown)
  const parsedQuestions = questions.length > 0
    ? questions
    : [];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onDismiss}
      />

      {/* Modal */}
      <div className="relative z-10 w-full max-w-lg mx-4 bg-gradient-to-br from-slate-900 to-slate-800 border border-amber-500/30 rounded-2xl p-6 shadow-2xl shadow-amber-500/10">
        {/* Header */}
        <div className="flex items-start justify-between mb-5">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-2xl">❓</span>
              <h2 className="text-lg font-semibold text-white">Clarification Needed</h2>
            </div>
            <p className="text-sm text-gray-400">
              Your query has some ambiguous terms. Please clarify:
            </p>
          </div>
          <button
            onClick={onDismiss}
            className="text-gray-500 hover:text-white transition-colors p-1"
          >
            ✕
          </button>
        </div>

        {/* Original query */}
        <div className="mb-4 px-3 py-2 bg-white/5 rounded-lg border border-white/10">
          <p className="text-xs text-gray-500 mb-1">Your query:</p>
          <p className="text-sm text-gray-300 italic">&ldquo;{originalQuery}&rdquo;</p>
        </div>

        {/* Questions */}
        {parsedQuestions.length > 0 && (
          <div className="mb-4 space-y-2">
            <p className="text-xs text-amber-400 uppercase tracking-wider">The agent is asking:</p>
            <ul className="space-y-1.5">
              {parsedQuestions.map((q, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-gray-300">
                  <span className="text-amber-400 mt-0.5">•</span>
                  <span>{q}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Clarification input */}
        <div className="mb-4">
          <label className="block text-xs text-gray-400 mb-1.5">Your clarification:</label>
          <textarea
            id="clarification-input"
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSubmit();
              }
            }}
            placeholder='e.g. "last 30 days", "by revenue descending", "top 10"...'
            rows={3}
            className="w-full bg-black/30 border border-white/15 rounded-xl px-4 py-3 text-sm text-white placeholder:text-gray-600 focus:outline-none focus:border-amber-500/50 resize-none"
            autoFocus
          />
          <p className="text-xs text-gray-600 mt-1">Press Enter or click Submit</p>
        </div>

        {/* Quick suggestion chips */}
        <div className="flex flex-wrap gap-2 mb-5">
          {["last 30 days", "last year", "top 5", "top 10", "by count descending", "by revenue"].map((sug) => (
            <button
              key={sug}
              onClick={() => setText(sug)}
              className="px-2.5 py-1 text-xs rounded-full bg-white/5 border border-white/10 text-gray-400 hover:bg-amber-500/15 hover:border-amber-500/30 hover:text-amber-300 transition-all"
            >
              {sug}
            </button>
          ))}
        </div>

        {/* Actions */}
        <div className="flex gap-3 justify-end">
          <button
            onClick={onDismiss}
            className="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors rounded-xl hover:bg-white/5"
          >
            Cancel
          </button>
          <button
            id="clarification-submit"
            onClick={handleSubmit}
            disabled={!text.trim()}
            className="px-5 py-2 text-sm font-medium rounded-xl bg-gradient-to-r from-amber-500 to-orange-500 text-white hover:from-amber-400 hover:to-orange-400 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
          >
            Submit Clarification
          </button>
        </div>
      </div>
    </div>
  );
}
