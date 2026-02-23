import { describe, it, expect } from "bun:test";

import type { Event, Stage } from "../protocol/events";
import type { AppState } from "../protocol/state";
import { createInitialState } from "../protocol/state";
import { applyEvent, applyEvents } from "./reducer";

function createEvent(overrides: {
  type: Event["type"];
  stage?: Stage;
  data?: Record<string, unknown>;
  ts?: number;
  run_id?: string;
}): Event {
  const base = {
    ts: overrides.ts ?? Date.now() / 1000,
    run_id: overrides.run_id ?? "test-run-1",
  };

  switch (overrides.type) {
    case "stage_start":
      return {
        ...base,
        type: "stage_start",
        stage: overrides.stage!,
        data: {
          description: "",
          total: 100,
          ...overrides.data,
        },
      };
    case "stage_progress":
      return {
        ...base,
        type: "stage_progress",
        stage: overrides.stage!,
        data: {
          completed: 0,
          total: 100,
          ...overrides.data,
        },
      };
    case "stage_end":
      return {
        ...base,
        type: "stage_end",
        stage: overrides.stage!,
        data: {
          duration: 0,
          status: "complete" as const,
          ...overrides.data,
        },
      };
    case "artifact":
      return {
        ...base,
        type: "artifact",
        data: {
          kind: "audio",
          path: "/tmp/test.mp3",
          ...overrides.data,
        },
      };
    case "log":
      return {
        ...base,
        type: "log",
        data: {
          message: "",
          level: "INFO" as const,
          ...overrides.data,
        },
      };
    case "warning":
      return {
        ...base,
        type: "warning",
        data: {
          message: "",
          level: "WARNING" as const,
          ...overrides.data,
        },
      };
    case "error":
      return {
        ...base,
        type: "error",
        stage: overrides.stage,
        data: {
          message: "",
          level: "ERROR" as const,
          ...overrides.data,
        },
      };
    case "summary":
      return {
        ...base,
        type: "summary",
        data: {
          ...overrides.data,
        },
      };
    case "cancelled":
      return {
        ...base,
        type: "cancelled",
        data: {
          reason: "",
          ...overrides.data,
        },
      };
    default:
      // For unknown types, return a log event (tests handle this)
      return {
        ...base,
        type: overrides.type as "log",
        data: {
          message: "",
          level: "INFO" as const,
        },
      };
  }
}

