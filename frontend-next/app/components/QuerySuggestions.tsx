"use client";

interface QuerySuggestionsProps {
    onSelect: (query: string) => void;
}

const SUGGESTIONS = [
    { label: "Count customers", query: "How many customers are there?" },
    { label: "Top artists", query: "Which 5 artists have the most tracks?" },
    { label: "Revenue by country", query: "Total sales revenue by country, top 10" },
    { label: "Longest tracks", query: "Show the top 10 longest tracks" },
    { label: "Tables in DB", query: "What tables exist in this database?" },
    { label: "Genres", query: "How many genres are there?" },
    { label: "Recent invoices", query: "Show the 5 most recent invoices" },
    { label: "Employee hierarchy", query: "List all employees and their managers" },
];

export default function QuerySuggestions({ onSelect }: QuerySuggestionsProps) {
    return (
        <div className="flex gap-2 flex-wrap">
            {SUGGESTIONS.map((s, i) => (
                <button
                    key={i}
                    onClick={() => onSelect(s.query)}
                    title={s.query}
                    className="px-3 py-1.5 text-xs rounded-full bg-white/5 text-gray-400 border border-white/10 hover:bg-cyan-500/10 hover:text-cyan-300 hover:border-cyan-500/30 transition-all duration-200"
                >
                    {s.label}
                </button>
            ))}
        </div>
    );
}
