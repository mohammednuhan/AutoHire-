"use client";

import { AlertCircle, X } from "lucide-react";
import { errorCopy } from "../../lib/errors";
import { useAgentStore } from "../../store/agentStore";

export function ErrorBanner() {
  const errors = useAgentStore((state) => state.errorQueue);
  const dismiss = useAgentStore((state) => state.dismissError);
  const persistent = errors.find((event) => errorCopy(event.error_code, event.message).persistent);
  if (!persistent) return null;
  const index = errors.indexOf(persistent);
  const copy = errorCopy(persistent.error_code, persistent.message);

  return (
    <div className="mb-4 flex items-start justify-between rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">
      <div className="flex gap-3">
        <AlertCircle className="mt-0.5 h-5 w-5 shrink-0" />
        <div>
          <p className="font-semibold">{copy.title}</p>
          <p className="mt-1">{copy.message}</p>
          <p className="mt-1 text-red-700">{copy.action}</p>
        </div>
      </div>
      <button className="rounded p-1 hover:bg-red-100" onClick={() => dismiss(index)}>
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}
