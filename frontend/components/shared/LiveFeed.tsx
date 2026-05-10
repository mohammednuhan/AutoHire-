"use client";

import Link from "next/link";
import { AlertTriangle, CheckCircle2, Info, Zap } from "lucide-react";
import { cn, formatRelativeTime } from "../../lib/utils";
import type { WebSocketEvent } from "../../types/api";
import { Button } from "../ui/button";

const eventStyles: Record<string, string> = {
  APPLICATION_SUCCESS: "border-emerald-200 bg-emerald-50",
  NEEDS_HUMAN: "border-amber-200 bg-amber-50",
  ERROR: "border-red-200 bg-red-50",
  JOB_DISCOVERED: "border-blue-200 bg-blue-50",
  BROWSER_ACTION: "border-slate-200 bg-white",
  LLM_CALL: "border-slate-200 bg-slate-50 opacity-80",
};

function EventIcon({ event }: { event: string }) {
  if (event === "APPLICATION_SUCCESS") return <CheckCircle2 className="h-4 w-4 text-emerald-600" />;
  if (event === "NEEDS_HUMAN") return <AlertTriangle className="h-4 w-4 text-amber-600" />;
  if (event === "BROWSER_ACTION") return <Zap className="h-4 w-4 text-slate-600" />;
  return <Info className="h-4 w-4 text-blue-600" />;
}

function eventText(event: WebSocketEvent) {
  switch (event.event) {
    case "BROWSER_ACTION": {
      const confidence = typeof event.confidence === "number" ? `${Math.round(event.confidence * 100)}%` : "--";
      return `Filled ${event.field} on application workflow (confidence: ${confidence})`;
    }
    case "JOB_DISCOVERED":
      return `Found: ${event.title} at ${event.company} - score ${event.score}/100`;
    case "APPLICATION_SUCCESS":
      return `Ready to review: ${event.role} at ${event.company}`;
    case "NEEDS_HUMAN":
      return `Needs your input: ${event.company} - ${event.field_name}`;
    case "LLM_CALL":
      return `${event.purpose} in progress`;
    case "ERROR":
      return `Error: ${event.message}`;
    default:
      return event.event.replaceAll("_", " ");
  }
}

export function LiveFeed({
  events,
  onClear,
}: {
  events: WebSocketEvent[];
  onClear?: () => void;
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white">
      <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
        <div>
          <h2 className="text-sm font-semibold text-slate-900">Live Activity</h2>
          <p className="text-xs text-slate-500">Newest events first, last 50 retained.</p>
        </div>
        {onClear && (
          <Button variant="ghost" size="sm" onClick={onClear}>
            Clear feed
          </Button>
        )}
      </div>
      <div className="max-h-[520px] divide-y divide-slate-100 overflow-auto">
        {events.length === 0 && (
          <div className="px-4 py-10 text-center text-sm text-slate-500">
            No live events yet.
          </div>
        )}
        {events.map((event, index) => (
          <div
            key={`${event.event}-${event.timestamp}-${index}`}
            className={cn("flex items-start gap-3 border-l-4 px-4 py-3", eventStyles[event.event])}
          >
            <EventIcon event={event.event} />
            <div className="min-w-0 flex-1">
              <p className="text-sm text-slate-800">{eventText(event)}</p>
              <p className="mt-1 text-xs text-slate-500">{formatRelativeTime(event.timestamp)}</p>
            </div>
            {event.event === "NEEDS_HUMAN" && (
              <Link href={`/applications/${event.application_id}/review`}>
                <Button variant="outline" size="sm">Respond</Button>
              </Link>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
