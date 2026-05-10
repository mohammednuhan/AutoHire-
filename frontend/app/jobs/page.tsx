"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Briefcase, MapPin, X } from "lucide-react";
import { toast } from "sonner";
import { AppShell } from "../../components/layout/AppShell";
import { ScoreBadge } from "../../components/shared/ScoreBadge";
import { ScoreBreakdownChart } from "../../components/shared/ScoreBreakdownChart";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent } from "../../components/ui/card";
import { Input, Select } from "../../components/ui/form";
import { api } from "../../lib/api";
import { formatRelativeTime } from "../../lib/utils";
import type { JobResponse } from "../../types/api";

const boards = ["wellfound", "internshala", "career_page"];
const statuses = ["all", "new", "queued", "applied", "skipped"];
const workTypes = ["all", "remote", "hybrid", "onsite"];

export default function JobsPage() {
  const queryClient = useQueryClient();
  const [scoreMin, setScoreMin] = useState(0);
  const [scoreMax, setScoreMax] = useState(100);
  const [selectedBoards, setSelectedBoards] = useState<string[]>([]);
  const [status, setStatus] = useState("all");
  const [workType, setWorkType] = useState("all");
  const [sort, setSort] = useState("score_desc");
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);

  const params = useMemo(
    () => ({
      score_min: scoreMin,
      score_max: scoreMax,
      board: selectedBoards.length ? selectedBoards : undefined,
      status: status === "all" ? undefined : status,
      work_type: workType === "all" ? undefined : workType,
      sort,
    }),
    [scoreMax, scoreMin, selectedBoards, sort, status, workType],
  );

  const jobs = useQuery({ queryKey: ["jobs", params], queryFn: () => api.listJobs(params) });
  const selectedJob = useQuery({
    queryKey: ["job", selectedJobId],
    queryFn: () => api.getJob(selectedJobId!),
    enabled: Boolean(selectedJobId),
  });

  const queueJob = useMutation({
    mutationFn: api.queueJob,
    onSuccess: () => {
      toast.success("Job queued");
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "Could not queue job"),
  });

  const skipJob = useMutation({
    mutationFn: api.skipJob,
    onSuccess: () => {
      toast.success("Job skipped");
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });

  return (
    <AppShell>
      <div className="space-y-4">
        <div className="sticky top-16 z-20 rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
          <div className="grid grid-cols-6 gap-3">
            <div className="col-span-2">
              <div className="flex items-center gap-2">
                <Input type="number" min={0} max={100} value={scoreMin} onChange={(event) => setScoreMin(Math.min(Number(event.target.value), scoreMax))} />
                <span className="text-xs text-slate-500">to</span>
                <Input type="number" min={0} max={100} value={scoreMax} onChange={(event) => setScoreMax(Math.max(Number(event.target.value), scoreMin))} />
              </div>
              <div className="mt-2 grid grid-cols-2 gap-2">
                <input type="range" min={0} max={100} value={scoreMin} onChange={(event) => setScoreMin(Math.min(Number(event.target.value), scoreMax))} />
                <input type="range" min={0} max={100} value={scoreMax} onChange={(event) => setScoreMax(Math.max(Number(event.target.value), scoreMin))} />
              </div>
            </div>
            <select
              multiple
              className="h-20 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm"
              value={selectedBoards}
              onChange={(event) =>
                setSelectedBoards(Array.from(event.currentTarget.selectedOptions, (option) => option.value))
              }
            >
              {boards.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
            <Select value={workType} onChange={(event) => setWorkType(event.target.value)}>
              {workTypes.map((item) => <option key={item} value={item}>{item}</option>)}
            </Select>
            <Select value={status} onChange={(event) => setStatus(event.target.value)}>
              {statuses.map((item) => <option key={item} value={item}>{item}</option>)}
            </Select>
            <Select value={sort} onChange={(event) => setSort(event.target.value)}>
              <option value="score_desc">Score desc</option>
              <option value="date_desc">Date desc</option>
              <option value="company_asc">Company A-Z</option>
            </Select>
          </div>
          <button
            className="mt-2 text-xs font-medium text-slate-500 hover:text-slate-900"
            onClick={() => {
              setScoreMin(0);
              setScoreMax(100);
              setSelectedBoards([]);
              setStatus("all");
              setWorkType("all");
              setSort("score_desc");
            }}
          >
            Clear filters
          </button>
        </div>

        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          {(jobs.data?.items ?? []).map((job) => (
            <JobCard
              key={job.id}
              job={job}
              onOpen={() => setSelectedJobId(job.id)}
              onQueue={() => queueJob.mutate(job.id)}
              onSkip={() => skipJob.mutate(job.id)}
            />
          ))}
          {jobs.isLoading && <div className="text-sm text-slate-500">Loading jobs...</div>}
          {!jobs.isLoading && (jobs.data?.items ?? []).length === 0 && (
            <div className="text-sm text-slate-500">No jobs match these filters.</div>
          )}
        </div>

        {selectedJobId && (
          <div className="fixed inset-0 z-40 bg-slate-950/30" onClick={() => setSelectedJobId(null)}>
            <aside
              className="absolute right-0 top-0 h-full w-[560px] overflow-auto bg-white p-6 shadow-xl"
              onClick={(event) => event.stopPropagation()}
            >
              <button className="absolute right-4 top-4 rounded p-1 hover:bg-slate-100" onClick={() => setSelectedJobId(null)}>
                <X className="h-5 w-5" />
              </button>
              {selectedJob.data && (
                <div className="space-y-5">
                  <div>
                    <p className="text-sm text-slate-500">{selectedJob.data.company}</p>
                    <h2 className="text-xl font-semibold">{selectedJob.data.title}</h2>
                    <div className="mt-2 flex gap-2">
                      <ScoreBadge score={selectedJob.data.total_score} />
                      <Badge>{selectedJob.data.board}</Badge>
                    </div>
                  </div>
                  <ScoreBreakdownChart score={selectedJob.data.score_breakdown} />
                  <SkillSection title="Matching skills" skills={selectedJob.data.score_breakdown?.matching_skills ?? []} tone="green" />
                  <SkillSection title="Missing skills" skills={selectedJob.data.score_breakdown?.missing_skills ?? []} tone="red" />
                  <div>
                    <h3 className="text-sm font-semibold">Score explanation</h3>
                    <p className="mt-1 text-sm text-slate-600">{selectedJob.data.score_breakdown?.score_explanation ?? "No explanation available."}</p>
                  </div>
                  <Badge
                    variant={
                      selectedJob.data.score_breakdown?.recommendation === "APPLY"
                        ? "green"
                        : selectedJob.data.score_breakdown?.recommendation === "SKIP"
                          ? "red"
                          : "yellow"
                    }
                  >
                    {selectedJob.data.score_breakdown?.recommendation ?? "REVIEW"}
                  </Badge>
                  <div className="max-h-72 overflow-auto rounded-md border border-slate-200 p-3 text-sm text-slate-700">
                    {selectedJob.data.description ?? "No description available."}
                  </div>
                  <Button className="w-full" onClick={() => queueJob.mutate(selectedJob.data.id)}>
                    Queue for Application
                  </Button>
                  <label className="flex items-center gap-2 text-sm text-slate-700">
                    <input type="checkbox" className="h-4 w-4" />
                    Mark as Dream Company
                  </label>
                  <button className="text-sm text-red-600" onClick={() => skipJob.mutate(selectedJob.data.id)}>
                    Skip this job
                  </button>
                </div>
              )}
            </aside>
          </div>
        )}
      </div>
    </AppShell>
  );
}

function JobCard({
  job,
  onOpen,
  onQueue,
  onSkip,
}: {
  job: JobResponse;
  onOpen: () => void;
  onQueue: () => void;
  onSkip: () => void;
}) {
  return (
    <Card className="cursor-pointer transition hover:border-slate-300" onClick={onOpen}>
      <CardContent className="space-y-4">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="font-semibold">{job.company}</h2>
              <Badge>{job.board}</Badge>
            </div>
            <p className="mt-1 text-sm text-slate-700">{job.title}</p>
          </div>
          <ScoreBadge score={job.total_score} />
        </div>
        <div className="flex flex-wrap gap-2 text-xs text-slate-600">
          <span className="inline-flex items-center gap-1"><MapPin className="h-3 w-3" />{job.location ?? "India"}</span>
          <Badge>{job.work_type ?? "not specified"}</Badge>
          <span>{formatRelativeTime(job.posted_at ?? job.scraped_at)}</span>
        </div>
        <div className="flex items-center justify-between border-t border-slate-100 pt-3" onClick={(event) => event.stopPropagation()}>
          {job.status !== "new" ? (
            <Badge variant="blue">{job.status}</Badge>
          ) : (
            <div className="flex gap-2">
              <Button size="sm" onClick={onQueue}><Briefcase className="h-4 w-4" />Queue</Button>
              <Button size="sm" variant="ghost" onClick={onSkip}>Skip</Button>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function SkillSection({ title, skills, tone }: { title: string; skills: string[]; tone: "green" | "red" }) {
  return (
    <div>
      <h3 className="text-sm font-semibold">{title}</h3>
      <div className="mt-2 flex flex-wrap gap-2">
        {skills.length === 0 && <span className="text-sm text-slate-500">None listed.</span>}
        {skills.map((skill) => <Badge key={skill} variant={tone}>{skill}</Badge>)}
      </div>
    </div>
  );
}
