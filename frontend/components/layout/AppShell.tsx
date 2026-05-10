"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bell, BriefcaseBusiness, Home, KanbanSquare, Menu, Settings, ShieldCheck, X } from "lucide-react";
import type { ReactNode } from "react";
import { useState } from "react";
import { cn } from "../../lib/utils";
import { useAgentStore } from "../../store/agentStore";
import { AgentStatusBadge } from "../shared/AgentStatusBadge";
import { ErrorBanner } from "../shared/ErrorBanner";
import { NeedsHumanAlert } from "../shared/NeedsHumanAlert";
import { StopButton } from "../shared/StopButton";

const nav = [
  { href: "/dashboard", label: "Dashboard", icon: Home },
  { href: "/jobs", label: "Jobs", icon: BriefcaseBusiness },
  { href: "/applications", label: "Applications", icon: KanbanSquare },
  { href: "/settings", label: "Settings", icon: Settings },
];

function titleForPath(pathname: string) {
  if (pathname.startsWith("/jobs")) return "Jobs";
  if (pathname.startsWith("/applications")) return "Applications";
  if (pathname.startsWith("/settings")) return "Settings";
  return "Dashboard";
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const needsHumanCount = useAgentStore((state) => state.needsHumanQueue.length);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-950">
      <aside className="fixed inset-y-0 left-0 hidden w-64 flex-col border-r border-slate-200 bg-white lg:flex">
        <div className="flex h-16 items-center gap-3 border-b border-slate-200 px-5">
          <div className="flex h-9 w-9 items-center justify-center rounded-md bg-slate-900 text-white">
            <ShieldCheck className="h-5 w-5" />
          </div>
          <span className="text-base font-semibold">AutoHire</span>
        </div>

        <nav className="flex-1 space-y-1 px-3 py-4">
          {nav.map((item) => {
            const active = pathname.startsWith(item.href);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium",
                  active ? "bg-slate-900 text-white" : "text-slate-700 hover:bg-slate-100",
                )}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="space-y-3 border-t border-slate-200 p-4">
          <AgentStatusBadge />
          <StopButton />
        </div>
      </aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-50 bg-slate-950/40 lg:hidden" onClick={() => setMobileOpen(false)}>
          <aside className="flex h-full w-64 flex-col border-r border-slate-200 bg-white" onClick={(event) => event.stopPropagation()}>
            <div className="flex h-16 items-center justify-between border-b border-slate-200 px-5">
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-md bg-slate-900 text-white">
                  <ShieldCheck className="h-5 w-5" />
                </div>
                <span className="text-base font-semibold">AutoHire</span>
              </div>
              <button className="rounded p-1 hover:bg-slate-100" onClick={() => setMobileOpen(false)}>
                <X className="h-5 w-5" />
              </button>
            </div>
            <nav className="flex-1 space-y-1 px-3 py-4">
              {nav.map((item) => {
                const active = pathname.startsWith(item.href);
                const Icon = item.icon;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={cn(
                      "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium",
                      active ? "bg-slate-900 text-white" : "text-slate-700 hover:bg-slate-100",
                    )}
                    onClick={() => setMobileOpen(false)}
                  >
                    <Icon className="h-4 w-4" />
                    {item.label}
                  </Link>
                );
              })}
            </nav>
            <div className="space-y-3 border-t border-slate-200 p-4">
              <AgentStatusBadge />
              <StopButton />
            </div>
          </aside>
        </div>
      )}

      <div className="lg:pl-64">
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-slate-200 bg-white px-6">
          <div className="flex items-center gap-3">
            <button className="rounded p-1 hover:bg-slate-100 lg:hidden" onClick={() => setMobileOpen(true)}>
              <Menu className="h-5 w-5" />
            </button>
            <div>
              <h1 className="text-lg font-semibold">{titleForPath(pathname)}</h1>
              <p className="text-xs text-slate-500">Operations control room</p>
            </div>
          </div>
          <div className="relative">
            <Bell className="h-5 w-5 text-slate-600" />
            {needsHumanCount > 0 && (
              <span className="absolute -right-2 -top-2 rounded-full bg-amber-500 px-1.5 text-[10px] font-semibold text-white">
                {needsHumanCount}
              </span>
            )}
          </div>
        </header>
        <main className="p-6">
          <ErrorBanner />
          <NeedsHumanAlert />
          {children}
        </main>
      </div>
    </div>
  );
}
