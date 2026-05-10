"use client";

import { useQuery } from "@tanstack/react-query";
import { Cell, Pie, PieChart, ResponsiveContainer } from "recharts";
import { api } from "../../lib/api";
import { Card, CardContent } from "../ui/card";

export function MetricsPanel() {
  const metrics = useQuery({
    queryKey: ["metrics"],
    queryFn: api.getMetrics,
    refetchInterval: 30 * 60 * 1000,
  });
  const data = metrics.data;
  const confirmationRate = data?.apps_sent_vs_confirmed.rate ?? 0;
  const confidence = Math.round((data?.llm_confidence_avg ?? 0) * 100);
  const gateRate = data?.human_gate_trigger_rate ?? 0;

  return (
    <div className="grid grid-cols-1 gap-3 xl:grid-cols-5">
      <MetricCard
        label="Applications Sent vs Confirmed"
        value={`${data?.apps_sent_vs_confirmed.confirmed ?? 0}/${data?.apps_sent_vs_confirmed.sent ?? 0} confirmed`}
        detail={`${confirmationRate}%`}
        tone={confirmationRate >= 90 ? "green" : confirmationRate >= 80 ? "yellow" : "red"}
      />
      <Card>
        <CardContent>
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Form Fill Success Rate</p>
          <div className="mt-3 h-24">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={boardChartData(data?.form_fill_success_rate ?? {})}
                  dataKey="value"
                  nameKey="name"
                  innerRadius={24}
                  outerRadius={42}
                  paddingAngle={2}
                >
                  {boardChartData(data?.form_fill_success_rate ?? {}).map((entry) => (
                    <Cell key={entry.name} fill={entry.fill} />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
          </div>
          <p className="text-xs text-slate-500">{boardSummary(data?.form_fill_success_rate ?? {})}</p>
        </CardContent>
      </Card>
      <Card>
        <CardContent>
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Avg LLM Confidence</p>
          <p className="mt-2 text-2xl font-semibold">{confidence}%</p>
          <div className="mt-3 h-2 rounded-full bg-slate-100">
            <div className="h-2 rounded-full bg-emerald-600" style={{ width: `${confidence}%` }} />
          </div>
        </CardContent>
      </Card>
      <MetricCard
        label="Avg Time Per Application"
        value={formatDuration(data?.avg_time_per_application_seconds ?? 0)}
        detail="browser fill time"
      />
      <MetricCard
        label="Human Gate Rate"
        value={`${gateRate}%`}
        detail="of applications paused for input"
        tone={gateRate > 30 ? "yellow" : "green"}
        title={gateRate > 30 ? "High pause rate may indicate prompt quality issues" : undefined}
      />
    </div>
  );
}

function MetricCard({
  label,
  value,
  detail,
  tone,
  title,
}: {
  label: string;
  value: string;
  detail: string;
  tone?: "green" | "yellow" | "red";
  title?: string;
}) {
  const color =
    tone === "green" ? "text-emerald-700" : tone === "yellow" ? "text-amber-700" : tone === "red" ? "text-red-700" : "text-slate-950";
  return (
    <Card>
      <CardContent title={title}>
        <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
        <p className={`mt-2 text-2xl font-semibold ${color}`}>{value}</p>
        <p className="mt-1 text-xs text-slate-500">{detail}</p>
      </CardContent>
    </Card>
  );
}

function boardChartData(values: Record<string, number>) {
  const fills = ["#059669", "#2563eb", "#d97706", "#7c3aed"];
  return Object.entries(values).map(([name, value], index) => ({
    name,
    value,
    fill: fills[index % fills.length],
  }));
}

function boardSummary(values: Record<string, number>) {
  const entries = Object.entries(values);
  if (!entries.length) return "No form fills yet.";
  return entries.map(([board, value]) => `${board}: ${value}%`).join(", ");
}

function formatDuration(seconds: number) {
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return `${minutes} min ${remainder} sec`;
}
