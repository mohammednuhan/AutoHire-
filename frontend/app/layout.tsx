import type { Metadata } from "next";
import type { ReactNode } from "react";
import { QueryProvider } from "./query-provider";
import { SentryProvider } from "./sentry-provider";
import { WebSocketProvider } from "./websocket-provider";
import "./globals.css";

export const metadata: Metadata = {
  title: "AutoHire",
  description: "Self-hosted job application agent",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <SentryProvider>
          <QueryProvider>
            <WebSocketProvider>{children}</WebSocketProvider>
          </QueryProvider>
        </SentryProvider>
      </body>
    </html>
  );
}
