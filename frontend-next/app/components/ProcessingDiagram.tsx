"use client";

import { useEffect, useState } from "react";

interface PipelineBatch {
    id: number;
    icon: string;
    title: string;
    subtitle: string;
    duration: string;
    agents: string[];
    nodeKey: string; // Matches SSE node names
}

export interface LiveStreamEvent {
    node: string;
    label: string;
    icon: string;
    description: string;
    step: number;
}

const PIPELINE_BATCHES: PipelineBatch[] = [
    {
        id: 1,
        icon: "🔍",
        title: "Schema Retrieval",
        subtitle: "Hybrid FAISS + BM25 RAG",
        duration: "~300ms",
        nodeKey: "schema_retrieval",
        agents: ["FAISS Vector Search", "BM25 Keyword", "CrossEncoder Reranker"],
    },
    {
        id: 2,
        icon: "🧠",
        title: "Reasoning & Planning",
        subtitle: "Multi-agent intent analysis",
        duration: "~800ms",
        nodeKey: "reasoning",
        agents: ["IntentAnalyzer", "ClarificationAgent", "QueryDecomposer", "QueryPlanner"],
    },
    {
        id: 3,
        icon: "💾",
        title: "SQL Generation",
        subtitle: "Structured output + safety",
        duration: "~600ms",
        nodeKey: "sql_generation",
        agents: ["SQLGenerator", "SafetyValidator", "SQLExecutor", "SelfCorrectionAgent"],
    },
    {
        id: 4,
        icon: "✨",
        title: "Response Synthesis",
        subtitle: "Human-readable answer",
        duration: "~400ms",
        nodeKey: "response_synthesis",
        agents: ["ResponseSynthesizer"],
    },
];

// Map SSE node names to batch indices
const NODE_TO_BATCH: Record<string, number> = {
    schema_retrieval: 0,
    reasoning: 1,
    sql_generation: 2,
    safety_validation: 2,
    sql_execution: 2,
    self_correction: 2,
    response_synthesis: 3,
};

const COMPARISON_POINTS = [
    { naive: "Hallucinates table names", smart: "Explores schema via FAISS+BM25 BEFORE generating" },
    { naive: "Assumes meaning of 'recent', 'best'", smart: "ClarificationAgent asks & resolves ambiguity" },
    { naive: "Returns errors, not answers", smart: "SelfCorrectionAgent auto-fixes SQL (3x retry)" },
    { naive: "No safety (SELECT * on 1M rows)", smart: "Safety-validated, enforces LIMIT, no mutating SQL" },
    { naive: "Full schema in every prompt (token waste)", smart: "RAG: top-5 tables only via CrossEncoder reranking" },
];

interface ProcessingDiagramProps {
    streamEvents?: LiveStreamEvent[];
    isLive?: boolean;
}

