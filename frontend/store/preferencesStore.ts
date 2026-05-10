import { create } from "zustand";
import type { UserPreferences } from "../types/api";

type PreferencesState = {
  preferences: Partial<UserPreferences>;
  setPreference: <K extends keyof UserPreferences>(key: K, value: UserPreferences[K]) => void;
  setPreferences: (preferences: Partial<UserPreferences>) => void;
  addTag: (key: "target_roles" | "preferred_locations" | "dream_companies" | "blacklisted_companies", value: string) => void;
  removeTag: (key: "target_roles" | "preferred_locations" | "dream_companies" | "blacklisted_companies", value: string) => void;
};

export const usePreferencesStore = create<PreferencesState>((set) => ({
  preferences: {
    target_roles: [],
    preferred_locations: [],
    work_type: "any",
    score_threshold: 70,
    max_apps_per_day: 10,
    dream_companies: [],
    blacklisted_companies: [],
    enabled_boards: ["wellfound", "internshala"],
  },

  setPreference: (key, value) =>
    set((state) => ({ preferences: { ...state.preferences, [key]: value } })),

  setPreferences: (preferences) =>
    set((state) => ({ preferences: { ...state.preferences, ...preferences } })),

  addTag: (key, value) =>
    set((state) => {
      const clean = value.trim();
      if (!clean) return state;
      const existing = state.preferences[key] ?? [];
      if (existing.some((item) => item.toLowerCase() === clean.toLowerCase())) return state;
      return { preferences: { ...state.preferences, [key]: [...existing, clean] } };
    }),

  removeTag: (key, value) =>
    set((state) => ({
      preferences: {
        ...state.preferences,
        [key]: (state.preferences[key] ?? []).filter((item) => item !== value),
      },
    })),
}));
