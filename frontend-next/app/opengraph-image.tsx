import { ImageResponse } from "next/og";

export const runtime = "edge";

export const alt = "ReasonSQL - Multi-Agent NL→SQL System";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default async function Image() {
    return new ImageResponse(
        (
            <div
                style={{
                    width: "100%",
                    height: "100%",
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    justifyContent: "center",
                    background: "linear-gradient(135deg, #0c1222 0%, #0f172a 40%, #042f2e 100%)",
                    fontFamily: "system-ui, sans-serif",
                    position: "relative",
                    overflow: "hidden",
                }}
            >
                {/* Background decorations */}
                <div
                    style={{
                        position: "absolute",
                        top: -100,
                        right: -100,
                        width: 400,
                        height: 400,
                        borderRadius: "50%",
                        background: "radial-gradient(circle, rgba(6,182,212,0.15) 0%, transparent 70%)",
                    }}
                />
                <div
                    style={{
                        position: "absolute",
                        bottom: -100,
                        left: -100,
                        width: 400,
                        height: 400,
                        borderRadius: "50%",
                        background: "radial-gradient(circle, rgba(16,185,129,0.15) 0%, transparent 70%)",
                    }}
                />

                {/* Logo */}
                <div
                    style={{
                        fontSize: 80,
                        fontWeight: 800,
                        background: "linear-gradient(90deg, #06b6d4, #14b8a6, #10b981)",
                        backgroundClip: "text",
                        color: "transparent",
                        letterSpacing: "-2px",
                        marginBottom: 16,
                        display: "flex",
                    }}
                >
                    ReasonSQL
                </div>

                {/* Subtitle */}
                <div
                    style={{
                        fontSize: 28,
                        color: "#94a3b8",
                        fontWeight: 300,
                        marginBottom: 40,
                        display: "flex",
                        gap: 8,
                    }}
                >
                    Natural Language → SQL with{" "}
                    <span style={{ color: "#06b6d4", fontWeight: 600 }}>12 AI Agents</span>
                </div>

                {/* Feature pills */}
                <div style={{ display: "flex", gap: 16 }}>
                    {["Quota-Optimized", "Safety-Validated", "Self-Correcting"].map(
                        (label) => (
                            <div
                                key={label}
                                style={{
                                    padding: "10px 24px",
                                    borderRadius: 100,
                                    border: "1px solid rgba(6,182,212,0.3)",
                                    background: "rgba(6,182,212,0.1)",
                                    color: "#67e8f9",
                                    fontSize: 18,
                                    display: "flex",
                                }}
                            >
                                {label}
                            </div>
                        )
                    )}
                </div>

                {/* Bottom bar */}
                <div
                    style={{
                        position: "absolute",
                        bottom: 32,
                        display: "flex",
                        gap: 24,
                        color: "#475569",
                        fontSize: 16,
                    }}
                >
                    <span>FastAPI Backend</span>
                    <span>•</span>
                    <span>Next.js Frontend</span>
                    <span>•</span>
                    <span>Gemini LLM</span>
                </div>
            </div>
        ),
        { ...size }
    );
}
