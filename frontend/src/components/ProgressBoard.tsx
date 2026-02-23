/**
 * Progress board component - displays pipeline stage progress.
 *
 * Uses Timeline + Focus Card + Completed Summary pattern.
 *
 * Port of src/ui/tui/widgets/progress_board.py
 */

import type { AppState } from "../protocol/state";
import type { Stage } from "../protocol/events";

import { ProgressTimeline } from "./ProgressTimeline";
import { FocusCard } from "./FocusCard";
import { CompletedSummary } from "./CompletedSummary";

export interface ProgressBoardProps {
  state: AppState;
}

/**
 * Progress board with timeline, focus card, and completed summary.
 */
export function ProgressBoard({ state }: ProgressBoardProps) {
  return (
    <box style={{ flexDirection: "column", width: "100%", height: "100%" }}>
      {/* Timeline at top - always visible */}
      <ProgressTimeline state={state} />

      {/* Focus card for active stage */}
      <FocusCard state={state} />

      {/* Completed summary at bottom */}
      <CompletedSummary state={state} />
    </box>
  );
}
