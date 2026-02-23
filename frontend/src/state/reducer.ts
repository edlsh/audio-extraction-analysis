/**
 * Pure reducer function for applying events to state.
 *
 * Direct port of apply_event() from src/ui/tui/state.py
 */

import type { Event, Stage, LogLevel } from "../protocol/events";
import type { AppState, LogEntry, LogItem, TruncationMarker } from "../protocol/state";

/** Maximum number of log entries to keep */
const MAX_LOG_ENTRIES = 2000;

/**
 * Append item to ring buffer with middle truncation.
 *
 * Maintains a ring buffer by keeping the first 25% and last 75% of entries
 * when the buffer exceeds maxSize, with a truncation marker in between.
 */
function appendToRing<T>(items: T[], item: T, maxSize: number): (T | TruncationMarker)[] {
  const result = [...items, item];

  if (result.length > maxSize) {
    // Keep first 25% and last 75% with truncation marker
    const keepHead = Math.floor(maxSize / 4);
    const keepTail = maxSize - keepHead - 1; // Reserve 1 slot for marker

    const marker: TruncationMarker = {
      truncated: true,
      count: result.length - maxSize + 1,
    };

    return [
      ...result.slice(0, keepHead),
      marker,
      ...result.slice(-keepTail),
    ] as (T | TruncationMarker)[];
  }

  return result as (T | TruncationMarker)[];
}

/**
 * Convert event timestamp to number (seconds since epoch).
 */
function coerceTimestamp(ts: number | string | unknown): number {
  if (typeof ts === "number") {
    return ts;
  }

  if (typeof ts === "string") {
    try {
      return new Date(ts).getTime() / 1000;
    } catch {
      return Date.now() / 1000;
    }
  }

  return Date.now() / 1000;
}

/**
 * Pure reducer function: (state, event) -> new_state.
 *
 * Applies an event to the current state and returns a new state instance.
 * NEVER mutates the input state.
 */
export function applyEvent(state: AppState, event: Event): AppState {
  const eventType = event.type;
  const eventStage = event.stage as Stage | undefined;
  const eventData = event.data as Record<string, unknown>;

  switch (eventType) {
    case "stage_start": {
      // data: { description: string, total: number }
      const total = (eventData.total as number) ?? 100;
      const description = (eventData.description as string) ?? "";

      return {
        ...state,
        currentStage: eventStage ?? null,
        currentMessage: description,
        stageTotals: {
          ...state.stageTotals,
          ...(eventStage ? { [eventStage]: total } : {}),
        },
        stageCompleted: {
          ...state.stageCompleted,
          ...(eventStage ? { [eventStage]: 0 } : {}),
        },
        stageStatus: {
          ...state.stageStatus,
          ...(eventStage ? { [eventStage]: "running" } : {}),
        },
        stageStartedAt: {
          ...state.stageStartedAt,
          ...(eventStage ? { [eventStage]: Date.now() / 1000 } : {}),
        },
        stageMessages: {
          ...state.stageMessages,
          ...(eventStage ? { [eventStage]: description } : {}),
        },
        isRunning: true,
        canCancel: true,
      };
    }

    case "stage_progress": {
      // data: { completed: number, total: number, message?: string }
      const completed = (eventData.completed as number) ?? 0;
      const total =
        (eventData.total as number) ??
        (eventStage ? state.stageTotals[eventStage] : undefined) ??
        100;
      const message = (eventData.message as string) ?? state.currentMessage;

      // Update totals if provided (handles dynamic total updates)
      const newTotals =
        eventStage && total !== state.stageTotals[eventStage]
          ? { ...state.stageTotals, [eventStage]: total }
          : state.stageTotals;

      return {
        ...state,
        stageCompleted: {
          ...state.stageCompleted,
          ...(eventStage ? { [eventStage]: completed } : {}),
        },
        stageTotals: newTotals,
        stageStatus: {
          ...state.stageStatus,
          ...(eventStage ? { [eventStage]: "running" } : {}),
        },
        stageMessages: {
          ...state.stageMessages,
          ...(eventStage ? { [eventStage]: message } : {}),
        },
        currentMessage: message,
        currentProgress: total > 0 ? (completed / total) * 100 : 0,
      };
    }

    case "stage_end": {
      // data: { duration: number, status: string }
      const status = (eventData.status as string) ?? "complete";
      const duration = (eventData.duration as number) ?? 0;

      return {
        ...state,
        stageDurations: {
          ...state.stageDurations,
          ...(eventStage ? { [eventStage]: duration } : {}),
        },
        stageStatus: {
          ...state.stageStatus,
          ...(eventStage ? { [eventStage]: status as "complete" | "error" } : {}),
        },
        currentStage: null,
        currentProgress: 0,
      };
    }

    case "artifact": {
      // data: { kind: string, path: string }
      return {
        ...state,
        artifacts: [
          ...state.artifacts,
          {
            kind: (eventData.kind as string) ?? "unknown",
            path: (eventData.path as string) ?? "",
          },
        ],
      };
    }

    case "log": {
      // data: { message: string, level: string, logger?: string }
      const logEntry: LogEntry = {
        type: "log",
        timestamp: coerceTimestamp(event.ts),
        level: (eventData.level as LogLevel) ?? "INFO",
        message: (eventData.message as string) ?? "",
        logger: (eventData.logger as string) ?? "",
      };

      return {
        ...state,
        logs: appendToRing(state.logs, logEntry, MAX_LOG_ENTRIES),
      };
    }

    case "warning": {
      // data: { message: string, level: string, logger?: string }
      const logEntry: LogEntry = {
        type: "warning",
        timestamp: coerceTimestamp(event.ts),
        level: "WARNING",
        message: (eventData.message as string) ?? "",
        logger: (eventData.logger as string) ?? "",
      };

      return {
        ...state,
        logs: appendToRing(state.logs, logEntry, MAX_LOG_ENTRIES),
      };
    }

    case "error": {
      // data: { message: string, level: string, logger?: string }
      const errorMsg = (eventData.message as string) ?? "Unknown error";
      const logEntry: LogEntry = {
        type: "error",
        timestamp: coerceTimestamp(event.ts),
        level: "ERROR",
        message: errorMsg,
        logger: (eventData.logger as string) ?? "",
      };

      const newStageStatus = eventStage
        ? { ...state.stageStatus, [eventStage]: "error" as const }
        : state.stageStatus;

      return {
        ...state,
        errors: [...state.errors, errorMsg],
        stageStatus: newStageStatus,
        logs: appendToRing(state.logs, logEntry, MAX_LOG_ENTRIES),
      };
    }

    case "summary": {
      // data: { metrics?: object, provider?: string, output_dir?: string }
      return {
        ...state,
        summary: eventData,
        isRunning: false,
        canCancel: false,
      };
    }

    case "cancelled": {
      // data: { reason: string }
      const reason = (eventData.reason as string) ?? "User interrupt";

      return {
        ...state,
        isRunning: false,
        canCancel: false,
        currentMessage: `Cancelled: ${reason}`,
      };
    }

    default:
      // Unknown event type; preserve state
      return state;
  }
}

/**
 * Apply a batch of events to state.
 */
export function applyEvents(state: AppState, events: Event[]): AppState {
  return events.reduce((s, e) => applyEvent(s, e), state);
}
