import type { Metadata } from "next";
import { Suspense } from "react";
import { Sidebar } from "@/components/Sidebar";
import { ConnectBar } from "@/components/BridgeStatus";
import "./globals.css";

export const metadata: Metadata = {
  title: "ResearchLedger",
  description: "Evidence-first AI research workspace",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Serif:wght@500;600&display=swap" />
      </head>
      <body className="font-sans antialiased">
        <div className="flex min-h-screen flex-col lg:flex-row">
          <Suspense><Sidebar /></Suspense>
          <div className="min-w-0 flex-1"><ConnectBar />{children}</div>
        </div>
      </body>
    </html>
  );
}
