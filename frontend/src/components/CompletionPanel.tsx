import { useCallback, useState } from "react";
import { useKeyboard } from "@opentui/react";

import { getIpcClient } from "../ipc/client";
import type { Artifact, PipelineSummary } from "../protocol/state";
import type { Stage } from "../protocol/events";

export interface CompletionPanelProps {
  artifacts: Artifact[];
  summary: PipelineSummary;
  stageDurations: Record<Stage, number>;
  outputDir: string;
  hasErrors: boolean;
  onOpenOutput: () => void;
  onBack: () => void;
}

const ARTIFACT_ICONS: Record<string, string> = {
  audio: "\u266B",
  transcript: "\u2263",
  analysis: "\u2756",
  summary: "\u2605",
  default: "\u25A0",
};

function formatDuration(seconds: number): string {
  if (seconds < 60) {
    return `${seconds.toFixed(1)}s`;
  }
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}m ${secs}s`;
}

function getArtifactIcon(kind: string): string {
  return ARTIFACT_ICONS[kind.toLowerCase()] ?? ARTIFACT_ICONS.default;
}

function getFileName(path: string): string {
  return path.split("/").pop() ?? path;
}

export function CompletionPanel({
  artifacts,
  summary,
  stageDurations,
  outputDir,
  hasErrors,
  onOpenOutput,
  onBack,
}: CompletionPanelProps) {
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const totalDuration = Object.values(stageDurations).reduce((sum, d) => sum + d, 0);
  const provider = summary.provider ?? "auto";

  const handleOpenArtifact = useCallback(async (path: string) => {
    try {
      const client = getIpcClient();
      await client.call("system.openPath", { path });
      setStatusMessage(`Opened: ${getFileName(path)}`);
    } catch {
      setStatusMessage("Failed to open file");
    }
  }, []);

  useKeyboard((key) => {
    if (key.name === "j" || key.name === "down") {
      setSelectedIndex((prev) => Math.min(prev + 1, artifacts.length - 1));
    } else if (key.name === "k" || key.name === "up") {
      setSelectedIndex((prev) => Math.max(prev - 1, 0));
    } else if (key.name === "return" || key.name === "enter") {
      if (artifacts[selectedIndex]) {
        handleOpenArtifact(artifacts[selectedIndex].path);
      }
    } else if (key.name === "o" || key.name === "O") {
      onOpenOutput();
    } else if (key.name === "escape") {
      onBack();
    }
  });

  const statusColor = hasErrors ? "#EF4444" : "#10B981";
  const statusIcon = hasErrors ? "\u2717" : "\u2713";
  const statusText = hasErrors ? "Completed with errors" : "Pipeline completed successfully";

  return (
    <box
      style={{
        flexDirection: "column",
        width: "100%",
        height: "100%",
      }}
    >
      <box
        style={{
          border: true,
          borderStyle: "rounded",
          padding: 1,
          marginBottom: 1,
          flexDirection: "column",
          alignItems: "center",
        }}
      >
        <text fg={statusColor} style={{ marginBottom: 1 }}>
          <b>{statusIcon} {statusText}</b>
        </text>

        <box style={{ flexDirection: "row", gap: 3 }}>
          <box style={{ flexDirection: "row", gap: 1 }}>
            <text fg="#64748B">Total time:</text>
            <text fg="#FFFFFF">{formatDuration(totalDuration)}</text>
          </box>
          <box style={{ flexDirection: "row", gap: 1 }}>
            <text fg="#64748B">Provider:</text>
            <text fg="#0EA5E9">{provider}</text>
          </box>
          <box style={{ flexDirection: "row", gap: 1 }}>
            <text fg="#64748B">Files:</text>
            <text fg="#FFFFFF">{artifacts.length}</text>
          </box>
        </box>
      </box>

      <box
        style={{
          border: true,
          borderStyle: "rounded",
          padding: 1,
          flexGrow: 1,
          flexDirection: "column",
        }}
      >
        <text fg="#94A3B8" style={{ marginBottom: 1 }}>
          <b>Generated Files</b> (j/k to navigate, Enter to open)
        </text>

        {artifacts.length === 0 ? (
          <text fg="#6B7280">No artifacts generated</text>
        ) : (
          <box style={{ flexDirection: "column" }}>
            {artifacts.map((artifact, index) => {
              const isSelected = index === selectedIndex;
              const icon = getArtifactIcon(artifact.kind);
              const fileName = getFileName(artifact.path);

              return (
                <box
                  key={artifact.path}
                  style={{
                    flexDirection: "row",
                    backgroundColor: isSelected ? "#334155" : undefined,
                    paddingLeft: 1,
                    paddingRight: 1,
                  }}
                >
                  <text fg={isSelected ? "#0EA5E9" : "#64748B"} style={{ width: 3 }}>
                    {isSelected ? "\u25B6" : " "}
                  </text>
                  <text fg="#F59E0B" style={{ width: 3 }}>
                    {icon}
                  </text>
                  <text fg="#FFFFFF" style={{ width: 30 }}>
                    {fileName.length > 28 ? fileName.slice(0, 25) + "..." : fileName}
                  </text>
                  <text fg="#64748B">
                    {artifact.kind}
                  </text>
                </box>
              );
            })}
          </box>
        )}
      </box>

      <box style={{ flexDirection: "row", gap: 1, marginTop: 1 }}>
        <text fg="#64748B">Output:</text>
        <text fg="#94A3B8">{outputDir}</text>
      </box>

      {statusMessage && (
        <box style={{ marginTop: 1 }}>
          <text fg="#0EA5E9">{statusMessage}</text>
        </box>
      )}

      <box
        style={{
          flexDirection: "row",
          gap: 3,
          marginTop: 1,
          paddingTop: 1,
        }}
      >
        <text fg="#10B981">
          [O] Open Output Folder
        </text>
        <text fg="#6B7280">
          [Enter] Open Selected
        </text>
        <text fg="#6B7280">
          [Esc] Back
        </text>
      </box>
    </box>
  );
}
