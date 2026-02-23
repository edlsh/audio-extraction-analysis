/**
 * Zustand store for application state.
 */

import { create } from "zustand";

import type { Event } from "../protocol/events";
import type { AppState } from "../protocol/state";
import { createInitialState, resetRunState } from "../protocol/state";
import { applyEvent, applyEvents } from "./reducer";

interface StoreState extends AppState {
  applyEvent: (event: Event) => void;
  applyEvents: (events: Event[]) => void;
  reset: () => void;
  setInputPath: (path: string | null) => void;
  setOutputDir: (dir: string | null) => void;
  setQuality: (quality: string) => void;
  setLanguage: (language: string) => void;
  setProvider: (provider: string) => void;
  setAnalysisStyle: (style: string) => void;
  setPendingRunConfig: (config: Record<string, unknown> | null) => void;
}

export const useStore = create<StoreState>((set) => ({
  ...createInitialState(),

  applyEvent: (event: Event) => {
    set((state) => applyEvent(state, event));
  },

  applyEvents: (events: Event[]) => {
    set((state) => applyEvents(state, events));
  },

  reset: () => {
    set((state) => resetRunState(state));
  },

  setInputPath: (path: string | null) => {
    set({ inputPath: path });
  },

  setOutputDir: (dir: string | null) => {
    set({ outputDir: dir });
  },

  setQuality: (quality: string) => {
    set({ quality });
  },

  setLanguage: (language: string) => {
    set({ language });
  },

  setProvider: (provider: string) => {
    set({ provider });
  },

  setAnalysisStyle: (style: string) => {
    set({ analysisStyle: style });
  },

  setPendingRunConfig: (config: Record<string, unknown> | null) => {
    set({ pendingRunConfig: config });
  },
}));

export type { StoreState };
