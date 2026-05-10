import { Badge } from "../ui/badge";

export function ScoreBadge({ score }: { score?: number | null }) {
  if (typeof score !== "number") return <Badge>--</Badge>;
  const variant = score >= 80 ? "green" : score >= 60 ? "yellow" : "slate";
  return <Badge variant={variant}>{score}/100</Badge>;
}