describe("applyEvent", () => {
  describe("stage_start", () => {
    it("sets currentStage and marks as running", () => {
      const state = createInitialState();
      const event = createEvent({
        type: "stage_start",
        stage: "extract" as Stage,
        data: { description: "Extracting audio", total: 100 },
      });

      const newState = applyEvent(state, event);

      expect(newState.currentStage).toBe("extract");
      expect(newState.isRunning).toBe(true);
      expect(newState.canCancel).toBe(true);
      expect(newState.stageTotals.extract).toBe(100);
      expect(newState.stageStatus.extract).toBe("running");
      expect(newState.stageMessages.extract).toBe("Extracting audio");
    });

    it("uses defaults when data is missing", () => {
      const state = createInitialState();
      const event = createEvent({
        type: "stage_start",
        stage: "transcribe" as Stage,
        data: {},
      });

      const newState = applyEvent(state, event);

      expect(newState.stageTotals.transcribe).toBe(100);
      expect(newState.stageMessages.transcribe).toBe("");
    });
  });

  describe("stage_progress", () => {
    it("updates progress and message", () => {
      let state = createInitialState();
      state = applyEvent(state, createEvent({
        type: "stage_start",
        stage: "extract" as Stage,
        data: { total: 100 },
      }));

      const event = createEvent({
        type: "stage_progress",
        stage: "extract" as Stage,
        data: { completed: 50, total: 100, message: "50% done" },
      });

      const newState = applyEvent(state, event);

      expect(newState.stageCompleted.extract).toBe(50);
      expect(newState.currentProgress).toBe(50);
      expect(newState.currentMessage).toBe("50% done");
    });

    it("handles dynamic total updates", () => {
      let state = createInitialState();
      state = applyEvent(state, createEvent({
        type: "stage_start",
        stage: "transcribe" as Stage,
        data: { total: 50 },
      }));

      const event = createEvent({
        type: "stage_progress",
        stage: "transcribe" as Stage,
        data: { completed: 10, total: 100 },
      });

      const newState = applyEvent(state, event);

      expect(newState.stageTotals.transcribe).toBe(100);
      expect(newState.currentProgress).toBe(10);
    });
  });

  describe("stage_end", () => {
    it("marks stage complete and clears current progress", () => {
      let state = createInitialState();
      state = applyEvent(state, createEvent({
        type: "stage_start",
        stage: "extract" as Stage,
        data: { total: 100 },
      }));
      state = applyEvent(state, createEvent({
        type: "stage_progress",
        stage: "extract" as Stage,
        data: { completed: 100, total: 100 },
      }));

      const event = createEvent({
        type: "stage_end",
        stage: "extract" as Stage,
        data: { duration: 5.5, status: "complete" },
      });

      const newState = applyEvent(state, event);

      expect(newState.currentStage).toBe(null);
      expect(newState.currentProgress).toBe(0);
      expect(newState.stageDurations.extract).toBe(5.5);
      expect(newState.stageStatus.extract).toBe("complete");
    });
  });

  describe("artifact", () => {
    it("adds artifact to list", () => {
      const state = createInitialState();
      const event = createEvent({
        type: "artifact",
        data: { kind: "audio", path: "/tmp/output.mp3" },
      });

      const newState = applyEvent(state, event);

      expect(newState.artifacts).toHaveLength(1);
      expect(newState.artifacts[0]).toEqual({
        kind: "audio",
        path: "/tmp/output.mp3",
      });
    });

    it("uses data.type when kind is missing", () => {
      const state = createInitialState();
      const event = createEvent({
        type: "artifact",
        data: { type: "transcript", path: "/tmp/output.txt" },
      });
      delete (event.data as Record<string, unknown>).kind;

      const newState = applyEvent(state, event);

      expect(newState.artifacts).toHaveLength(1);
      expect(newState.artifacts[0]).toEqual({
        kind: "transcript",
        path: "/tmp/output.txt",
      });
    });
  });

  describe("log events", () => {
    it("appends log entry", () => {
      const state = createInitialState();
      const event = createEvent({
        type: "log",
        data: { message: "Processing...", level: "INFO", logger: "pipeline" },
      });

      const newState = applyEvent(state, event);

      expect(newState.logs).toHaveLength(1);
      const log = newState.logs[0];
      expect("truncated" in log).toBe(false);
      if (!("truncated" in log)) {
        expect(log.message).toBe("Processing...");
        expect(log.level).toBe("INFO");
      }
    });

    it("appends warning entry", () => {
      const state = createInitialState();
      const event = createEvent({
        type: "warning",
        data: { message: "Low quality audio" },
      });

      const newState = applyEvent(state, event);

      expect(newState.logs).toHaveLength(1);
      const log = newState.logs[0];
      if (!("truncated" in log)) {
        expect(log.type).toBe("warning");
        expect(log.level).toBe("WARNING");
      }
    });
  });

  describe("error", () => {
    it("adds to errors list and logs", () => {
      const state = createInitialState();
      const event = createEvent({
        type: "error",
        stage: "transcribe" as Stage,
        data: { message: "API timeout" },
      });

      const newState = applyEvent(state, event);

      expect(newState.errors).toContain("API timeout");
      expect(newState.stageStatus.transcribe).toBe("error");
      expect(newState.logs).toHaveLength(1);
    });
  });

  describe("summary", () => {
    it("sets summary and stops running", () => {
      let state = createInitialState();
      state = { ...state, isRunning: true, canCancel: true };

      const event = createEvent({
        type: "summary",
        data: {
          metrics: { total_time: 30 },
          provider: "deepgram",
          output_dir: "/tmp/output",
        },
      });

      const newState = applyEvent(state, event);

      expect(newState.isRunning).toBe(false);
      expect(newState.canCancel).toBe(false);
      expect(newState.summary.provider).toBe("deepgram");
      expect(newState.summary.output_dir).toBe("/tmp/output");
    });
  });

  describe("cancelled", () => {
    it("stops running and sets message", () => {
      let state = createInitialState();
      state = { ...state, isRunning: true, canCancel: true };

      const event = createEvent({
        type: "cancelled",
        data: { reason: "User requested" },
      });

      const newState = applyEvent(state, event);

      expect(newState.isRunning).toBe(false);
      expect(newState.canCancel).toBe(false);
      expect(newState.currentMessage).toContain("User requested");
    });
  });

  describe("unknown event", () => {
    it("preserves state unchanged", () => {
      const state = createInitialState();
      const event = createEvent({
        type: "unknown_type" as Event["type"],
      });

      const newState = applyEvent(state, event);

      expect(newState).toEqual(state);
    });
  });
});

describe("applyEvents", () => {
  it("applies multiple events in sequence", () => {
    const state = createInitialState();
    const events: Event[] = [
      createEvent({
        type: "stage_start",
        stage: "extract" as Stage,
        data: { total: 100 },
      }),
      createEvent({
        type: "stage_progress",
        stage: "extract" as Stage,
        data: { completed: 50, total: 100 },
      }),
      createEvent({
        type: "stage_end",
        stage: "extract" as Stage,
        data: { duration: 2.5, status: "complete" },
      }),
    ];

    const newState = applyEvents(state, events);

    expect(newState.stageStatus.extract).toBe("complete");
    expect(newState.stageDurations.extract).toBe(2.5);
    expect(newState.currentStage).toBe(null);
  });
});

describe("ring buffer truncation", () => {
  it("truncates logs when exceeding max size", () => {
    let state = createInitialState();

    for (let i = 0; i < 2100; i++) {
      state = applyEvent(state, createEvent({
        type: "log",
        data: { message: `Log ${i}`, level: "INFO" },
      }));
    }

    expect(state.logs.length).toBeLessThanOrEqual(2000);

    const hasMarker = state.logs.some((item) => "truncated" in item);
    expect(hasMarker).toBe(true);
  });
});
