"use client";

import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, FileUp, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { TagInput } from "../../components/shared/TagInput";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardHeader } from "../../components/ui/card";
import { Input, Label, Select, Textarea } from "../../components/ui/form";
import { api } from "../../lib/api";
import type { ResumeProfile } from "../../types/api";

type OnboardingStep = "expectations" | "upload" | "profile" | "preferences";

const emptyProfile: ResumeProfile = {
  full_name: "",
  email: "",
  phone: "",
  location: "",
  linkedin_url: "",
  github_url: "",
  portfolio_url: "",
  summary: "",
  education: [],
  experience: [],
  projects: [],
  skills: { languages: [], frameworks: [], databases: [], tools: [], cloud: [], soft_skills: [] },
  certifications: [],
  achievements: [],
  languages_spoken: [],
};

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = useState<OnboardingStep>("expectations");
  const [file, setFile] = useState<File | null>(null);
  const [profile, setProfile] = useState<ResumeProfile>(emptyProfile);
  const [progress, setProgress] = useState("");
  const [preferences, setPreferences] = useState({
    target_roles: [] as string[],
    preferred_locations: [] as string[],
    work_type: "any",
    score_threshold: 70,
    max_apps_per_day: 10,
    dream_companies: [] as string[],
    blacklisted_companies: [] as string[],
    enabled_boards: ["wellfound", "internshala"] as string[],
    telegram_bot_token: "",
    telegram_chat_id: "",
  });

  const completeness = useMemo(() => profileCompleteness(profile), [profile]);
  const upload = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error("Select a resume first");
      setProgress("Extracting text...");
      await wait(500);
      setProgress("Analyzing with AI...");
      const result = await api.uploadResume(file);
      setProgress("Building your profile...");
      await wait(500);
      return result;
    },
    onSuccess: (result) => {
      setProfile(result.profile);
      setStep("profile");
      toast.success("Resume parsed");
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "Upload failed"),
  });

  async function saveProfileAndContinue() {
    try {
      await api.updateProfile(profile as any);
      setStep("preferences");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not save profile");
    }
  }

  async function startAutoHire() {
    try {
      await api.updateProfile(preferences as any);
      router.push("/dashboard");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not save preferences");
    }
  }

  if (step === "expectations") {
    return (
      <OnboardingShell stepLabel="Before you start">
        <Card className="mx-auto max-w-2xl border-amber-200 bg-amber-50">
          <CardHeader>
            <div className="flex items-center gap-2 text-amber-900">
              <AlertTriangle className="h-5 w-5" />
              <h1 className="text-lg font-semibold">Honest Expectations</h1>
            </div>
          </CardHeader>
          <CardContent className="space-y-4 text-sm leading-6 text-amber-950">
            <p>
              Before you start: AutoHire is autonomous but not perfect. In the first week,
              it may make some mistakes - that's expected and normal.
            </p>
            <p>
              Every action is logged and reviewable. You will always be asked before
              AutoHire applies to your dream companies.
            </p>
            <p>You can stop the agent at any time. Review applications before they're submitted.</p>
            <Button onClick={() => setStep("upload")}>I understand - continue</Button>
            <p className="rounded-md border border-amber-200 bg-white/60 p-3 text-xs leading-5">
              AutoHire automates browser interactions to help manage job applications. You are
              responsible for compliance with each platform's Terms of Service. Use responsibly and
              at your own discretion. The authors are not liable for account restrictions resulting
              from automated usage. Built-in rate limits are enforced to minimize detection risk -
              do not attempt to bypass them.
            </p>
          </CardContent>
        </Card>
      </OnboardingShell>
    );
  }

  return (
    <OnboardingShell stepLabel={step === "upload" ? "Step 1 of 3" : step === "profile" ? "Step 2 of 3" : "Step 3 of 3"}>
      {step === "upload" && (
        <Card className="mx-auto max-w-3xl">
          <CardHeader>
            <h1 className="text-lg font-semibold">Upload Resume</h1>
            <p className="text-sm text-slate-500">PDF or DOCX, max 10MB</p>
          </CardHeader>
          <CardContent className="space-y-4">
            <label
              className="flex h-64 cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-slate-300 bg-slate-50 text-center hover:bg-slate-100"
              onDragOver={(event) => event.preventDefault()}
              onDrop={(event) => {
                event.preventDefault();
                setFile(event.dataTransfer.files[0] ?? null);
              }}
            >
              <FileUp className="h-10 w-10 text-slate-500" />
              <span className="mt-3 font-medium">Drop your resume here or click to browse</span>
              <span className="mt-1 text-sm text-slate-500">PDF or DOCX, max 10MB</span>
              <input hidden type="file" accept=".pdf,.docx" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
            </label>
            {file && (
              <div className="rounded-md border border-slate-200 p-3 text-sm">
                {file.name} - {(file.size / 1024 / 1024).toFixed(2)} MB
              </div>
            )}
            {progress && (
              <div className="flex items-center gap-2 text-sm text-slate-600">
                <Loader2 className="h-4 w-4 animate-spin" />
                {progress}
              </div>
            )}
            <Button disabled={!file || upload.isPending} onClick={() => upload.mutate()}>
              Parse Resume
            </Button>
          </CardContent>
        </Card>
      )}

      {step === "profile" && (
        <Card className="mx-auto max-w-5xl">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-lg font-semibold">Review Your Profile</h1>
                <p className="text-sm text-slate-500">Every field is editable inline.</p>
              </div>
              <span className="text-sm font-semibold">{completeness}% complete</span>
            </div>
            <div className="h-2 rounded-full bg-slate-100">
              <div className="h-2 rounded-full bg-emerald-600" style={{ width: `${completeness}%` }} />
            </div>
          </CardHeader>
          <CardContent className="space-y-6">
            <ProfileEditor profile={profile} onChange={setProfile} />
            <Button onClick={saveProfileAndContinue}>Looks good, continue</Button>
          </CardContent>
        </Card>
      )}

      {step === "preferences" && (
        <Card className="mx-auto max-w-5xl">
          <CardHeader>
            <h1 className="text-lg font-semibold">Set Preferences</h1>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-5">
            <PreferenceTags label="Target roles" field="target_roles" preferences={preferences} setPreferences={setPreferences} />
            <PreferenceTags label="Preferred locations" field="preferred_locations" preferences={preferences} setPreferences={setPreferences} />
            <Field label="Work type">
              <Select value={preferences.work_type} onChange={(event) => setPreferences({ ...preferences, work_type: event.target.value })}>
                {["remote", "hybrid", "onsite", "any"].map((item) => <option key={item} value={item}>{item}</option>)}
              </Select>
            </Field>
            <Field label={`Score threshold: ${preferences.score_threshold}`}>
              <input type="range" min={50} max={95} value={preferences.score_threshold} onChange={(event) => setPreferences({ ...preferences, score_threshold: Number(event.target.value) })} className="w-full" />
              <p className="mt-1 text-xs text-slate-500">At {preferences.score_threshold}, roughly 12 jobs/week would qualify.</p>
            </Field>
            <Field label="Max applications per day">
              <Input type="number" min={1} max={30} value={preferences.max_apps_per_day} onChange={(event) => setPreferences({ ...preferences, max_apps_per_day: Number(event.target.value) })} />
            </Field>
            <PreferenceTags label="Dream companies" field="dream_companies" preferences={preferences} setPreferences={setPreferences} />
            <PreferenceTags label="Blacklisted companies" field="blacklisted_companies" preferences={preferences} setPreferences={setPreferences} />
            <Field label="Job boards">
              <div className="space-y-2 text-sm">
                {["wellfound", "internshala", "naukri", "foundit"].map((board) => (
                  <label key={board} className="flex items-center gap-2">
                    <input type="checkbox" checked={preferences.enabled_boards.includes(board)} onChange={() => toggleBoard(board, preferences, setPreferences)} />
                    {board}
                  </label>
                ))}
              </div>
            </Field>
            <Field label="Telegram bot token">
              <Input value={preferences.telegram_bot_token} onChange={(event) => setPreferences({ ...preferences, telegram_bot_token: event.target.value })} />
            </Field>
            <Field label="Telegram chat ID">
              <div className="flex gap-2">
                <Input value={preferences.telegram_chat_id} onChange={(event) => setPreferences({ ...preferences, telegram_chat_id: event.target.value })} />
                <Button variant="outline" onClick={() => api.testTelegram({ bot_token: preferences.telegram_bot_token, chat_id: preferences.telegram_chat_id }).catch(() => toast.error("Telegram test endpoint unavailable"))}>Test</Button>
              </div>
            </Field>
            <div className="col-span-2">
              <Button size="lg" onClick={startAutoHire}>Start AutoHire</Button>
            </div>
          </CardContent>
        </Card>
      )}
    </OnboardingShell>
  );
}

