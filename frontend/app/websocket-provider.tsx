"use client";

import { useEffect } from "react";
import type { ReactNode } from "react";
import { toast } from "sonner";
import { errorCopy } from "../lib/errors";
import { useAgentStore } from "../store/agentStore";
import { wsClient } from "../lib/websocket";
import type { WebSocketEvent } from "../types/api";

export function WebSocketProvider({ children }: { children: ReactNode }) {
  useEffect(() => {
    const store = useAgentStore.getState();
    const unsubscribeWildcard = wsClient.on("*", (event: WebSocketEvent) => {
      store.addEvent(event);
    });
    const unsubscribeStatus = wsClient.on("AGENT_STATUS", (event) => {
      useAgentStore.getState().applyAgentStatus(event);
    });
    const unsubscribeNeedsHuman = wsClient.on("NEEDS_HUMAN", (event) => {
      useAgentStore.getState().addNeedsHuman(event);
    });
    const unsubscribeMorningDigest = wsClient.on("MORNING_SUMMARY", (event) => {
      useAgentStore.getState().setMorningDigest(event);
    });
    const unsubscribeError = wsClient.on("ERROR", (event) => {
      useAgentStore.getState().addError(event);
      const copy = errorCopy(event.error_code, event.message);
      toast.error(copy.message, { description: copy.action, duration: 5000 });
    });

    wsClient.connect();

    return () => {
      unsubscribeWildcard();
      unsubscribeStatus();
      unsubscribeNeedsHuman();
      unsubscribeMorningDigest();
      unsubscribeError();
    };
  }, []);

  return <>{children}</>;
}
