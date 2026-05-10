import { cn } from "../../lib/utils";
import { useAgentStore } from "../../store/agentStore";

const colors = {
  idle: "bg-slate-400",
  running: "bg-emerald-500",
  paused: "bg-amber-500",
  error: "bg-red-500",
};

export function AgentStatusBadge({ compact = false }: { compact?: boolean }) {
  const { status, currentCompany } = useAgentStore();
  const text =
    status === "running" && currentCompany
      ? `Running - ${currentCompany}`
      : status.charAt(0).toUpperCase() + status.slice(1);

  return (
    <div className="flex items-center gap-2 text-sm text-slate-700">
      <span
        className={cn(
          "h-2.5 w-2.5 rounded-full",
          colors[status],
          status === "running" && "animate-pulse",
        )}
      />
      {!compact && <span className="truncate">{text}</span>}
    </div>
  );
}