function OnboardingShell({ stepLabel, children }: { stepLabel: string; children: ReactNode }) {
  return (
    <main className="min-h-screen bg-slate-50 px-6 py-12 text-slate-950">
      <div className="mx-auto mb-8 max-w-5xl">
        <p className="text-sm font-medium text-slate-500">{stepLabel}</p>
        <h1 className="mt-1 text-2xl font-semibold">AutoHire setup</h1>
      </div>
      {children}
    </main>
  );
}

function ProfileEditor({ profile, onChange }: { profile: ResumeProfile; onChange: (profile: ResumeProfile) => void }) {
  return (
    <div className="grid grid-cols-2 gap-5">
      <Field label="Full name" missing={!profile.full_name}><Input value={profile.full_name} onChange={(event) => onChange({ ...profile, full_name: event.target.value })} /></Field>
      <Field label="Email" missing={!profile.email}><Input value={profile.email ?? ""} onChange={(event) => onChange({ ...profile, email: event.target.value })} /></Field>
      <Field label="Phone"><Input value={profile.phone ?? ""} onChange={(event) => onChange({ ...profile, phone: event.target.value })} /></Field>
      <Field label="Location"><Input value={profile.location ?? ""} onChange={(event) => onChange({ ...profile, location: event.target.value })} /></Field>
      <Field label="Skills" missing={!profile.skills.languages.length}><Textarea value={Object.values(profile.skills).flat().join(", ")} onChange={(event) => onChange({ ...profile, skills: { ...profile.skills, languages: commaList(event.target.value) } })} /></Field>
      <Field label="Experience"><Textarea value={profile.experience.map((item) => `${item.role} at ${item.company}`).join("\n")} readOnly /></Field>
      <Field label="Projects"><Textarea value={profile.projects.map((item) => item.name).join("\n")} readOnly /></Field>
      <Field label="Education"><Textarea value={profile.education.map((item) => `${item.degree} - ${item.institution}`).join("\n")} readOnly /></Field>
    </div>
  );
}

