/**
 * Run screen - displays live pipeline progress and logs.
 *
 * Port of src/ui/tui/views/run.py to OpenTUI/React.
 *
 * Layout:
 *   +-------------------------------------------+
 *   | Pipeline Timeline (horizontal)            |
 *   | DL   Prep   Ext   Trans   Analyze         |
 *   +-------------------------------------------+
 *   | Focus Card (active stage)                 |
 *   |  Extracting Audio            72%          |
 *   |  [================>         ] ETA: 00:45  |
 *   +-------------------------------------------+
 *   | Completed: Download (2.1s) Prepare (0.5s) |
 *   +-------------------------------------------+
 *   | Logs (scrollable)                         |
 *   |  [filterable scrolling logs]              |
 *   +-------------------------------------------+
 *   | [Cancel] [Open Output]                    |
 *   +-------------------------------------------+
 */

import { useCallback, useEffect, useState, useRef } from "react";
import { useKeyboard } from "@opentui/react";

import { getIpcClient } from "../ipc/client";
import { useStore } from "../state/store";
import { ProgressBoard } from "../components/ProgressBoard";
import { LogPanel } from "../components/LogPanel";
import { CompletionPanel } from "../components/CompletionPanel";

import type { Stage } from "../protocol/events";
import type { PipelineStartParams } from "../protocol/commands";

export interface RunScreenProps {
  /** Input file path */
  inputPath: string | null;
  /** Configuration for the pipeline run */
  config: {
    output_dir: string;
    quality?: string;
    language?: string;
    provider?: string;
    analysis_style?: string;
    url?: string;
  };
  /** Callback when user wants to go back */
  onBack: () => void;
  /** Callback when pipeline completes */
  onComplete?: (outputDir: string) => void;
}

/**
 * Compute ETA for currently running stage.
 */
function computeEta(
  stage: Stage | null,
  completed: number,
  total: number,
  startedAt: number | undefined
): string {
  if (!stage || completed <= 0 || total <= 0 || !startedAt) {
    return "--:--";
  }

  const elapsed = Math.max((Date.now() / 1000) - startedAt, 0.001);
  const rate = completed / elapsed;
  if (rate <= 0) return "--:--";

  const remaining = Math.max(total - completed, 0);
  const remainingSeconds = remaining / rate;
  const minutes = Math.floor(remainingSeconds / 60);
  const seconds = Math.floor(remainingSeconds % 60);

  if (minutes > 99) return "99:59";
  return `${minutes.toString().padStart(2, "0")}:${seconds.toString().padStart(2, "0")}`;
}

/**
 * Run screen component.
 */
