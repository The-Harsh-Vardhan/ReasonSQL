"use client";

import { useEffect, useState } from "react";

interface PipelineBatch {
    id: number;
    icon: string;
    title: string;
    subtitle: string;
    duration: string;
    agents: string[];
}

const PIPELINE_BATCHES: PipelineBatch[] = [
    {
        id: 1,
        icon: "🧠",
        title: "Intent Analysis",
        subtitle: "Understanding your question",
        duration: "~500ms",
        agents: ["IntentAnalyzer", "ClarificationAgent"],
    },
    {
        id: 2,
        icon: "📊",
        title: "Schema & Planning",
        subtitle: "Exploring database structure",
        duration: "~800ms",
        agents: ["SchemaExplorer", "QueryDecomposer", "DataExplorer", "QueryPlanner"],
    },
    {
        id: 3,
        icon: "💾",
        title: "SQL Generation",
        subtitle: "Creating & validating query",
        duration: "~800ms",
        agents: ["SQLGenerator", "SafetyValidator", "SQLExecutor", "SelfCorrection"],
    },
    {
        id: 4,
        icon: "✨",
        title: "Answer Synthesis",
        subtitle: "Formatting results",
        duration: "~500ms",
        agents: ["ResponseSynthesizer"],
    },
];

const COMPARISON_POINTS = [
    { naive: "Hallucinates table names", smart: "Explores schema BEFORE generating" },
    { naive: "Assumes meaning of 'recent', 'best'", smart: "Asks clarifying questions" },
    { naive: "Returns errors, not answers", smart: "Self-corrects on failures (3x retry)" },
    { naive: "No safety (SELECT * on 1M rows)", smart: "Safety-validated, enforces LIMIT" },
];

export default function ProcessingDiagram() {
    const [activeBatch, setActiveBatch] = useState(0);
    const [comparisonIndex, setComparisonIndex] = useState(0);

    useEffect(() => {
        // Cycle through batches
        const batchInterval = setInterval(() => {
            setActiveBatch((prev) => (prev + 1) % PIPELINE_BATCHES.length);
        }, 2000);

        // Cycle through comparison points
        const compInterval = setInterval(() => {
            setComparisonIndex((prev) => (prev + 1) % COMPARISON_POINTS.length);
        }, 3000);

        return () => {
            clearInterval(batchInterval);
            clearInterval(compInterval);
        };
    }, []);

    return (
        <div className="w-full max-w-4xl mx-auto">
            {/* Pipeline Visualization */}
            <div className="bg-gradient-to-r from-slate-900/80 to-slate-800/80 rounded-2xl border border-white/10 p-6 mb-6">
                <h3 className="text-center text-gray-400 text-sm mb-6 uppercase tracking-wider">
                    12 Specialized Agents • 4 Batches • Full Transparency
                </h3>

                {/* Batch Cards */}
                <div className="flex items-center justify-between gap-2">
                    {PIPELINE_BATCHES.map((batch, idx) => (
                        <div key={batch.id} className="flex items-center flex-1">
                            {/* Batch Card */}
                            <div
                                className={`flex-1 rounded-xl p-4 transition-all duration-500 ${activeBatch === idx
                                        ? "bg-gradient-to-br from-cyan-500/20 to-emerald-500/20 border-2 border-cyan-400/50 animate-pulse-glow scale-105"
                                        : "bg-white/5 border border-white/10"
                                    }`}
                            >
                                <div className="text-center">
                                    <div className="text-3xl mb-2">{batch.icon}</div>
                                    <div className={`font-semibold text-sm ${activeBatch === idx ? "text-cyan-300" : "text-white"}`}>
                                        {batch.title}
                                    </div>
                                    <div className="text-xs text-gray-500 mt-1">{batch.subtitle}</div>
                                    <div className={`text-xs mt-2 px-2 py-1 rounded-full inline-block ${activeBatch === idx
                                            ? "bg-cyan-500/20 text-cyan-300"
                                            : "bg-white/5 text-gray-500"
                                        }`}>
                                        {batch.duration}
                                    </div>
                                </div>
                            </div>

                            {/* Arrow (except last) */}
                            {idx < PIPELINE_BATCHES.length - 1 && (
                                <div className={`px-2 text-2xl ${activeBatch === idx ? "text-cyan-400 animate-flow" : "text-gray-600"}`}>
                                    →
                                </div>
                            )}
                        </div>
                    ))}
                </div>

                {/* Active Batch Agents */}
                <div className="mt-6 text-center">
                    <div className="text-xs text-gray-500 mb-2">Currently Active Agents:</div>
                    <div className="flex justify-center gap-2 flex-wrap">
                        {PIPELINE_BATCHES[activeBatch].agents.map((agent) => (
                            <span
                                key={agent}
                                className="px-3 py-1 text-xs rounded-full bg-gradient-to-r from-cyan-500/20 to-emerald-500/20 text-cyan-300 border border-cyan-500/30"
                            >
                                {agent}
                            </span>
                        ))}
                    </div>
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
