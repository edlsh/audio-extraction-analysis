/**
 * Focus card component - displays active stage with progress bar.
 *
 * Shows:
 *   Stage Name               72%
 *   [================>     ] ETA: 00:45
 *   Current message or action
 *
 * Port of src/ui/tui/widgets/focus_card.py
 */

import type { AppState } from "../protocol/state";
import type { Stage } from "../protocol/events";

/** Full stage names for display */
const STAGE_NAMES: Record<Stage, string> = {
  download: "Downloading",
  extract: "Extracting Audio",
  transcribe: "Transcribing",
  analyze: "Analyzing",
};

export interface FocusCardProps {
  state: AppState;
}

/**
 * Compute ETA string from state.
 */
function computeEta(state: AppState, stage: Stage): string {
  const completed = state.stageCompleted[stage] ?? 0;
  const total = state.stageTotals[stage] ?? 0;
  const startedAt = state.stageStartedAt[stage];

  if (completed <= 0 || total <= 0 || !startedAt) {
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
 * Render progress bar as text.
 */
function renderProgressBar(percent: number, width: number = 30): string {
  const filled = Math.floor((percent / 100) * width);
  const empty = width - filled;
  const bar = "█".repeat(filled) + "░".repeat(empty);
  return `[${bar}]`;
}

/**
 * Focus card showing active stage progress.
 */
export function FocusCard({ state }: FocusCardProps) {
  const stage = state.currentStage;

  // If no active stage, show idle state
  if (!stage) {
    if (state.summary && Object.keys(state.summary).length > 0) {
      return (
        <box style={{ height: 4, flexDirection: "column", padding: 1 }}>
          <text fg="#10B981">
            <b>Pipeline Complete</b>
          </text>
          <text fg="#6B7280">
            All stages finished successfully
          </text>
        </box>
      );
    }

    if (state.errors.length > 0) {
      return (
        <box style={{ height: 4, flexDirection: "column", padding: 1 }}>
          <text fg="#EF4444">
            <b>Pipeline Error</b>
          </text>
          <text fg="#EF4444">
            {state.errors[state.errors.length - 1]}
          </text>
        </box>
      );
    }

    return (
      <box style={{ height: 4, flexDirection: "column", padding: 1 }}>
        <text fg="#6B7280">
          Waiting to start...
        </text>
      </box>
    );
  }

  // Get stage data
  const stageName = STAGE_NAMES[stage];
  const completed = state.stageCompleted[stage] ?? 0;
  const total = state.stageTotals[stage] ?? 100;
  const percent = total > 0 ? Math.round((completed / total) * 100) : 0;
  const eta = computeEta(state, stage);
  const message = state.stageMessages[stage] ?? state.currentMessage;
  const progressBar = renderProgressBar(percent);

  return (
    <box style={{ height: 4, flexDirection: "column", marginBottom: 1 }}>
      <box style={{ flexDirection: "row", justifyContent: "space-between" }}>
        <text fg="#0EA5E9">
          <b>{stageName}</b>
        </text>
        <text fg="#0EA5E9">
          {percent}%
        </text>
      </box>

      {/* Progress bar + ETA */}
      <box style={{ flexDirection: "row", justifyContent: "space-between" }}>
        <text fg="#0EA5E9">
          {progressBar}
        </text>
        <text fg="#6B7280">
          ETA: {eta}
        </text>
      </box>

      {/* Current message */}
      {message && (
        <text fg="#9CA3AF" style={{ marginTop: 0 }}>
          {message.length > 60 ? message.slice(0, 57) + "..." : message}
        </text>
      )}
    </box>
  );
}
