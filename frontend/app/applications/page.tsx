"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, List, Rows3, X } from "lucide-react";
import { toast } from "sonner";
import { AppShell } from "../../components/layout/AppShell";
import { ApplicationStatusBadge } from "../../components/shared/ApplicationStatusBadge";
import { ConfidenceBadge } from "../../components/shared/ConfidenceBadge";
import { FeedbackButton } from "../../components/shared/FeedbackButton";
import { ScoreBadge } from "../../components/shared/ScoreBadge";
import { Button } from "../../components/ui/button";
import { Card, CardContent } from "../../components/ui/card";
import { api } from "../../lib/api";
import { formatDate, formatRelativeTime } from "../../lib/utils";
import { ApplicationStatus, type ApplicationDetailResponse, type ApplicationListItem } from "../../types/api";

const columns = [
  { id: ApplicationStatus.Queued, label: "Queued" },
  { id: ApplicationStatus.AgentProcessing, label: "Processing" },
  { id: ApplicationStatus.NeedsHuman, label: "Needs Review" },
  { id: ApplicationStatus.ReadyToSubmit, label: "Ready to Submit" },
  { id: ApplicationStatus.Submitted, label: "Submitted" },
  { id: ApplicationStatus.Shortlisted, label: "Shortlisted" },
  { id: ApplicationStatus.Interview, label: "Interview" },
  { id: ApplicationStatus.Offer, label: "Offer" },
  { id: ApplicationStatus.Rejected, label: "Rejected" },
  { id: ApplicationStatus.Ghosted, label: "Ghosted" },
];

export default function ApplicationsPage() {
  const [mode, setMode] = useState<"kanban" | "table">("kanban");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const applications = useQuery({
    queryKey: ["applications"],
    queryFn: () => api.listApplications().catch(() => []),
  });

  const moveStatus = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) => api.updateApplicationStatus(id, status),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["applications"] }),
    onError: (error) => toast.error(error instanceof Error ? error.message : "Could not update status"),
  });

  const grouped = useMemo(() => {
    const map = new Map<string, ApplicationListItem[]>();
    columns.forEach((column) => map.set(column.id, []));
    (applications.data ?? []).forEach((item) => {
      const list = map.get(item.status) ?? [];
      list.push(item);
      map.set(item.status, list);
    });
    return map;
  }, [applications.data]);

  return (
    <AppShell>
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="inline-flex rounded-md border border-slate-200 bg-white p-1">
            <button className={`flex items-center gap-2 rounded px-3 py-1.5 text-sm ${mode === "kanban" ? "bg-slate-900 text-white" : "text-slate-600"}`} onClick={() => setMode("kanban")}>
              <Rows3 className="h-4 w-4" /> Kanban
            </button>
            <button className={`flex items-center gap-2 rounded px-3 py-1.5 text-sm ${mode === "table" ? "bg-slate-900 text-white" : "text-slate-600"}`} onClick={() => setMode("table")}>
              <List className="h-4 w-4" /> Table
            </button>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm">Submit all ready</Button>
            <Button variant="ghost" size="sm">Skip all queued</Button>
          </div>
        </div>

        {mode === "kanban" ? (
          <div className="flex gap-4 overflow-x-auto pb-3">
            {columns.map((column) => (
              <section
                key={column.id}
                className="min-h-[560px] w-72 shrink-0 rounded-lg border border-slate-200 bg-slate-100/70"
                onDragOver={(event) => event.preventDefault()}
                onDrop={(event) => {
                  const id = event.dataTransfer.getData("application/id");
                  if (id) moveStatus.mutate({ id, status: column.id });
                }}
              >
                <div className="flex items-center justify-between border-b border-slate-200 px-3 py-2">
                  <h2 className="text-sm font-semibold">{column.label}</h2>
                  <span className="rounded-full bg-white px-2 py-0.5 text-xs">{grouped.get(column.id)?.length ?? 0}</span>
                </div>
                <div className="space-y-3 p-3">
                  {(grouped.get(column.id) ?? []).map((app) => (
                    <ApplicationCard key={app.id} app={app} onOpen={() => setSelectedId(app.id)} />
                  ))}
                </div>
              </section>
            ))}
          </div>
        ) : (
          <ApplicationTable applications={applications.data ?? []} onOpen={setSelectedId} />
        )}

        {selectedId && <ApplicationDetailPanel applicationId={selectedId} onClose={() => setSelectedId(null)} />}
      </div>
    </AppShell>
  );
}

