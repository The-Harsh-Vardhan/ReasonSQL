"use client";

import { useState } from "react";

interface AgentAction {
    agent_name: string;
    summary: string;
    detail?: string;
}

interface ReasoningCardProps {
    action: AgentAction;
    index: number;
    totalSteps: number;
    simpleMode: boolean;
}

// Parse agent action into readable question-answer format
function parseToReadableStep(action: AgentAction, index: number): { question: string; explanation: string; isLLM: boolean; skip: boolean } {
    const agentName = action.agent_name.toLowerCase();
    const summary = action.summary || "";

    // Skip empty or useless steps
    if (!summary || summary === "[]" || summary === "Assumptions: []" || summary === "Tables: []") {
        return { question: "", explanation: "", isLLM: false, skip: true };
    }

    // Clean up summary - remove "Stripped X chars:" prefix
    const cleanSummary = summary.replace(/^Stripped \d+ chars:\s*/i, "").trim();

    // Skip if summary is just code or too technical
    if (cleanSummary.startsWith("```") || cleanSummary.startsWith("import ") || cleanSummary.startsWith("def ")) {
        return { question: "", explanation: "", isLLM: false, skip: true };
    }

    // Intent Analysis
    if (agentName.includes("intent") || (agentName.includes("batch1") && !agentName.includes("batch2"))) {
        const explanation = cleanSummary.includes("DATA")
            ? "This is a data query - the user wants to retrieve information from the database."
            : cleanSummary.includes("META")
                ? "This is a meta query - asking about the database structure itself."
                : cleanSummary.length > 10 ? cleanSummary : "Analyzing the query to determine if it's asking for data or schema information.";
        return {
            question: "What type of query is this?",
            explanation,
            isLLM: true,
            skip: false
        };
    }

    // Clarification - only show if there are actual assumptions
    if (agentName.includes("clarif")) {
        if (cleanSummary === "Assumptions: []" || cleanSummary.length < 5) {
            return { question: "", explanation: "", isLLM: false, skip: true };
        }
        return {
            question: "Are there any assumptions needed?",
            explanation: cleanSummary,
            isLLM: true,
            skip: false
        };
    }

    // Schema Exploration
    if (agentName.includes("schema") && !agentName.includes("generator")) {
        return {
            question: "What tables and columns are available?",
            explanation: cleanSummary.length > 200
                ? cleanSummary.slice(0, 200) + "..."
                : cleanSummary || "Exploring the database schema to find relevant tables.",
            isLLM: false,
            skip: false
        };
    }

    // Query Decomposition / Planning
    if (agentName.includes("decompos") || agentName.includes("planner") || agentName.includes("planning")) {
        if (cleanSummary === "[]" || cleanSummary.length < 5) {
            return { question: "", explanation: "", isLLM: false, skip: true };
        }
        return {
            question: "How should we break down this query?",
            explanation: cleanSummary || "Breaking down the query into logical steps.",
            isLLM: true,
            skip: false
        };
    }

    // SQL Generation
    if (agentName.includes("sqlgen") || agentName.includes("generator") ||
        (agentName.includes("batch2") && agentName.includes("sql")) ||
        agentName.includes("batch3") || agentName.includes("generation")) {
        // Check if it contains actual SQL
        const hasSql = cleanSummary.toUpperCase().includes("SELECT") ||
            cleanSummary.toUpperCase().includes("FROM");
        return {
            question: "What SQL query should we generate?",
            explanation: hasSql ? cleanSummary : (cleanSummary || "Generating the SQL query based on schema and requirements."),
            isLLM: true,
            skip: false
        };
    }

    // Safety Validation
    if (agentName.includes("safety") || agentName.includes("valid")) {
        const isBlocked = cleanSummary.toLowerCase().includes("block") || cleanSummary.toLowerCase().includes("denied");
        return {
            question: "Is this query safe to execute?",
            explanation: isBlocked
                ? `BLOCKED: ${cleanSummary}`
                : "APPROVED: The query is safe - it's a read-only SELECT with proper limits.",
            isLLM: false,
            skip: false
        };
    }

    // SQL Execution
    if (agentName.includes("execut")) {
        // Check if it's just showing the SQL again
        if (cleanSummary.toUpperCase().startsWith("SELECT")) {
            return {
                question: "Executing the query...",
                explanation: `Running: ${cleanSummary}`,
                isLLM: false,
                skip: false
            };
        }
        return {
            question: "What results did we get?",
            explanation: cleanSummary || "Executing the validated SQL query.",
            isLLM: false,
            skip: false
        };
    }

    // Self Correction
    if (agentName.includes("correct") || agentName.includes("retry")) {
        return {
            question: "Did we need to retry?",
            explanation: cleanSummary || "Checking if any corrections were needed.",
            isLLM: true,
            skip: false
        };
    }

    // Response Synthesis
    if (agentName.includes("synth") || agentName.includes("response") || agentName.includes("batch4")) {
        return {
            question: "Final answer",
            explanation: cleanSummary || "Preparing the final response.",
            isLLM: true,
            skip: false
        };
    }

    // Data Explorer
    if (agentName.includes("dataexplorer") || agentName.includes("sample")) {
        return {
            question: "What does the data look like?",
            explanation: cleanSummary || "Sampling data to understand the format.",
            isLLM: false,
            skip: false
        };
    }

    // Default - show if there's meaningful content
    if (cleanSummary.length < 5) {
        return { question: "", explanation: "", isLLM: false, skip: true };
    }

    return {
        question: action.agent_name.replace(/([A-Z])/g, ' $1').replace(/_/g, ' ').trim(),
        explanation: cleanSummary,
        isLLM: agentName.includes("batch") || agentName.includes("llm"),
        skip: false
    };
}

