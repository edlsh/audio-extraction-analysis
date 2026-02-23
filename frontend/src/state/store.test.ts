import { describe, it, expect, beforeEach } from "bun:test";

import type { Event, Stage } from "../protocol/events";
import { useStore } from "./store";

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
        data: { description: "", total: 100, ...overrides.data },
      };
    case "stage_progress":
      return {
        ...base,
        type: "stage_progress",
        stage: overrides.stage!,
        data: { completed: 0, total: 100, ...overrides.data },
      };
    case "stage_end":
      return {
        ...base,
        type: "stage_end",
        stage: overrides.stage!,
        data: { duration: 0, status: "complete" as const, ...overrides.data },
      };
    case "artifact":
      return {
        ...base,
        type: "artifact",
        data: { kind: "audio", path: "/tmp/test.mp3", ...overrides.data },
      };
    case "log":
      return {
        ...base,
        type: "log",
        data: { message: "", level: "INFO" as const, ...overrides.data },
      };
    default:
      return {
        ...base,
        type: "log",
        data: { message: "", level: "INFO" as const },
      };
  }
}

describe("useStore", () => {
  beforeEach(() => {
    useStore.setState(useStore.getInitialState());
  });

  describe("initial state", () => {
    it("has correct defaults", () => {
      const state = useStore.getState();

      expect(state.inputPath).toBe(null);
      expect(state.outputDir).toBe(null);
      expect(state.quality).toBe("speech");
      expect(state.language).toBe("en");
      expect(state.provider).toBe("auto");
      expect(state.analysisStyle).toBe("concise");
      expect(state.isRunning).toBe(false);
      expect(state.artifacts).toEqual([]);
      expect(state.logs).toEqual([]);
    });
  });

  describe("setters", () => {
    it("setInputPath updates inputPath", () => {
      useStore.getState().setInputPath("/path/to/video.mp4");
      expect(useStore.getState().inputPath).toBe("/path/to/video.mp4");
    });

    it("setInputPath handles null", () => {
      useStore.getState().setInputPath("/path/to/video.mp4");
      useStore.getState().setInputPath(null);
      expect(useStore.getState().inputPath).toBe(null);
    });

    it("setOutputDir updates outputDir", () => {
      useStore.getState().setOutputDir("/tmp/output");
      expect(useStore.getState().outputDir).toBe("/tmp/output");
    });

    it("setQuality updates quality", () => {
      useStore.getState().setQuality("high");
      expect(useStore.getState().quality).toBe("high");
    });

    it("setLanguage updates language", () => {
      useStore.getState().setLanguage("es");
      expect(useStore.getState().language).toBe("es");
    });

    it("setProvider updates provider", () => {
      useStore.getState().setProvider("whisper");
      expect(useStore.getState().provider).toBe("whisper");
    });

    it("setAnalysisStyle updates analysisStyle", () => {
      useStore.getState().setAnalysisStyle("full");
      expect(useStore.getState().analysisStyle).toBe("full");
    });

    it("setPendingRunConfig sets config", () => {
      useStore.getState().setPendingRunConfig({ url: "https://example.com" });
      expect(useStore.getState().pendingRunConfig).toEqual({ url: "https://example.com" });
    });

    it("setPendingRunConfig clears with null", () => {
      useStore.getState().setPendingRunConfig({ url: "https://example.com" });
      useStore.getState().setPendingRunConfig(null);
      expect(useStore.getState().pendingRunConfig).toBe(null);
    });
  });

  describe("applyEvent", () => {
    it("applies stage_start event", () => {
      const event = createEvent({
        type: "stage_start",
        stage: "extract" as Stage,
        data: { description: "Extracting", total: 100 },
      });

      useStore.getState().applyEvent(event);

      const state = useStore.getState();
      expect(state.currentStage).toBe("extract");
      expect(state.isRunning).toBe(true);
      expect(state.stageStatus.extract).toBe("running");
    });

    it("applies multiple events correctly", () => {
      useStore.getState().applyEvent(createEvent({
        type: "stage_start",
        stage: "extract" as Stage,
        data: { total: 100 },
      }));

      useStore.getState().applyEvent(createEvent({
        type: "stage_progress",
        stage: "extract" as Stage,
        data: { completed: 50, total: 100 },
      }));

      expect(useStore.getState().currentProgress).toBe(50);
    });
  });

  describe("applyEvents", () => {
    it("applies batch of events", () => {
      const events: Event[] = [
        createEvent({
          type: "stage_start",
          stage: "extract" as Stage,
          data: { total: 100 },
        }),
        createEvent({
          type: "stage_progress",
          stage: "extract" as Stage,
          data: { completed: 100, total: 100 },
        }),
        createEvent({
          type: "stage_end",
          stage: "extract" as Stage,
          data: { duration: 3.0, status: "complete" },
        }),
      ];

      useStore.getState().applyEvents(events);

      const state = useStore.getState();
      expect(state.stageStatus.extract).toBe("complete");
      expect(state.stageDurations.extract).toBe(3.0);
      expect(state.currentStage).toBe(null);
    });
  });

  describe("reset", () => {
    it("resets run state but preserves configuration", () => {
      const state = useStore.getState();
      state.setInputPath("/path/to/file.mp4");
      state.setQuality("high");
      state.applyEvent(createEvent({
        type: "stage_start",
        stage: "extract" as Stage,
        data: { total: 100 },
      }));
      state.applyEvent(createEvent({
        type: "artifact",
        data: { kind: "audio", path: "/tmp/out.mp3" },
      }));

      useStore.getState().reset();

      const resetState = useStore.getState();
      expect(resetState.inputPath).toBe("/path/to/file.mp4");
      expect(resetState.quality).toBe("high");
      expect(resetState.isRunning).toBe(false);
      expect(resetState.artifacts).toEqual([]);
      expect(resetState.currentStage).toBe(null);
    });
  });
});
