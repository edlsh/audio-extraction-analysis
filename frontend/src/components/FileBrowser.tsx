import { useCallback, useEffect, useState } from "react";
import { useKeyboard } from "@opentui/react";

import { getIpcClient } from "../ipc/client";
import type { DirEntry } from "../protocol/commands";

export interface FileBrowserProps {
  initialPath?: string;
  filter?: string;
  onSelect: (path: string) => void;
  onCancel?: () => void;
  focused?: boolean;
}

const AUDIO_VIDEO_EXTENSIONS = [
  ".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".wmv",
  ".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma",
];

function isMediaFile(name: string): boolean {
  const lower = name.toLowerCase();
  return AUDIO_VIDEO_EXTENSIONS.some((ext) => lower.endsWith(ext));
}

function formatSize(bytes: number | undefined): string {
  if (bytes === undefined) return "";
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)}GB`;
}

export function FileBrowser({
  initialPath,
  filter,
  onSelect,
  onCancel,
  focused = true,
}: FileBrowserProps) {
  const [currentPath, setCurrentPath] = useState(initialPath ?? process.env.HOME ?? "/");
  const [entries, setEntries] = useState<DirEntry[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [parentPath, setParentPath] = useState<string | undefined>(undefined);

  const loadDirectory = useCallback(async (path: string) => {
    setLoading(true);
    setError(null);
    try {
      const client = getIpcClient();
      const result = await client.call("system.listDir", { path, filter });

      const sortedEntries = result.entries.sort((a, b) => {
        if (a.is_dir && !b.is_dir) return -1;
        if (!a.is_dir && b.is_dir) return 1;
        return a.name.localeCompare(b.name);
      });

      setEntries(sortedEntries);
      setParentPath(result.parent);
      setCurrentPath(path);
      setSelectedIndex(0);
      setLoading(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load directory");
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    loadDirectory(currentPath);
  }, []);

  const handleEnter = useCallback(() => {
    if (entries.length === 0) return;

    const entry = entries[selectedIndex];
    if (!entry) return;

    if (entry.is_dir) {
      loadDirectory(entry.path);
    } else {
      onSelect(entry.path);
    }
  }, [entries, selectedIndex, loadDirectory, onSelect]);

  const handleBack = useCallback(() => {
    if (parentPath) {
      loadDirectory(parentPath);
    }
  }, [parentPath, loadDirectory]);

  useKeyboard((key) => {
    if (!focused) return;

    if (key.name === "up" || key.name === "k") {
      setSelectedIndex((i) => Math.max(0, i - 1));
    } else if (key.name === "down" || key.name === "j") {
      setSelectedIndex((i) => Math.min(entries.length - 1, i + 1));
    } else if (key.name === "return" || key.name === "enter") {
      handleEnter();
    } else if (key.name === "backspace" || key.name === "h" || key.name === "left") {
      handleBack();
    } else if (key.name === "escape") {
      onCancel?.();
    } else if (key.name === "g" && key.shift) {
      setSelectedIndex(entries.length - 1);
    } else if (key.name === "g") {
      setSelectedIndex(0);
    }
  });

  const visibleEntries = entries.slice(
    Math.max(0, selectedIndex - 8),
    Math.min(entries.length, selectedIndex + 12)
  );
  const startIndex = Math.max(0, selectedIndex - 8);

  return (
    <box
      style={{
        border: true,
        flexDirection: "column",
        height: "100%",
        width: "100%",
      }}
    >
      <box style={{ height: 2, paddingLeft: 1, paddingRight: 1, flexDirection: "column" }}>
        <text fg="#0EA5E9" style={{ marginBottom: 0 }}>
          <b>{currentPath}</b>
        </text>
        {parentPath && (
          <text fg="#6B7280">
            [Backspace] Go up
          </text>
        )}
      </box>

      {loading && (
        <box style={{ padding: 1 }}>
          <text fg="#6B7280">Loading...</text>
        </box>
      )}

      {error && (
        <box style={{ padding: 1 }}>
          <text fg="#EF4444">{error}</text>
        </box>
      )}

      {!loading && !error && entries.length === 0 && (
        <box style={{ padding: 1 }}>
          <text fg="#6B7280">Empty directory</text>
        </box>
      )}

      {!loading && !error && entries.length > 0 && (
        <scrollbox style={{ flexGrow: 1, paddingLeft: 1 }}>
          {visibleEntries.map((entry, idx) => {
            const actualIndex = startIndex + idx;
            const isSelected = actualIndex === selectedIndex;
            const isDir = entry.is_dir;
            const isMedia = !isDir && isMediaFile(entry.name);

            let icon = "  ";
            let color = "#FFFFFF";

            if (isDir) {
              icon = "\u{1F4C1} ";
              color = "#60A5FA";
            } else if (isMedia) {
              icon = "\u{1F3AC} ";
              color = "#10B981";
            } else {
              icon = "   ";
              color = "#9CA3AF";
            }

            return (
              <box
                key={entry.path}
                style={{
                  flexDirection: "row",
                  backgroundColor: isSelected ? "#1F2937" : undefined,
                }}
              >
                <text fg={isSelected ? "#FFFFFF" : color}>
                  {isSelected ? ">" : " "} {icon}{entry.name}
                </text>
                {!isDir && entry.size_bytes !== undefined && (
                  <text fg="#6B7280" style={{ marginLeft: 1 }}>
                    ({formatSize(entry.size_bytes)})
                  </text>
                )}
              </box>
            );
          })}
        </scrollbox>
      )}

      <box style={{ height: 1, paddingLeft: 1, marginTop: 1, flexDirection: "row", gap: 2 }}>
        <text fg="#6B7280">[Enter] Select</text>
        <text fg="#6B7280">[j/k] Navigate</text>
        <text fg="#6B7280">[Esc] Cancel</text>
      </box>
    </box>
  );
}
