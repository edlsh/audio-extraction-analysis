/**
 * Event types for the audio-extraction-analysis TUI.
 *
 * These types mirror the Python Event model from src/models/events.py
 * and are used for JSON-RPC notifications from backend to frontend.
 */

/** Pipeline stages */
export type Stage =
  | "download"
  | "extract"
  | "transcribe"
  | "analyze";

/** Event types emitted by the backend */
export type EventType =
  | "stage_start"
  | "stage_progress"
  | "stage_end"
  | "artifact"
  | "log"
  | "warning"
  | "error"
  | "summary"
  | "cancelled";

/** Stage status values */
export type StageStatus = "pending" | "running" | "complete" | "error" | "skipped";

/** Log levels */
export type LogLevel = "DEBUG" | "INFO" | "WARNING" | "ERROR";

/** Base event structure */
export interface BaseEvent {
  type: EventType;
  stage?: Stage;
  data: Record<string, unknown>;
  ts: number | string;
  run_id: string;
}

/** Stage start event data */
export interface StageStartData {
  description: string;
  total: number;
  [key: string]: unknown;
}

/** Stage progress event data */
export interface StageProgressData {
  completed: number;
  total: number;
  message?: string;
  [key: string]: unknown;
}

/** Stage end event data */
export interface StageEndData {
  duration: number;
  status: StageStatus;
  [key: string]: unknown;
}

/** Artifact event data */
export interface ArtifactData {
  kind?: string;
  type?: string;
  path: string;
  [key: string]: unknown;
}

/** Log event data */
export interface LogData {
  message: string;
  level: LogLevel;
  logger?: string;
  [key: string]: unknown;
}

/** Summary event data */
export interface SummaryData {
  metrics?: Record<string, unknown>;
  provider?: string;
  output_dir?: string;
  [key: string]: unknown;
}

/** Cancelled event data */
export interface CancelledData {
  reason?: string;
  [key: string]: unknown;
}

/** Typed event variants */
export interface StageStartEvent extends BaseEvent {
  type: "stage_start";
  stage: Stage;
  data: StageStartData;
}

export interface StageProgressEvent extends BaseEvent {
  type: "stage_progress";
  stage: Stage;
  data: StageProgressData;
}

export interface StageEndEvent extends BaseEvent {
  type: "stage_end";
  stage: Stage;
  data: StageEndData;
}

export interface ArtifactEvent extends BaseEvent {
  type: "artifact";
  data: ArtifactData;
}

export interface LogEvent extends BaseEvent {
  type: "log";
  data: LogData;
}

export interface WarningEvent extends BaseEvent {
  type: "warning";
  data: LogData;
}

export interface ErrorEvent extends BaseEvent {
  type: "error";
  data: LogData;
}

export interface SummaryEvent extends BaseEvent {
  type: "summary";
  data: SummaryData;
}

export interface CancelledEvent extends BaseEvent {
  type: "cancelled";
  data: CancelledData;
}

/** Union of all event types */
export type Event =
  | StageStartEvent
  | StageProgressEvent
  | StageEndEvent
  | ArtifactEvent
  | LogEvent
  | WarningEvent
  | ErrorEvent
  | SummaryEvent
  | CancelledEvent;

/** JSON-RPC 2.0 event notification */
export interface EventNotification {
  jsonrpc: "2.0";
  method: "event";
  params: Event;
}
