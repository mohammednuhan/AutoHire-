"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowLeft, CheckCircle2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { AppShell } from "../../../../components/layout/AppShell";
import { ApplicationStatusBadge } from "../../../../components/shared/ApplicationStatusBadge";
import { ConfidenceBadge } from "../../../../components/shared/ConfidenceBadge";
import { ScoreBreakdownChart } from "../../../../components/shared/ScoreBreakdownChart";
import { Badge } from "../../../../components/ui/badge";
import { Button } from "../../../../components/ui/button";
import { Card, CardContent, CardHeader } from "../../../../components/ui/card";
import { Textarea } from "../../../../components/ui/form";
import { api } from "../../../../lib/api";

export default function ReviewPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const detail = useQuery({
    queryKey: ["application", params.id],
    queryFn: () => api.getApplication(params.id).catch(() => null),
  });

  const submit = useMutation({
    mutationFn: () => api.submitApplication(params.id),
    onSuccess: () => {
      setSubmitted(true);
      toast.success("Application submitted");
      setTimeout(() => router.push("/applications"), 1200);
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "Submit failed"),
  });

  const app = detail.data;
  const hasUnresolvedNeedsHuman = Boolean(
    app?.agent_log.some((log) => {
      const value = answers[log.id] ?? String((log.action_data as any)?.value ?? "");
      return value === "NEEDS_HUMAN";
    }),
  );

  return (
    <AppShell>
      <div className="space-y-4 pb-20">
        <div className="flex items-center justify-between">
          <Link href="/applications" className="inline-flex items-center gap-2 text-sm text-slate-600">
            <ArrowLeft className="h-4 w-4" /> Back
          </Link>
          {app && <ApplicationStatusBadge status={app.status} />}
        </div>

        {submitted && (
          <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-emerald-800">
            <CheckCircle2 className="mr-2 inline h-5 w-5" />
            Applied. Good luck.
          </div>
        )}

        {!app && (
          <Card>
            <CardContent>
              <p className="text-sm text-slate-500">Application detail endpoint is not available yet.</p>
            </CardContent>
          </Card>
        )}

        {app && (
          <>
            <div className="grid grid-cols-5 gap-4">
              <Card className="col-span-3">
                <CardHeader>
                  <h2 className="font-semibold">Prepared application</h2>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div>
                    <label className="text-sm font-medium">Cover letter</label>
                    <Textarea className="mt-2 min-h-72" defaultValue={app.cover_letter?.content ?? ""} />
                  </div>
                  <iframe
                    className="h-[460px] w-full rounded-md border border-slate-200"
                    src={api.fileUrl(`/api/applications/${app.id}/resume.pdf`)}
                  />
                </CardContent>
              </Card>

              <Card className="col-span-2">
                <CardHeader>
                  <h2 className="font-semibold">{app.job?.title ?? app.title}</h2>
                  <p className="text-sm text-slate-500">{app.company ?? app.job?.company}</p>
                </CardHeader>
                <CardContent className="space-y-4">
                  <ScoreBreakdownChart score={app.job?.score_breakdown} />
                  <div>
                    <h3 className="text-sm font-semibold">Key requirements</h3>
                    <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-600">
                      {(app.job?.skills_required ?? []).map((skill) => <li key={skill}>{skill}</li>)}
                    </ul>
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold">Matching skills</h3>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {(app.job?.score_breakdown?.matching_skills ?? []).map((skill) => (
                        <Badge key={skill} variant="green">{skill}</Badge>
                      ))}
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>

            <Card>
              <CardHeader>
                <h2 className="font-semibold">Form Answers Preview</h2>
              </CardHeader>
              <CardContent>
                <table className="w-full text-left text-sm">
                  <thead className="text-xs uppercase text-slate-500">
                    <tr><th className="p-2">Field</th><th className="p-2">Value</th><th className="p-2">Confidence</th><th className="p-2">Status</th></tr>
                  </thead>
                  <tbody>
                    {app.agent_log.map((log) => {
                      const value = answers[log.id] ?? String((log.action_data as any)?.value ?? "");
                      const unresolved = value === "NEEDS_HUMAN";
                      return (
                        <tr key={log.id} className={unresolved ? "bg-amber-50" : ""}>
                          <td className="p-2">{log.field_name ?? "--"}</td>
                          <td className="p-2">
                            <input
                              className="w-full rounded border border-slate-200 px-2 py-1"
                              value={value}
                              onChange={(event) => setAnswers((current) => ({ ...current, [log.id]: event.target.value }))}
                            />
                          </td>
                          <td className="p-2"><ConfidenceBadge confidence={log.confidence} /></td>
                          <td className="p-2">{log.status}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
                {hasUnresolvedNeedsHuman && (
                  <p className="mt-3 text-sm text-amber-700">Fill every highlighted answer before submitting.</p>
                )}
              </CardContent>
            </Card>
          </>
        )}

        <div className="fixed bottom-0 left-64 right-0 flex items-center justify-between border-t border-slate-200 bg-white px-6 py-3">
          <Link href="/applications" className="text-sm text-slate-600">Back</Link>
          <Button variant="outline">Save for Later</Button>
          <div className="flex items-center gap-3">
            <Button variant="ghost">Skip this application</Button>
            <Button variant="success" size="lg" disabled={hasUnresolvedNeedsHuman} onClick={() => setConfirmOpen(true)}>
              Submit Application
            </Button>
          </div>
        </div>

        {confirmOpen && app && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40">
            <div className="w-[440px] rounded-lg bg-white p-6 shadow-xl">
              <h2 className="text-lg font-semibold">Confirm submit</h2>
              <p className="mt-2 text-sm text-slate-600">
                You are about to submit your application to {app.company} for {app.title}.
                This cannot be undone.
              </p>
              <div className="mt-6 flex justify-end gap-2">
                <Button variant="outline" onClick={() => setConfirmOpen(false)}>Cancel</Button>
                <Button variant="success" onClick={() => submit.mutate()} disabled={submit.isPending}>
                  Confirm Submit
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
