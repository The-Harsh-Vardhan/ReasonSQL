"use client";

import { useMemo } from "react";
import {
    BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
    XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from "recharts";

interface ResultsChartProps {
    data: Record<string, unknown>[];
}

const COLORS = ["#06b6d4", "#10b981", "#8b5cf6", "#f59e0b", "#ef4444", "#3b82f6"];

export default function ResultsChart({ data }: ResultsChartProps) {
    const { chartType, categoryKey, numericalKeys } = useMemo(() => {
        if (!data || data.length === 0) return { chartType: null };

        const keys = Object.keys(data[0]);
        let categoryKey: string | null = null;
        let timeKey: string | null = null;
        const numericalKeys: string[] = [];

        // Analyze columns
        keys.forEach(key => {
            const val = data[0][key];
            const isNum = typeof val === "number" || (!isNaN(Number(val)) && typeof val !== "boolean");
            const isDate = !isNum && (key.toLowerCase().includes("date") || key.toLowerCase().includes("time") || key.toLowerCase().includes("month") || key.toLowerCase().includes("year"));

            if (isNum) {
                numericalKeys.push(key);
            } else if (isDate && !timeKey) {
                timeKey = key;
            } else if (!categoryKey) {
                categoryKey = key;
            }
        });

        // Heuristics for chart type
        if (numericalKeys.length === 0) return { chartType: null };

        // 1. Time Series -> Line Chart
        if (timeKey && numericalKeys.length > 0) {
            return { chartType: "line", categoryKey: timeKey, numericalKeys };
        }

        // 2. Few categories -> Pie Chart (if 1 numeric)
        if (categoryKey && numericalKeys.length === 1 && data.length <= 5) {
            return { chartType: "pie", categoryKey, numericalKeys };
        }

        // 3. Comparison -> Bar Chart
        if (categoryKey && numericalKeys.length > 0) {
            return { chartType: "bar", categoryKey, numericalKeys };
        }

        // Fallback: Use index as category if needed, or if just 1 row with numeric
        if (numericalKeys.length > 0 && data.length > 1) {
            return { chartType: "bar", categoryKey: categoryKey || "index", numericalKeys };
        }

        return { chartType: null };
    }, [data]);

    if (!chartType || !data || data.length === 0) return null;

    // Format data for Recharts (ensure numbers are numbers)
    const chartData = data.map((item, i) => {
        const newItem: any = { ...item, index: i + 1 };
        numericalKeys?.forEach(key => {
            newItem[key] = Number(item[key]);
        });
        return newItem;
    });

    const axisStyle = { fontSize: 12, fill: "#9ca3af" };
    const tooltipStyle = { backgroundColor: "#1e293b", borderColor: "#334155", color: "#f1f5f9", borderRadius: "8px" };

    return (
        <div className="w-full h-[300px] mt-4 animate-fade-in">
            <div className="text-xs text-gray-500 mb-2 uppercase tracking-wider font-semibold">
                Visualization ({chartType})
            </div>
            <ResponsiveContainer width="100%" height="100%">
                {chartType === "line" ? (
                    <LineChart data={chartData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
                        <XAxis dataKey={categoryKey!} stroke="#475569" tick={axisStyle} />
                        <YAxis stroke="#475569" tick={axisStyle} />
                        <Tooltip contentStyle={tooltipStyle} itemStyle={{ color: "#fff" }} />
                        <Legend />
                        {numericalKeys!.map((key, i) => (
                            <Line key={key} type="monotone" dataKey={key} stroke={COLORS[i % COLORS.length]} strokeWidth={3} dot={{ r: 4, strokeWidth: 2 }} activeDot={{ r: 6 }} />
                        ))}
                    </LineChart>
                ) : chartType === "pie" ? (
                    <PieChart>
                        <Pie
                            data={chartData}
                            cx="50%"
                            cy="50%"
                            innerRadius={60}
                            outerRadius={80}
                            paddingAngle={5}
                            dataKey={numericalKeys![0]}
                            nameKey={categoryKey!}
                        >
                            {chartData.map((_, index) => (
                                <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} stroke="rgba(0,0,0,0.2)" />
                            ))}
                        </Pie>
                        <Tooltip contentStyle={tooltipStyle} itemStyle={{ color: "#fff" }} />
                        <Legend />
                    </PieChart>
                ) : (
                    <BarChart data={chartData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
                        <XAxis dataKey={categoryKey!} stroke="#475569" tick={axisStyle} />
                        <YAxis stroke="#475569" tick={axisStyle} />
                        <Tooltip cursor={{ fill: "rgba(255,255,255,0.05)" }} contentStyle={tooltipStyle} itemStyle={{ color: "#fff" }} />
                        <Legend />
                        {numericalKeys!.map((key, i) => (
                            // Add radius to top corners of bars
                            <Bar key={key} dataKey={key} fill={COLORS[i % COLORS.length]} radius={[4, 4, 0, 0]} maxBarSize={60} />
                        ))}
                    </BarChart>
                )}
            </ResponsiveContainer>
        </div>
    );
}
