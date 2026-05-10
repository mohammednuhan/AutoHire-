import { Badge } from "../ui/badge";

export function ConfidenceBadge({ confidence }: { confidence?: number | null }) {
  if (typeof confidence !== "number") return <Badge>--</Badge>;
  const percent = confidence <= 1 ? Math.round(confidence * 100) : Math.round(confidence);
  const variant = percent >= 80 ? "green" : percent >= 60 ? "yellow" : "red";
  return <Badge variant={variant}>{percent}%</Badge>;
}
