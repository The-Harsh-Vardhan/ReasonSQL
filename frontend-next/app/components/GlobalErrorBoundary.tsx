"use client";

import { Component, ReactNode } from "react";

interface ErrorBoundaryProps {
    children: ReactNode;
    fallback?: ReactNode;
}

interface ErrorBoundaryState {
    hasError: boolean;
    error?: Error;
    errorInfo?: string;
}

export default class GlobalErrorBoundary extends Component<
    ErrorBoundaryProps,
    ErrorBoundaryState
> {
    constructor(props: ErrorBoundaryProps) {
        super(props);
        this.state = { hasError: false };
    }

    static getDerivedStateFromError(error: Error): ErrorBoundaryState {
        return { hasError: true, error };
    }

    componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
        console.error("GlobalErrorBoundary caught an error:", error, errorInfo);
        this.setState({ errorInfo: errorInfo.componentStack || "" });
    }

    render() {
        if (this.state.hasError) {
            return (
                this.props.fallback || (
                    <div style={{
                        minHeight: "100vh",
                        backgroundColor: "#0f172a",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        padding: "2rem"
                    }}>
                        <div style={{
                            maxWidth: "28rem",
                            width: "100%",
                            backgroundColor: "#1e293b",
                            borderRadius: "0.75rem",
                            padding: "2rem",
                            border: "1px solid #ef4444"
                        }}>
                            <h2 style={{
                                fontSize: "1.5rem",
                                fontWeight: "bold",
                                color: "#f87171",
                                marginBottom: "1rem"
                            }}>
                                Something went wrong!
                            </h2>
                            <p style={{ color: "#94a3b8", marginBottom: "1rem" }}>
                                An error occurred while rendering the application.
                            </p>
                            <div style={{
                                backgroundColor: "#000",
                                borderRadius: "0.5rem",
                                padding: "1rem",
                                marginBottom: "1.5rem",
                                overflowX: "auto"
                            }}>
                                <code style={{
                                    color: "#fca5a5",
                                    fontSize: "0.875rem",
                                    fontFamily: "monospace",
                                    wordBreak: "break-word"
                                }}>
                                    {this.state.error?.message || "Unknown error"}
                                </code>
                            </div>
                            {this.state.errorInfo && (
                                <details style={{ marginBottom: "1rem" }}>
                                    <summary style={{ color: "#94a3b8", cursor: "pointer" }}>
                                        Stack trace
                                    </summary>
                                    <pre style={{
                                        fontSize: "0.75rem",
                                        color: "#64748b",
                                        marginTop: "0.5rem",
                                        overflowX: "auto",
                                        whiteSpace: "pre-wrap"
                                    }}>
                                        {this.state.errorInfo}
                                    </pre>
                                </details>
                            )}
                            <button
                                onClick={() => this.setState({ hasError: false, error: undefined })}
                                style={{
                                    width: "100%",
                                    padding: "0.75rem",
                                    background: "linear-gradient(to right, #06b6d4, #10b981)",
                                    color: "white",
                                    fontWeight: "600",
                                    borderRadius: "0.5rem",
                                    border: "none",
                                    cursor: "pointer"
                                }}
                            >
                                Try Again
                            </button>
                        </div>
                    </div>
                )
            );
        }

        return this.props.children;
    }
}
