/**
 * Application state types.
 *
 * Mirrors the Python AppState from src/ui/tui/state.py
 */

import type { LogLevel, Stage, StageStatus } from "./events";

/** Log entry in the UI */
export interface LogEntry {
  type: "log" | "warning" | "error";
  timestamp: number;
  level: LogLevel;
  message: string;
  logger: string;
}

/** Truncation marker for ring buffer */
export interface TruncationMarker {
  truncated: true;
  count: number;
}

/** Union type for log entries */
export type LogItem = LogEntry | TruncationMarker;

/** Artifact produced by the pipeline */
export interface Artifact {
  kind: string;
  path: string;
}

/** Summary data from completed pipeline */
export interface PipelineSummary {
  metrics?: Record<string, unknown>;
  provider?: string;
  output_dir?: string;
  [key: string]: unknown;
}

/** Application state for the TUI */
export interface AppState {
  // Configuration
  inputPath: string | null;
  outputDir: string | null;
  quality: string;
  language: string;
  provider: string;
  analysisStyle: string;

  // Run state
  isRunning: boolean;
  canCancel: boolean;
  currentStage: Stage | null;
  currentProgress: number;
  currentMessage: string;

  // Stage tracking
  stageTotals: Record<Stage, number>;
  stageCompleted: Record<Stage, number>;
  stageDurations: Record<Stage, number>;
  stageStatus: Record<Stage, StageStatus>;
  stageStartedAt: Record<Stage, number>;
  stageMessages: Record<Stage, string>;

  // Results
  artifacts: Artifact[];
  errors: string[];
  logs: LogItem[];
  summary: PipelineSummary;

  // Run ID for event tracking
  runId: string | null;
  pendingRunConfig: Record<string, unknown> | null;
}

/** Create initial/default state */
export function createInitialState(): AppState {
  return {
    // Configuration
    inputPath: null,
    outputDir: null,
    quality: "speech",
    language: "en",
    provider: "auto",
    analysisStyle: "concise",

    // Run state
    isRunning: false,
    canCancel: false,
    currentStage: null,
    currentProgress: 0,
    currentMessage: "",

    // Stage tracking
    stageTotals: {} as Record<Stage, number>,
    stageCompleted: {} as Record<Stage, number>,
    stageDurations: {} as Record<Stage, number>,
    stageStatus: {} as Record<Stage, StageStatus>,
    stageStartedAt: {} as Record<Stage, number>,
    stageMessages: {} as Record<Stage, string>,

    // Results
    artifacts: [],
    errors: [],
    logs: [],
    summary: {},

    // Run ID
    runId: null,
    pendingRunConfig: null,
  };
}

/** Reset run state while preserving configuration */
export function resetRunState(state: AppState): AppState {
  return {
    ...state,
    isRunning: false,
    canCancel: false,
    currentStage: null,
    currentProgress: 0,
    currentMessage: "",
    stageTotals: {} as Record<Stage, number>,
    stageCompleted: {} as Record<Stage, number>,
    stageDurations: {} as Record<Stage, number>,
    stageStatus: {} as Record<Stage, StageStatus>,
    stageStartedAt: {} as Record<Stage, number>,
    stageMessages: {} as Record<Stage, string>,
    artifacts: [],
    errors: [],
    logs: [],
    summary: {},
    runId: null,
    pendingRunConfig: null,
  };
}
