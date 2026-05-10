"use client";

import type { ReactNode } from "react";
import { useEffect } from "react";

export function SentryProvider({ children }: { children: ReactNode }) {
  useEffect(() => {
    if (process.env.NEXT_PUBLIC_ENVIRONMENT !== "production" || !process.env.NEXT_PUBLIC_SENTRY_DSN) {
      return;
    }
    import("@sentry/nextjs").then((Sentry) => {
      Sentry.init({ dsn: process.env.NEXT_PUBLIC_SENTRY_DSN, tracesSampleRate: 0.1 });
    });
  }, []);

  return <>{children}</>;
}
