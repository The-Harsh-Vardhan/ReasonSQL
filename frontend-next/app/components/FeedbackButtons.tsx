"use client";

import { useState } from "react";

interface FeedbackButtonsProps {
  runId: string | null | undefined;
  apiBase: string;
}

type FeedbackState = "idle" | "loading" | "sent_up" | "sent_down" | "error";

export default function FeedbackButtons({ runId, apiBase }: FeedbackButtonsProps) {
  const [state, setState] = useState<FeedbackState>("idle");

  if (!runId) return null; // Don't render if no run_id (LangSmith not enabled)

  const submit = async (score: 0 | 1) => {
    setState("loading");
    try {
      const res = await fetch(`${apiBase}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ run_id: runId, score }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setState(score === 1 ? "sent_up" : "sent_down");
    } catch {
      setState("error");
      setTimeout(() => setState("idle"), 2000);
    }
  };

  if (state === "sent_up" || state === "sent_down") {
    return (
      <div className="flex items-center gap-2 text-sm text-emerald-400 animate-fade-in">
        <span className="text-lg">{state === "sent_up" ? "👍" : "👎"}</span>
        <span>Thanks for your feedback!</span>
      </div>
    );
  }

  if (state === "error") {
    return (
      <span className="text-xs text-red-400">Failed to submit feedback</span>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-gray-500">Was this helpful?</span>
      <button
        id="feedback-thumbs-up"
        disabled={state === "loading"}
        onClick={() => submit(1)}
        className="px-2 py-1 rounded-lg bg-white/5 border border-white/10 text-sm hover:bg-emerald-500/20 hover:border-emerald-500/30 hover:text-emerald-400 transition-all duration-200 disabled:opacity-50"
        title="This answer was helpful"
      >
        👍
      </button>
      <button
        id="feedback-thumbs-down"
        disabled={state === "loading"}
        onClick={() => submit(0)}
        className="px-2 py-1 rounded-lg bg-white/5 border border-white/10 text-sm hover:bg-red-500/20 hover:border-red-500/30 hover:text-red-400 transition-all duration-200 disabled:opacity-50"
        title="This answer was not helpful"
      >
        👎
      </button>
      {state === "loading" && (
        <div className="w-4 h-4 border-2 border-cyan-400/30 border-t-cyan-400 rounded-full animate-spin" />
      )}
    </div>
  );
}
