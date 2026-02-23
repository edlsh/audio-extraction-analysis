import { useCallback } from "react";
import { useKeyboard } from "@opentui/react";

export interface QuickRunModalProps {
  inputPath: string | null;
  url: string | null;
  outputDir: string;
  quality: string;
  provider: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export function QuickRunModal({
  inputPath,
  url,
  outputDir,
  quality,
  provider,
  onConfirm,
  onCancel,
}: QuickRunModalProps) {
  useKeyboard((key) => {
    if (key.name === "return" || key.name === "enter" || key.name === "y" || key.name === "Y") {
      onConfirm();
    } else if (key.name === "escape" || key.name === "n" || key.name === "N") {
      onCancel();
    }
  });

  const input = inputPath ?? url ?? "(none)";
  const inputLabel = url ? "URL" : "File";

  return (
    <box
      style={{
        position: "absolute",
        top: "50%",
        left: "50%",
        width: 60,
        height: 14,
        marginTop: -7,
        marginLeft: -30,
        border: true,
        flexDirection: "column",
        padding: 1,
      }}
    >
      <text fg="#0EA5E9" style={{ marginBottom: 1 }}>
        <b>Start Pipeline?</b>
      </text>

      <box style={{ flexDirection: "column", gap: 1, marginBottom: 2 }}>
        <box style={{ flexDirection: "row" }}>
          <text fg="#9CA3AF" style={{ width: 12 }}>{inputLabel}:</text>
          <text fg="#FFFFFF">
            {input.length > 40 ? "..." + input.slice(-37) : input}
          </text>
        </box>

        <box style={{ flexDirection: "row" }}>
          <text fg="#9CA3AF" style={{ width: 12 }}>Output:</text>
          <text fg="#FFFFFF">{outputDir}</text>
        </box>

        <box style={{ flexDirection: "row" }}>
          <text fg="#9CA3AF" style={{ width: 12 }}>Quality:</text>
          <text fg="#FFFFFF">{quality}</text>
        </box>

        <box style={{ flexDirection: "row" }}>
          <text fg="#9CA3AF" style={{ width: 12 }}>Provider:</text>
          <text fg="#FFFFFF">{provider}</text>
        </box>
      </box>

      <box style={{ flexDirection: "row", gap: 4, marginTop: "auto" }}>
        <text fg="#10B981">
          [Enter/Y] Confirm
        </text>
        <text fg="#6B7280">
          [Esc/N] Cancel
        </text>
      </box>
    </box>
  );
}
