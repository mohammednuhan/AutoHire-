"use client";

import Link from "next/link";
import { useMutation, useQuery } from "@tanstack/react-query";
import { AlertTriangle, Briefcase, CheckCircle2, Clock, Play, TrendingUp } from "lucide-react";
import type { ElementType } from "react";
import { toast } from "sonner";
import { AppShell } from "../../components/layout/AppShell";
import { LiveFeed } from "../../components/shared/LiveFeed";
import { MetricsPanel } from "../../components/shared/MetricsPanel";
import { StopButton } from "../../components/shared/StopButton";
import { Button } from "../../components/ui/button";
import { Card, CardContent } from "../../components/ui/card";
import { api } from "../../lib/api";
import { useAgentStore } from "../../store/agentStore";

function SummaryCard({
  label,
  value,
  icon: Icon,
  tone,
}: {
  label: string;
  value: string | number;
  icon: ElementType;
  tone?: "green" | "orange";
}) {
  return (
    <Card>
      <CardContent className="flex items-center justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
          <p className="mt-2 text-2xl font-semibold text-slate-950">{value}</p>
        </div>
        <div
          className={
            tone === "green"
              ? "rounded-md bg-emerald-100 p-2 text-emerald-700"
              : tone === "orange"
                ? "rounded-md bg-amber-100 p-2 text-amber-700"
                : "rounded-md bg-slate-100 p-2 text-slate-600"
          }
        >
          <Icon className="h-5 w-5" />
        </div>
      </CardContent>
    </Card>
  );
}

function AgentStatusBar() {
  const { status, currentCompany, currentField, needsHumanQueue } = useAgentStore();
  const runAgent = useMutation({
    mutationFn: api.runAgent,
    onSuccess: () => toast.success("Agent run started"),
    onError: (error) => toast.error(error instanceof Error ? error.message : "Could not run agent"),
  });

  const copy = {
    idle: "Agent is idle. Last ran: --",
    running: `Running - ${currentCompany ?? "application"}: filling ${currentField ?? "field"}`,
    paused: `Paused - needs your input on ${needsHumanQueue.length} applications`,
    error: "Error: agent reported a failure",
  }[status];

  const dot = {
    idle: "bg-slate-400",
    running: "bg-emerald-500 animate-pulse",
    paused: "bg-amber-500",
    error: "bg-red-500",
  }[status];

  return (
    <div className="flex items-center justify-between rounded-lg border border-slate-200 bg-white px-4 py-3">
      <div className="flex items-center gap-3">
        <span className={`h-2.5 w-2.5 rounded-full ${dot}`} />
        <div>
          <p className="text-sm font-medium text-slate-900">{copy}</p>
          <p className="text-xs text-slate-500">All browser actions are logged and reviewable.</p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <Button variant="outline" onClick={() => runAgent.mutate()} disabled={runAgent.isPending}>
          <Play className="h-4 w-4" />
          Run Now
        </Button>
        <div className="w-28">
          <StopButton />
        </div>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const events = useAgentStore((state) => state.liveEvents);
  const needsHumanCount = useAgentStore((state) => state.needsHumanQueue.length);
  const clearEvents = useAgentStore((state) => state.clearEvents);
  const metrics = useQuery({ queryKey: ["metrics"], queryFn: api.getMetrics });
  const jobsToday = events.filter((event) => event.event === "JOB_DISCOVERED").length;
  const appliedThisWeek = metrics.data?.apps_sent_vs_confirmed.confirmed ?? 0;
  const responseRate =
    metrics.data && metrics.data.apps_sent_vs_confirmed.sent >= 5
      ? `${metrics.data.apps_sent_vs_confirmed.rate}%`
      : "--";

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
          <SummaryCard label="Jobs Scanned Today" value={jobsToday} icon={Briefcase} tone={jobsToday > 0 ? "green" : undefined} />
          <SummaryCard label="Applied This Week" value={appliedThisWeek} icon={CheckCircle2} />
          <SummaryCard label="Awaiting Review" value={needsHumanCount} icon={AlertTriangle} tone={needsHumanCount > 0 ? "orange" : undefined} />
          <SummaryCard label="Response Rate" value={responseRate} icon={TrendingUp} />
        </div>

        <AgentStatusBar />

        <LiveFeed events={events} onClear={clearEvents} />

        <MetricsPanel />

        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <Link href="/applications?status=ready_to_submit">
            <Button variant="outline" className="w-full">
              <Clock className="h-4 w-4" />
              Review Pending Applications
            </Button>
          </Link>
          <Link href="/jobs?score_min=85">
            <Button variant="outline" className="w-full">View High-Score Jobs</Button>
          </Link>
          <Button className="w-full" onClick={() => api.runAgent().catch(() => undefined)}>
            Run Agent Now
          </Button>
        </div>
      </div>
    </AppShell>
  );
}
