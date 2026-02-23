/**
 * Pipeline timeline component - horizontal stage indicator.
 *
 * Shows all 5 stages with status icons:
 *   DL ──── Prep ──── Ext ──── Trans ──── Analyze
 *   [complete] [complete] [running] [pending] [pending]
 *
 * Port of src/ui/tui/widgets/pipeline_timeline.py
 */

import type { AppState } from "../protocol/state";
import type { Stage, StageStatus } from "../protocol/events";

/** All pipeline stages in order */
const STAGES: Stage[] = ["download", "extract", "transcribe", "analyze"];

/** Short labels for stages */
const STAGE_LABELS: Record<Stage, string> = {
  download: "DL",
  extract: "Ext",
  transcribe: "Trans",
  analyze: "Analyze",
};

/** Status icons */
const STATUS_ICONS: Record<StageStatus | "pending", string> = {
  pending: "○",
  running: "◉",
  complete: "●",
  error: "✗",
  skipped: "◌",
};

/** Status colors */
const STATUS_COLORS: Record<StageStatus | "pending", string> = {
  pending: "#6B7280",  // gray
  running: "#0EA5E9",  // blue
  complete: "#10B981", // green
  error: "#EF4444",    // red
  skipped: "#94A3B8",  // slate
};

export interface ProgressTimelineProps {
  state: AppState;
}

/**
 * Horizontal timeline showing all pipeline stages.
 */
export function ProgressTimeline({ state }: ProgressTimelineProps) {
  return (
    <box
      style={{
        flexDirection: "row",
        justifyContent: "space-around",
        height: 2,
        marginBottom: 1,
      }}
    >
      {STAGES.map((stage, index) => {
        const status = state.stageStatus[stage] ?? "pending";
        const icon = STATUS_ICONS[status];
        const color = STATUS_COLORS[status];
        const label = STAGE_LABELS[stage];
        const isLast = index === STAGES.length - 1;

        return (
          <box key={stage} style={{ flexDirection: "row" }}>
            {/* Stage indicator */}
            <box style={{ flexDirection: "column", alignItems: "center" }}>
              <text fg={color}>{icon}</text>
              <text fg={color}>
                {label}
              </text>
            </box>

            {/* Connector line */}
            {!isLast && (
              <text fg="#4B5563" style={{ marginLeft: 1, marginRight: 1 }}>
                ────
              </text>
            )}
          </box>
        );
      })}
    </box>
  );
}
