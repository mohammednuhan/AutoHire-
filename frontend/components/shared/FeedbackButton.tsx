"use client";

import { useState } from "react";
import { toast } from "sonner";
import { api } from "../../lib/api";
import { Button } from "../ui/button";
import { Textarea } from "../ui/form";

export function FeedbackButton({
  applicationId,
  traceId,
}: {
  applicationId?: string | null;
  traceId?: string | null;
}) {
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState("");
  const [file, setFile] = useState<File | null>(null);

  async function submit() {
    if (!message.trim()) return;
    try {
      await api.submitFeedback({
        application_id: applicationId ?? undefined,
        trace_id: traceId ?? undefined,
        message,
        screenshot: file,
      });
      toast.success("Feedback submitted");
      setOpen(false);
      setMessage("");
      setFile(null);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not submit feedback");
    }
  }

  return (
    <>
      <Button variant="ghost" size="sm" onClick={() => setOpen(true)}>
        Report an issue
      </Button>
      {open && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-slate-950/40">
          <div className="w-[480px] rounded-lg bg-white p-5 shadow-xl">
            <h2 className="text-lg font-semibold">Report an issue</h2>
            <label className="mt-4 block text-sm font-medium text-slate-700">What went wrong?</label>
            <Textarea className="mt-2 min-h-32" value={message} onChange={(event) => setMessage(event.target.value)} />
            <label className="mt-4 block text-sm font-medium text-slate-700">Screenshot</label>
            <input className="mt-2 text-sm" type="file" accept="image/*" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
            <div className="mt-5 flex justify-end gap-2">
              <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
              <Button disabled={!message.trim()} onClick={submit}>Submit</Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