const TRUNCATE_LENGTH = 200;

export default function ReasoningCard({ action, index, totalSteps, simpleMode }: ReasoningCardProps) {
    const [expanded, setExpanded] = useState(false);
    const [showFullExplanation, setShowFullExplanation] = useState(false);
    const parsed = parseToReadableStep(action, index);

    // Skip empty/useless steps
    if (parsed.skip) {
        return null;
    }

    // Check if explanation needs truncation
    const needsTruncation = parsed.explanation.length > TRUNCATE_LENGTH;
    const displayExplanation = needsTruncation && !showFullExplanation
        ? parsed.explanation.slice(0, TRUNCATE_LENGTH) + "..."
        : parsed.explanation;

    // Gradient colors based on position
    const gradientColors = [
        "from-cyan-500 to-cyan-400",
        "from-cyan-400 to-teal-400",
        "from-teal-400 to-teal-500",
        "from-teal-500 to-emerald-400",
        "from-emerald-400 to-emerald-500"
    ];

    const colorIndex = Math.min(Math.floor(index / totalSteps * 5), 4);
    const gradientClass = gradientColors[colorIndex];

    return (
        <div className="relative pl-8">
            {/* Vertical Connection Line */}
            {index < totalSteps - 1 && (
                <div className="absolute left-[18px] top-12 bottom-0 w-0.5 bg-gradient-to-b from-white/20 to-white/5" />
            )}

            {/* Step Card */}
            <div className="relative mb-5">
                {/* Number Badge */}
                <div className={`absolute -left-8 top-0 w-8 h-8 rounded-full bg-gradient-to-br ${gradientClass} flex items-center justify-center text-white font-semibold text-sm shadow-lg`}>
                    {index + 1}
                </div>

                {/* Content */}
                <div className="bg-white/[0.03] hover:bg-white/[0.05] rounded-xl p-4 border border-white/10 transition-all">
                    {/* Question */}
                    <div className="flex items-center gap-2 mb-2">
                        <h4 className="text-white font-medium">{parsed.question}</h4>
                        {parsed.isLLM && (
                            <span className="text-xs px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-300">
                                AI
                            </span>
                        )}
                    </div>

                    {/* Explanation */}
                    <div className="text-gray-400 text-sm leading-relaxed">
                        {displayExplanation}
                    </div>

                    {/* Show more/less */}
                    {needsTruncation && (
                        <button
                            onClick={() => setShowFullExplanation(!showFullExplanation)}
                            className="text-xs text-cyan-400 mt-2 hover:text-cyan-300 transition-colors"
                        >
                            {showFullExplanation ? "Show less" : "Show more"}
                        </button>
                    )}

                    {/* Raw Details */}
                    {action.detail && !simpleMode && (
                        <>
                            <button
                                onClick={() => setExpanded(!expanded)}
                                className="text-xs text-gray-500 mt-2 block hover:text-gray-400 transition-colors"
                            >
                                {expanded ? "Hide raw output" : "Show raw output"}
                            </button>

                            {expanded && (
                                <div className="mt-2 p-2 rounded-lg bg-black/40 border border-white/5">
                                    <pre className="text-xs text-gray-500 font-mono whitespace-pre-wrap break-all overflow-x-auto max-h-40 overflow-y-auto">
                                        {action.detail}
                                    </pre>
                                </div>
                            )}
                        </>
                    )}
                </div>
            </div>
        </div>
    );
}