function Field({ label, missing, children }: { label: string; missing?: boolean; children: ReactNode }) {
  return (
    <label className="block space-y-2">
      <div className="flex items-center gap-2">
        <Label>{label}</Label>
        {missing && <span className="text-xs text-amber-700" title="This helps AutoHire answer forms accurately.">missing</span>}
      </div>
      <div className={missing ? "rounded-md border border-amber-300" : ""}>{children}</div>
    </label>
  );
}

function PreferenceTags({ label, field, preferences, setPreferences }: any) {
  return (
    <Field label={label}>
      <TagInput
        values={preferences[field]}
        placeholder="Type and press Enter"
        onAdd={(value) => setPreferences({ ...preferences, [field]: [...preferences[field], value] })}
        onRemove={(value) => setPreferences({ ...preferences, [field]: preferences[field].filter((item: string) => item !== value) })}
      />
    </Field>
  );
}

function toggleBoard(board: string, preferences: any, setPreferences: (value: any) => void) {
  const enabled = preferences.enabled_boards.includes(board);
  setPreferences({
    ...preferences,
    enabled_boards: enabled ? preferences.enabled_boards.filter((item: string) => item !== board) : [...preferences.enabled_boards, board],
  });
}

function profileCompleteness(profile: ResumeProfile) {
  const checks = [
    Boolean(profile.full_name),
    Boolean(profile.email),
    profile.experience.length > 0,
    profile.projects.length > 0,
    profile.skills.languages.length > 0 || profile.skills.frameworks.length > 0,
    profile.education.length > 0,
  ];
  return Math.round((checks.filter(Boolean).length / checks.length) * 100);
}

function commaList(value: string) {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

function wait(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
