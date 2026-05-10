"use client";

import { Square } from "lucide-react";
import { toast } from "sonner";
import { api } from "../../lib/api";
import { useAgentStore } from "../../store/agentStore";
import { Button } from "../ui/button";

export function StopButton() {
  const status = useAgentStore((state) => state.status);
  if (status !== "running") return null;

  return (
    <Button
      variant="danger"
      className="w-full"
      onClick={async () => {
        try {
          await api.stopAgent();
          toast.success("Stop requested");
        } catch (error) {
          toast.error(error instanceof Error ? error.message : "Could not stop agent");
        }
      }}
    >
      <Square className="h-4 w-4" />
      STOP
    </Button>
  );
}