export function RunScreen({ inputPath, config, onBack, onComplete }: RunScreenProps) {
  const [isRunning, setIsRunning] = useState(false);
  const [canOpenOutput, setCanOpenOutput] = useState(false);
  const [statusMessage, setStatusMessage] = useState("Initializing...");
  const runIdRef = useRef<string | null>(null);

  // Get state from store
  const state = useStore();
  const reset = useStore((s) => s.reset);

  // Compute derived values
  const currentStage = state.currentStage;
  const completed = currentStage ? (state.stageCompleted[currentStage] ?? 0) : 0;
  const total = currentStage ? (state.stageTotals[currentStage] ?? 100) : 100;
  const startedAt = currentStage ? state.stageStartedAt[currentStage] : undefined;
  const eta = computeEta(currentStage, completed, total, startedAt);

  // Start pipeline on mount
  useEffect(() => {
    const startPipeline = async () => {
      const client = getIpcClient();
      
      try {
        setIsRunning(true);
        setStatusMessage("Starting pipeline...");

        const params: PipelineStartParams = {
          input_path: inputPath ?? undefined,
          output_dir: config.output_dir,
          quality: (config.quality ?? "speech") as PipelineStartParams["quality"],
          language: config.language ?? "en",
          provider: config.provider ?? "auto",
          analysis_style: (config.analysis_style ?? "concise") as PipelineStartParams["analysis_style"],
          url: config.url,
        };

        const result = await client.call("pipeline.start", params);
        runIdRef.current = result.run_id;
        setStatusMessage("Pipeline started...");
      } catch (error) {
        setIsRunning(false);
        setStatusMessage(`Error: ${error instanceof Error ? error.message : "Unknown error"}`);
      }
    };

    // Reset state before starting
    reset();
    startPipeline();

    // Cleanup
    return () => {
      // Cancel pipeline if still running
      if (runIdRef.current) {
        const client = getIpcClient();
        client.call("pipeline.cancel", { run_id: runIdRef.current }).catch(() => {});
      }
    };
  }, []); // Run once on mount

  useEffect(() => {
    if (state.isRunning) {
      setIsRunning(true);
      if (currentStage) {
        const msg = state.stageMessages[currentStage] ?? state.currentMessage;
        const etaPart = eta !== "--:--" ? ` (ETA ${eta})` : "";
        setStatusMessage(`${currentStage}: ${msg}${etaPart}`);
      }
    } else if (state.summary && Object.keys(state.summary).length > 0) {
      setStatusMessage("Pipeline completed!");
      setIsRunning(false);
      setCanOpenOutput(true);
      onComplete?.(config.output_dir);
    } else if (state.errors.length > 0) {
      setStatusMessage(`Error: ${state.errors[state.errors.length - 1]}`);
      setIsRunning(false);
    } else if (state.currentMessage.startsWith("Cancelled:")) {
      setStatusMessage(state.currentMessage);
      setIsRunning(false);
    }
  }, [state, currentStage, eta, config.output_dir, onComplete]);

  // Handle cancel
  const handleCancel = useCallback(async () => {
    if (!isRunning || !runIdRef.current) return;

    const client = getIpcClient();
    try {
      await client.call("pipeline.cancel", { run_id: runIdRef.current });
      setIsRunning(false);
      setStatusMessage("Pipeline cancelled");
    } catch (error) {
      setStatusMessage(`Cancel failed: ${error instanceof Error ? error.message : "Unknown error"}`);
    }
  }, [isRunning]);

  // Handle open output
  const handleOpenOutput = useCallback(async () => {
    const client = getIpcClient();
    try {
      await client.call("system.openPath", { path: config.output_dir });
    } catch (error) {
      setStatusMessage(`Failed to open: ${error instanceof Error ? error.message : "Unknown error"}`);
    }
  }, [config.output_dir]);

  const handleBack = useCallback(() => {
    if (isRunning) {
      setStatusMessage("Please cancel the pipeline first");
      return;
    }
    onBack();
  }, [isRunning, onBack]);

  const pipelineCompleted = canOpenOutput && !isRunning;

  useKeyboard((key) => {
    if (pipelineCompleted) return;

    if (key.name === "c" || key.name === "C") {
      handleCancel();
    } else if (key.name === "o" || key.name === "O") {
      if (canOpenOutput) handleOpenOutput();
    } else if (key.name === "escape") {
      handleBack();
    }
  });

  if (pipelineCompleted) {
    return (
      <box
        title="Pipeline Complete"
        style={{
          border: true,
          width: "100%",
          height: "100%",
          flexDirection: "column",
          padding: 1,
        }}
      >
        <CompletionPanel
          artifacts={state.artifacts}
          summary={state.summary}
          stageDurations={state.stageDurations}
          outputDir={config.output_dir}
          hasErrors={state.errors.length > 0}
          onOpenOutput={handleOpenOutput}
          onBack={handleBack}
        />
      </box>
    );
  }

  return (
    <box
      title="Pipeline Run"
      style={{
        border: true,
        width: "100%",
        height: "100%",
        flexDirection: "column",
        padding: 1,
      }}
    >
      <box
        style={{
          border: true,
          height: 12,
          flexDirection: "column",
          padding: 1,
        }}
      >
        <ProgressBoard state={state} />
      </box>

      <box
        style={{
          border: true,
          flexGrow: 1,
          minHeight: 8,
          flexDirection: "column",
          padding: 0,
        }}
      >
        <LogPanel logs={state.logs} />
      </box>

      <box style={{ height: 1, marginTop: 1 }}>
        <text fg={state.errors.length > 0 ? "#EF4444" : state.isRunning ? "#0EA5E9" : "#10B981"}>
          {statusMessage}
        </text>
      </box>

      <box
        style={{
          height: 3,
          marginTop: 1,
          flexDirection: "row",
          gap: 2,
        }}
      >
        <text fg={isRunning ? "#EF4444" : "#6B7280"}>
          [C] Cancel
        </text>

        <text fg={canOpenOutput ? "#10B981" : "#6B7280"}>
          [O] Open Output
        </text>

        <text fg={!isRunning ? "#6B7280" : "#3B3B3B"}>
          [Esc] Back
        </text>
      </box>
    </box>
  );
}
