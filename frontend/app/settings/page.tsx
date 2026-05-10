"use client";

import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Eye, EyeOff, Play } from "lucide-react";
import { toast } from "sonner";
import { AppShell } from "../../components/layout/AppShell";
import { TagInput } from "../../components/shared/TagInput";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardHeader } from "../../components/ui/card";
import { Input, Label, Select } from "../../components/ui/form";
import { api } from "../../lib/api";
import { formatDate } from "../../lib/utils";
import { usePreferencesStore } from "../../store/preferencesStore";

const tabs = ["Profile", "Job Boards", "Schedule", "Notifications", "Advanced"];

export default function SettingsPage() {
  const [tab, setTab] = useState("Profile");
  const queryClient = useQueryClient();
  const profile = useQuery({ queryKey: ["profile"], queryFn: api.getProfile });
  const { preferences, setPreferences, setPreference, addTag, removeTag } = usePreferencesStore();
  const [showKeys, setShowKeys] = useState(false);

  useEffect(() => {
    if (profile.data?.preferences) setPreferences(profile.data.preferences);
  }, [profile.data?.preferences, setPreferences]);

  const save = useMutation({
    mutationFn: () => api.updateProfile(preferences as any),
    onSuccess: () => {
      toast.success("Settings saved");
      queryClient.invalidateQueries({ queryKey: ["profile"] });
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "Could not save"),
  });

  return (
    <AppShell>
      <div className="space-y-4">
        <div className="flex gap-2 border-b border-slate-200">
          {tabs.map((item) => (
            <button
              key={item}
              className={`border-b-2 px-3 py-2 text-sm ${tab === item ? "border-slate-900 text-slate-900" : "border-transparent text-slate-500"}`}
              onClick={() => setTab(item)}
            >
              {item}
            </button>
          ))}
        </div>

        {tab === "Profile" && (
          <Card>
            <CardHeader>
              <h2 className="font-semibold">Resume profile</h2>
            </CardHeader>
            <CardContent className="grid grid-cols-2 gap-4">
              <Field label="Replace current resume"><Input type="file" accept=".pdf,.docx" /></Field>
              <Info label="Current resume" value={profile.data?.resume_id ?? "No resume uploaded"} />
              <Info label="Parsed date" value={formatDate((profile.data as any)?.parsed_at)} />
              <Info label="Profile completeness" value="Calculated during onboarding" />
              <div className="col-span-2">
                <Button variant="outline">Re-parse resume</Button>
              </div>
            </CardContent>
          </Card>
        )}

        {tab === "Job Boards" && (
          <Card>
            <CardHeader><h2 className="font-semibold">Job boards</h2></CardHeader>
            <CardContent className="space-y-5">
              <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-xs leading-5 text-amber-950">
                AutoHire automates browser interactions to help manage job applications. You are
                responsible for compliance with each platform's Terms of Service. Use responsibly and
                at your own discretion. The authors are not liable for account restrictions resulting
                from automated usage. Built-in rate limits are enforced to minimize detection risk -
                do not attempt to bypass them.
              </div>
              {["wellfound", "internshala", "naukri", "foundit", "linkedin"].map((board) => {
                const locked = board === "linkedin";
                const enabled = (preferences.enabled_boards ?? []).includes(board);
                return (
                  <div key={board} className="flex items-center justify-between rounded-md border border-slate-200 p-3">
                    <div>
                      <p className="font-medium capitalize">{board}</p>
                      <p className="text-xs text-slate-500">{locked ? "Phase 3 only. Never automated in v1." : "Last scraped: --, jobs found last run: --"}</p>
                    </div>
                    <div className="flex items-center gap-3">
                      {(board === "naukri" || board === "foundit") && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => api.saveBoardLogin(board).catch(() => toast.error("Could not start board login"))}
                        >
                          Login profile
                        </Button>
                      )}
                      <input type="checkbox" disabled={locked} checked={enabled} onChange={() => toggleBoard(board, preferences.enabled_boards ?? [], setPreference)} />
                    </div>
                  </div>
                );
              })}
              <Field label={`Score threshold: ${preferences.score_threshold ?? 70}`}>
                <input className="w-full" type="range" min={50} max={95} value={preferences.score_threshold ?? 70} onChange={(event) => setPreference("score_threshold", Number(event.target.value))} />
                <p className="text-xs text-slate-500">Higher thresholds reduce queue volume.</p>
              </Field>
              <Button onClick={() => save.mutate()} disabled={save.isPending}>Save boards</Button>
            </CardContent>
          </Card>
        )}

        {tab === "Schedule" && (
          <Card>
            <CardHeader><h2 className="font-semibold">Schedule</h2></CardHeader>
            <CardContent className="grid grid-cols-2 gap-4">
              <Field label="Run time"><Input type="time" defaultValue="07:00" /></Field>
              <Info label="Timezone" value="Asia/Kolkata" />
              <Field label={`Max applications per day: ${preferences.max_apps_per_day ?? 10}`}>
                <input className="w-full" type="range" min={1} max={30} value={preferences.max_apps_per_day ?? 10} onChange={(event) => setPreference("max_apps_per_day", Number(event.target.value))} />
              </Field>
              <div className="flex items-end">
                <Button variant="outline" onClick={() => api.runAgent().catch(() => toast.error("Could not run scan"))}>
                  <Play className="h-4 w-4" /> Run scan now
                </Button>
              </div>
              <div className="col-span-2"><Button onClick={() => save.mutate()}>Save schedule</Button></div>
            </CardContent>
          </Card>
        )}

        {tab === "Notifications" && (
          <Card>
            <CardHeader><h2 className="font-semibold">Notifications</h2></CardHeader>
            <CardContent className="grid grid-cols-2 gap-4">
              <Field label="Telegram bot token"><Input type={showKeys ? "text" : "password"} /></Field>
              <Field label="Telegram chat ID"><Input defaultValue={preferences.telegram_chat_id ?? ""} onChange={(event) => setPreference("telegram_chat_id", event.target.value)} /></Field>
              <Button variant="outline" onClick={() => setShowKeys(!showKeys)}>{showKeys ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}Show/hide</Button>
              <Button variant="outline" onClick={() => api.testTelegram({ chat_id: preferences.telegram_chat_id ?? "" }).catch(() => toast.error("Telegram test endpoint unavailable"))}>Send test message</Button>
              {["Morning digest", "High-score job found", "Application submitted", "Needs human input"].map((item) => (
                <label key={item} className="flex items-center gap-2 text-sm">
                  <input type="checkbox" defaultChecked />
                  {item}
                </label>
              ))}
            </CardContent>
          </Card>
        )}

        {tab === "Advanced" && (
          <Card>
            <CardHeader><h2 className="font-semibold">Advanced</h2></CardHeader>
            <CardContent className="grid grid-cols-2 gap-5">
              <Field label="Dream companies"><TagInput values={preferences.dream_companies ?? []} placeholder="Add company" onAdd={(value) => addTag("dream_companies", value)} onRemove={(value) => removeTag("dream_companies", value)} /></Field>
              <Field label="Blacklisted companies"><TagInput values={preferences.blacklisted_companies ?? []} placeholder="Add company" onAdd={(value) => addTag("blacklisted_companies", value)} onRemove={(value) => removeTag("blacklisted_companies", value)} /></Field>
              <Field label="Blacklisted keywords"><TagInput values={preferences.keyword_blacklist ?? []} placeholder="Add keyword" onAdd={(value) => setPreference("keyword_blacklist", [...(preferences.keyword_blacklist ?? []), value])} onRemove={(value) => setPreference("keyword_blacklist", (preferences.keyword_blacklist ?? []).filter((item) => item !== value))} /></Field>
              <Field label="LLM provider"><Select value={preferences.llm_provider ?? "gemini"} onChange={(event) => setPreference("llm_provider", event.target.value as any)}><option value="gemini">Gemini</option><option value="claude">Claude</option><option value="ollama">Ollama</option></Select></Field>
              <Field label="Quality mode"><Select value={preferences.llm_quality_mode ?? "balanced"} onChange={(event) => setPreference("llm_quality_mode", event.target.value as any)}><option value="fast">Fast</option><option value="balanced">Balanced</option><option value="maximum">Maximum</option></Select></Field>
              <Field label="API key"><Input type={showKeys ? "text" : "password"} placeholder="Stored in backend environment" /></Field>
              <div className="col-span-2 flex gap-2">
                <Button onClick={() => save.mutate()}>Save advanced settings</Button>
                <Button variant="outline">Test LLM connection</Button>
                <Button variant="danger" onClick={() => window.confirm("Reset all AutoHire data?") && window.confirm("This is permanent. Continue?")}>Reset all data</Button>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </AppShell>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return <label className="block space-y-2"><Label>{label}</Label>{children}</label>;
}

function Info({ label, value }: { label: string; value: string }) {
  return <div className="rounded-md border border-slate-200 p-3"><p className="text-xs text-slate-500">{label}</p><p className="mt-1 text-sm font-medium">{value}</p></div>;
}

function toggleBoard(board: string, enabledBoards: string[], setPreference: any) {
  const enabled = enabledBoards.includes(board);
  setPreference("enabled_boards", enabled ? enabledBoards.filter((item) => item !== board) : [...enabledBoards, board]);
}
