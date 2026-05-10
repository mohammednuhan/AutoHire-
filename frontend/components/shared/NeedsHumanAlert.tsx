"use client";

import Link from "next/link";
import { AlertTriangle, X } from "lucide-react";
import { useAgentStore } from "../../store/agentStore";
import { Button } from "../ui/button";

export function NeedsHumanAlert() {
  const queue = useAgentStore((state) => state.needsHumanQueue);
  const resolve = useAgentStore((state) => state.resolveNeedsHuman);
  if (!queue.length) return null;
  const item = queue[0];

  return (
    <div className="mb-4 flex items-center justify-between rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
      <div className="flex min-w-0 items-center gap-3">
        <AlertTriangle className="h-5 w-5 shrink-0" />
        <div className="truncate">
          <span className="font-semibold">{queue.length} application needs input.</span>{" "}
          {item.company} - {item.field_name}
        </div>
      </div>
      <div className="flex items-center gap-2">
        <Link href={`/applications/${item.application_id}/review`}>
          <Button size="sm" variant="outline">Respond</Button>
        </Link>
        <button className="rounded p-1 hover:bg-amber-100" onClick={() => resolve(item.trace_id)}>
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
