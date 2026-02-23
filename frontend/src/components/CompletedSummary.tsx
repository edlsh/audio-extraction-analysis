/**
 * Completed summary component - compact row of finished stages.
 *
 * Shows: Completed: Download (2.1s) Prepare (0.5s) Extract (15.3s)
 *
 * Port of src/ui/tui/widgets/completed_summary.py
 */

import type { AppState } from "../protocol/state";
import type { Stage } from "../protocol/events";

/** All pipeline stages in order */
const STAGES: Stage[] = ["download", "extract", "transcribe", "analyze"];

/** Short labels for stages */
const STAGE_LABELS: Record<Stage, string> = {
  download: "Download",
  extract: "Extract",
  transcribe: "Transcribe",
  analyze: "Analyze",
};

export interface CompletedSummaryProps {
  state: AppState;
}

/**
 * Format duration for display.
 */
function formatDuration(seconds: number): string {
  if (seconds < 60) {
    return `${seconds.toFixed(1)}s`;
  }
  const minutes = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${minutes}m${secs}s`;
}

/**
 * Completed stages summary row.
 */
export function CompletedSummary({ state }: CompletedSummaryProps) {
  // Get completed stages
  const completedStages = STAGES.filter(
    (stage) => state.stageStatus[stage] === "complete"
  );

  if (completedStages.length === 0) {
    return null;
  }

  // Build summary items
  const items = completedStages.map((stage) => {
    const duration = state.stageDurations[stage] ?? 0;
    const label = STAGE_LABELS[stage];
    return `${label} (${formatDuration(duration)})`;
  });

  return (
    <box style={{ height: 1, flexDirection: "row" }}>
      <text fg="#10B981">Completed: </text>
      <text fg="#6B7280">{items.join(" | ")}</text>
    </box>
  );
}
