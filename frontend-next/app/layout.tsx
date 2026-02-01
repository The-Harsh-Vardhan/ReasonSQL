import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Analytics } from "@vercel/analytics/next";
import GlobalErrorBoundary from "./components/GlobalErrorBoundary";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "ReasonSQL - Multi-Agent NL→SQL System",
  description: "Convert natural language to SQL with 12 specialized AI agents. Features schema exploration, safety validation, and self-correction.",
  keywords: ["NL2SQL", "natural language to SQL", "AI agents", "database", "Gemini", "LLM"],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <GlobalErrorBoundary>
          {children}
        </GlobalErrorBoundary>
        <Analytics />
      </body>
    </html>
  );
}