export default function ProcessingDiagram({ streamEvents = [], isLive = false }: ProcessingDiagramProps) {
    const [activeBatch, setActiveBatch] = useState(0);
    const [comparisonIndex, setComparisonIndex] = useState(0);
    const [completedBatches, setCompletedBatches] = useState<Set<number>>(new Set());

    // When streaming live events, derive active batch from SSE events
    useEffect(() => {
        if (isLive && streamEvents.length > 0) {
            const lastEvent = streamEvents[streamEvents.length - 1];
            const batchIdx = NODE_TO_BATCH[lastEvent.node];
            if (batchIdx !== undefined) {
                setActiveBatch(batchIdx);
                // Mark all previous batches as completed
                const newCompleted = new Set<number>();
                for (let i = 0; i < batchIdx; i++) newCompleted.add(i);
                setCompletedBatches(newCompleted);
            }
            return; // Don't run auto-cycle when live
        }

        // Demo animation when idle
        const batchInterval = setInterval(() => {
            setActiveBatch((prev) => (prev + 1) % PIPELINE_BATCHES.length);
        }, 2000);

        const compInterval = setInterval(() => {
            setComparisonIndex((prev) => (prev + 1) % COMPARISON_POINTS.length);
        }, 3000);

        return () => {
            clearInterval(batchInterval);
            clearInterval(compInterval);
        };
    }, [isLive, streamEvents]);

    // Get the latest live agent description when streaming
    const liveDesc = isLive && streamEvents.length > 0
        ? streamEvents[streamEvents.length - 1].description
        : null;

    return (
        <div className="w-full max-w-4xl mx-auto">
            {/* Live indicator */}
            {isLive && (
                <div className="flex items-center justify-center gap-2 mb-3">
                    <div className="w-2 h-2 rounded-full bg-red-400 animate-pulse" />
                    <span className="text-xs text-red-300 font-medium uppercase tracking-wider">LIVE — Pipeline Executing</span>
                </div>
            )}

            {/* Pipeline Visualization */}
            <div className="bg-gradient-to-r from-slate-900/80 to-slate-800/80 rounded-2xl border border-white/10 p-6 mb-6">
                <h3 className="text-center text-gray-400 text-sm mb-6 uppercase tracking-wider">
                    {isLive ? "Real-Time Agent Execution" : "LangGraph Pipeline • FAISS + BM25 RAG • Structured Output"}
                </h3>

                {/* Batch Cards */}
                <div className="flex items-center justify-between gap-2">
                    {PIPELINE_BATCHES.map((batch, idx) => (
                        <div key={batch.id} className="flex items-center flex-1">
                            {/* Batch Card */}
                            <div
                                className={`flex-1 rounded-xl p-4 transition-all duration-500 ${
                                    completedBatches.has(idx)
                                        ? "bg-emerald-500/10 border-2 border-emerald-500/40"
                                        : activeBatch === idx
                                            ? "bg-gradient-to-br from-cyan-500/20 to-emerald-500/20 border-2 border-cyan-400/50 animate-pulse-glow scale-105"
                                            : "bg-white/5 border border-white/10"
                                }`}
                            >
                                <div className="text-center">
                                    <div className="text-3xl mb-2">
                                        {completedBatches.has(idx) ? "✅" : batch.icon}
                                    </div>
                                    <div className={`font-semibold text-sm ${
                                        completedBatches.has(idx) ? "text-emerald-300"
                                        : activeBatch === idx ? "text-cyan-300" : "text-white"
                                    }`}>
                                        {batch.title}
                                    </div>
                                    <div className="text-xs text-gray-500 mt-1">{batch.subtitle}</div>
                                    <div className={`text-xs mt-2 px-2 py-1 rounded-full inline-block ${
                                        completedBatches.has(idx) ? "bg-emerald-500/20 text-emerald-300"
                                        : activeBatch === idx ? "bg-cyan-500/20 text-cyan-300"
                                        : "bg-white/5 text-gray-500"
                                    }`}>
                                        {completedBatches.has(idx) ? "Done" : batch.duration}
                                    </div>
                                </div>
                            </div>

                            {/* Arrow */}
                            {idx < PIPELINE_BATCHES.length - 1 && (
                                <div className={`px-2 text-2xl ${
                                    completedBatches.has(idx) ? "text-emerald-400"
                                    : activeBatch === idx ? "text-cyan-400 animate-flow"
                                    : "text-gray-600"
                                }`}>→</div>
                            )}
                        </div>
                    ))}
                </div>

                {/* Active Batch Agents / Live Description */}
                <div className="mt-6 text-center">
                    {isLive && liveDesc ? (
                        <div>
                            <div className="text-xs text-cyan-400 mb-2 animate-pulse">⚡ {liveDesc}</div>
                            <div className="flex justify-center gap-2 flex-wrap">
                                {PIPELINE_BATCHES[activeBatch]?.agents.map((agent) => (
                                    <span key={agent} className="px-3 py-1 text-xs rounded-full bg-gradient-to-r from-cyan-500/20 to-emerald-500/20 text-cyan-300 border border-cyan-500/30 animate-pulse">
                                        {agent}
                                    </span>
                                ))}
                            </div>
                        </div>
                    ) : (
                        <div>
                            <div className="text-xs text-gray-500 mb-2">Agents in this stage:</div>
                            <div className="flex justify-center gap-2 flex-wrap">
                                {PIPELINE_BATCHES[activeBatch]?.agents.map((agent) => (
                                    <span key={agent} className="px-3 py-1 text-xs rounded-full bg-gradient-to-r from-cyan-500/20 to-emerald-500/20 text-cyan-300 border border-cyan-500/30">
                                        {agent}
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            </div>

            {/* Comparison Section */}
            <div className="bg-gradient-to-r from-red-950/30 via-slate-900/50 to-emerald-950/30 rounded-2xl border border-white/10 p-6">
                <h3 className="text-center text-gray-400 text-sm mb-4 uppercase tracking-wider">
                    Why This Beats Naive "Prompt → SQL"
                </h3>

                <div className="grid grid-cols-2 gap-4">
                    {/* Naive Approach */}
                    <div className="text-center">
                        <div className="text-red-400 font-semibold mb-3 flex items-center justify-center gap-2">
                            <span className="text-xl">❌</span> Naive Approach
                        </div>
                        <div
                            className="bg-red-500/10 border border-red-500/20 rounded-lg p-4 h-16 flex items-center justify-center transition-all duration-500"
                        >
                            <span className="text-red-300 text-sm">{COMPARISON_POINTS[comparisonIndex].naive}</span>
                        </div>
                    </div>

                    {/* Our Approach */}
                    <div className="text-center">
                        <div className="text-emerald-400 font-semibold mb-3 flex items-center justify-center gap-2">
                            <span className="text-xl">✅</span> ReasonSQL
                        </div>
                        <div
                            className="bg-emerald-500/10 border border-emerald-500/20 rounded-lg p-4 h-16 flex items-center justify-center transition-all duration-500"
                        >
                            <span className="text-emerald-300 text-sm">{COMPARISON_POINTS[comparisonIndex].smart}</span>
                        </div>
                    </div>
                </div>

                {/* Progress Dots */}
                <div className="flex justify-center gap-2 mt-4">
                    {COMPARISON_POINTS.map((_, idx) => (
                        <div
                            key={idx}
                            className={`w-2 h-2 rounded-full transition-all ${comparisonIndex === idx ? "bg-cyan-400 w-4" : "bg-gray-600"
                                }`}
                        />
                    ))}
                </div>
            </div>

            {/* Estimated Time */}
            <div className="text-center mt-4 text-gray-500 text-sm">
                <span className="inline-flex items-center gap-2">
                    <span className="inline-block w-3 h-3 rounded-full bg-gradient-to-r from-cyan-400 to-emerald-400 animate-pulse"></span>
                    Processing... Estimated time: 2-5 seconds
                </span>
            </div>
        </div>
    );
}