function ApplicationCard({ app, onOpen }: { app: ApplicationListItem; onOpen: () => void }) {
  const urgent = app.status === ApplicationStatus.NeedsHuman || app.status === ApplicationStatus.ReadyToSubmit;
  return (
    <Card
      draggable
      onDragStart={(event) => event.dataTransfer.setData("application/id", app.id)}
      className={urgent ? "cursor-pointer border-amber-300 ring-2 ring-amber-100" : "cursor-pointer"}
      onClick={onOpen}
    >
      <CardContent className="space-y-3">
        <div>
          <h3 className="font-semibold">{app.company ?? "Unknown company"}</h3>
          <p className="text-sm text-slate-600">{app.title ?? "Role unavailable"}</p>
        </div>
        <div className="flex items-center justify-between">
          <ScoreBadge score={(app as any).total_score} />
          <ApplicationStatusBadge status={app.status} />
        </div>
        <div onClick={(event) => event.stopPropagation()}>
          <FeedbackButton applicationId={app.id} traceId={app.trace_id} />
        </div>
        <p className="text-xs text-slate-500">In stage {formatRelativeTime(app.started_at ?? app.queued_at)}</p>
      </CardContent>
    </Card>
  );
}

function ApplicationTable({
  applications,
  onOpen,
}: {
  applications: ApplicationListItem[];
  onOpen: (id: string) => void;
}) {
  return (
    <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
      <table className="w-full text-left text-sm">
        <thead className="bg-slate-50 text-xs uppercase text-slate-500">
          <tr>
            <th className="px-4 py-3">Company</th>
            <th className="px-4 py-3">Role</th>
            <th className="px-4 py-3">Board</th>
            <th className="px-4 py-3">Score</th>
            <th className="px-4 py-3">Status</th>
            <th className="px-4 py-3">Applied Date</th>
            <th className="px-4 py-3">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {applications.map((app) => (
            <tr key={app.id}>
              <td className="px-4 py-3 font-medium">{app.company ?? "--"}</td>
              <td className="px-4 py-3">{app.title ?? "--"}</td>
              <td className="px-4 py-3">{app.board ?? "--"}</td>
              <td className="px-4 py-3"><ScoreBadge score={(app as any).total_score} /></td>
              <td className="px-4 py-3"><ApplicationStatusBadge status={app.status} /></td>
              <td className="px-4 py-3">{formatDate(app.submitted_at)}</td>
              <td className="px-4 py-3">
                <Button size="sm" variant="outline" onClick={() => onOpen(app.id)}>Open</Button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ApplicationDetailPanel({
  applicationId,
  onClose,
}: {
  applicationId: string;
  onClose: () => void;
}) {
  const [tab, setTab] = useState("overview");
  const detail = useQuery({
    queryKey: ["application", applicationId],
    queryFn: () => api.getApplication(applicationId).catch(() => null),
  });
  const app = detail.data;

  return (
    <div className="fixed inset-0 z-40 bg-slate-950/30" onClick={onClose}>
      <aside className="absolute right-0 top-0 h-full w-[65vw] overflow-auto bg-white shadow-xl" onClick={(event) => event.stopPropagation()}>
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-slate-200 bg-white px-6 py-4">
          <div>
            <h2 className="text-lg font-semibold">{app?.company ?? "Application detail"}</h2>
            <p className="text-sm text-slate-500">{app?.title ?? app?.job?.title ?? applicationId}</p>
          </div>
          <div className="flex items-center gap-2">
            {app && <FeedbackButton applicationId={app.id} traceId={app.trace_id} />}
            <button onClick={onClose}><X className="h-5 w-5" /></button>
          </div>
        </div>
        <div className="border-b border-slate-200 px-6">
          {["overview", "cover letter", "resume", "form answers", "agent log"].map((item) => (
            <button
              key={item}
              className={`mr-5 border-b-2 py-3 text-sm ${tab === item ? "border-slate-900 text-slate-900" : "border-transparent text-slate-500"}`}
              onClick={() => setTab(item)}
            >
              {item}
            </button>
          ))}
        </div>
        <div className="p-6">
          {!app && <p className="text-sm text-slate-500">Application detail endpoint is not available yet.</p>}
          {app && <DetailTab tab={tab} app={app} />}
        </div>
      </aside>
    </div>
  );
}

function DetailTab({ tab, app }: { tab: string; app: ApplicationDetailResponse }) {
  if (tab === "cover letter") {
    return (
      <div className="space-y-3">
        <div className="flex gap-2">
          <ApplicationStatusBadge status={app.status} />
          {app.cover_letter?.fact_check_passed && <span className="text-sm text-emerald-700">Fact-check passed</span>}
          <span className="text-sm text-slate-500">{app.cover_letter?.word_count ?? "--"} words</span>
        </div>
        <textarea className="min-h-96 w-full rounded-md border border-slate-200 p-3 text-sm" defaultValue={app.cover_letter?.content ?? ""} readOnly />
        <Button variant="outline">Edit</Button>
      </div>
    );
  }
  if (tab === "resume") {
    return (
      <div className="space-y-3">
        <iframe className="h-[560px] w-full rounded-md border border-slate-200" src={api.fileUrl(`/api/applications/${app.id}/resume.pdf`)} />
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => window.open(api.fileUrl(`/api/applications/${app.id}/resume.pdf`), "_blank")}><Download className="h-4 w-4" />Download PDF</Button>
          <Button variant="outline" onClick={() => window.open(api.fileUrl(`/api/applications/${app.id}/resume.docx`), "_blank")}><Download className="h-4 w-4" />Download DOCX</Button>
        </div>
      </div>
    );
  }
  if (tab === "form answers") {
    return <FormAnswers app={app} />;
  }
  if (tab === "agent log") {
    return <AgentLog app={app} />;
  }
  return (
    <div className="space-y-4">
      <ApplicationStatusBadge status={app.status} />
      {app.is_dream_company && <span className="ml-2 text-sm text-violet-700">Dream company</span>}
      <div className="grid grid-cols-2 gap-4 text-sm">
        <Info label="Queued" value={formatDate(app.queued_at)} />
        <Info label="Started" value={formatDate(app.started_at)} />
        <Info label="Submitted" value={formatDate(app.submitted_at)} />
        <Info label="Trace ID" value={app.trace_id} />
      </div>
      <Link href={`/applications/${app.id}/review`}>
        <Button>Open Review Screen</Button>
      </Link>
    </div>
  );
}

function FormAnswers({ app }: { app: ApplicationDetailResponse }) {
  const rows = app.agent_log.filter((log) => log.field_name);
  return (
    <table className="w-full text-left text-sm">
      <thead className="bg-slate-50 text-xs uppercase text-slate-500">
        <tr><th className="p-2">Field</th><th className="p-2">Value</th><th className="p-2">Confidence</th><th className="p-2">Status</th><th className="p-2">Screenshot</th></tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.id} className={(row.confidence ?? 1) < 0.8 ? "bg-amber-50" : ""}>
            <td className="p-2">{row.field_name}</td>
            <td className="p-2">{String((row.action_data as any)?.value ?? "--")}</td>
            <td className="p-2"><ConfidenceBadge confidence={row.confidence} /></td>
            <td className="p-2">{row.status}</td>
            <td className="p-2">
              {row.screenshot_path ? (
                <a href={api.fileUrl(`/api/applications/${app.id}/screenshots/${row.step_number}`)} target="_blank">
                  <img
                    src={api.fileUrl(`/api/applications/${app.id}/screenshots/${row.step_number}`)}
                    alt={`Step ${row.step_number} screenshot`}
                    className="h-10 w-16 rounded border border-slate-200 object-cover"
                  />
                </a>
              ) : "--"}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function AgentLog({ app }: { app: ApplicationDetailResponse }) {
  return (
    <div className="space-y-2">
      <Button variant="outline" onClick={() => downloadJson(app.agent_log)}>Export log as JSON</Button>
      {app.agent_log.map((log) => (
        <div key={log.id} className="rounded-md border border-slate-200 p-3 text-sm">
          <div className="flex justify-between">
            <span>Step {log.step_number}: {log.action_type} {log.field_name}</span>
            <ConfidenceBadge confidence={log.confidence} />
          </div>
          <p className="mt-1 text-xs text-slate-500">{formatRelativeTime(log.created_at)} - {log.status}</p>
          {log.screenshot_path && (
            <details className="mt-2">
              <summary className="cursor-pointer text-xs font-medium text-slate-600">View screenshot</summary>
              <img
                src={api.fileUrl(`/api/applications/${app.id}/screenshots/${log.step_number}`)}
                alt={`Step ${log.step_number} screenshot`}
                className="mt-2 max-h-72 rounded-md border border-slate-200"
              />
            </details>
          )}
        </div>
      ))}
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-slate-200 p-3">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="mt-1 break-all font-medium">{value}</p>
    </div>
  );
}

function downloadJson(payload: unknown) {
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "agent-log.json";
  link.click();
  URL.revokeObjectURL(url);
}
