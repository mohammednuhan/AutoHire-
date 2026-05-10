import { create } from "zustand";
import type {
  MorningSummaryEvent,
  NeedsHumanEvent,
  ErrorEvent,
  WebSocketEvent,
} from "../types/api";

export type AgentStatus = "idle" | "running" | "paused" | "error";

interface AgentStore {
  status: AgentStatus;
  currentCompany: string | null;
  currentField: string | null;
  liveEvents: WebSocketEvent[];
  needsHumanQueue: NeedsHumanEvent[];
  errorQueue: ErrorEvent[];
  morningDigest: MorningSummaryEvent | null;
  setStatus: (status: AgentStatus) => void;
  addEvent: (event: WebSocketEvent) => void;
  clearEvents: () => void;
  addNeedsHuman: (event: NeedsHumanEvent) => void;
  addError: (event: ErrorEvent) => void;
  dismissError: (index: number) => void;
  resolveNeedsHuman: (traceId: string) => void;
  applyAgentStatus: (event: Record<string, any>) => void;
  setMorningDigest: (event: MorningSummaryEvent) => void;
}

export const useAgentStore = create<AgentStore>((set) => ({
  status: "idle",
  currentCompany: null,
  currentField: null,
  liveEvents: [],
  needsHumanQueue: [],
  errorQueue: [],
  morningDigest: null,

  setStatus: (status) => set({ status }),

  addEvent: (event) =>
    set((state) => ({
      liveEvents: [event, ...state.liveEvents].slice(0, 50),
    })),

  clearEvents: () => set({ liveEvents: [] }),

  addNeedsHuman: (event) =>
    set((state) => ({
      status: "paused",
      currentCompany: event.company ?? state.currentCompany,
      currentField: event.field_name ?? state.currentField,
      needsHumanQueue: [
        event,
        ...state.needsHumanQueue.filter((item) => item.trace_id !== event.trace_id),
      ],
    })),

  addError: (event) =>
    set((state) => ({
      status: "error",
      errorQueue: [event, ...state.errorQueue].slice(0, 10),
    })),

  dismissError: (index) =>
    set((state) => ({
      errorQueue: state.errorQueue.filter((_item, itemIndex) => itemIndex !== index),
    })),

  resolveNeedsHuman: (traceId) =>
    set((state) => ({
      needsHumanQueue: state.needsHumanQueue.filter((item) => item.trace_id !== traceId),
    })),

  applyAgentStatus: (event) => {
    const statusPayload = typeof event.status === "object" ? event.status : event;
    set({
      status: (statusPayload.status as AgentStatus) ?? "idle",
      currentCompany: (statusPayload.current_company ??
        statusPayload.currentCompany ??
        null) as string | null,
      currentField: (statusPayload.current_field ??
        statusPayload.currentField ??
        null) as string | null,
    });
  },

  setMorningDigest: (event) => set({ morningDigest: event }),
}));
