import { ApplicationStatus } from "../../types/api";
import { Badge } from "../ui/badge";

const statusColors: Record<string, "slate" | "green" | "yellow" | "red" | "blue" | "purple"> = {
  [ApplicationStatus.Queued]: "slate",
  [ApplicationStatus.AgentProcessing]: "blue",
  [ApplicationStatus.NeedsHuman]: "yellow",
  [ApplicationStatus.ReadyToSubmit]: "green",
  [ApplicationStatus.Submitted]: "green",
  [ApplicationStatus.Shortlisted]: "purple",
  [ApplicationStatus.Interview]: "purple",
  [ApplicationStatus.Offer]: "green",
  [ApplicationStatus.Rejected]: "red",
  [ApplicationStatus.Ghosted]: "slate",
  [ApplicationStatus.Interrupted]: "yellow",
  [ApplicationStatus.Failed]: "red",
};

export function ApplicationStatusBadge({ status }: { status?: string | null }) {
  const label = (status ?? "unknown").replaceAll("_", " ");
  return <Badge variant={statusColors[status ?? ""] ?? "slate"}>{label}</Badge>;
}
