import { useCallback, useEffect, useState } from "react";
import { useKeyboard } from "@opentui/react";

import { getIpcClient } from "../ipc/client";
import type { RecentFile } from "../protocol/commands";
import { ProviderHealth, FileBrowser } from "../components";

export interface HomeScreenProps {
  onSelectFile: (path: string) => void;
  onSelectUrl: (url: string) => void;
  onSettings: () => void;
  onBack: () => void;
}

type FocusArea = "recent" | "path" | "url" | "browser";
type ViewMode = "recent" | "browser";

export function HomeScreen({ onSelectFile, onSelectUrl, onSettings, onBack }: HomeScreenProps) {
  const [recentFiles, setRecentFiles] = useState<RecentFile[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [pathInput, setPathInput] = useState("");
  const [urlInput, setUrlInput] = useState("");
  const [focus, setFocus] = useState<FocusArea>("recent");
  const [viewMode, setViewMode] = useState<ViewMode>("recent");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadRecent = async () => {
      try {
        const client = getIpcClient();
        const result = await client.call("recent.list", { max_entries: 10 });
        setRecentFiles(result.files);
        setLoading(false);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load recent files");
        setLoading(false);
      }
    };
    loadRecent();
  }, []);

  const handleSelectRecent = useCallback(() => {
    if (recentFiles.length > 0 && selectedIndex < recentFiles.length) {
      const file = recentFiles[selectedIndex];
      onSelectFile(file.path);
    }
  }, [recentFiles, selectedIndex, onSelectFile]);

  const handleSubmitPath = useCallback(() => {
    if (pathInput.trim()) {
      onSelectFile(pathInput.trim());
    }
  }, [pathInput, onSelectFile]);

  const handleSubmitUrl = useCallback(() => {
    const url = urlInput.trim();
    if (url && (url.startsWith("http://") || url.startsWith("https://"))) {
      onSelectUrl(url);
    }
  }, [urlInput, onSelectUrl]);

  const toggleViewMode = useCallback(() => {
    setViewMode((m) => (m === "recent" ? "browser" : "recent"));
    setFocus(viewMode === "recent" ? "browser" : "recent");
  }, [viewMode]);

  useKeyboard((key) => {
    if (focus === "browser") {
      if (key.name === "escape") {
        setViewMode("recent");
        setFocus("recent");
      } else if (key.name === "s" || key.name === "S") {
        onSettings();
      }
      return;
    }

    if (key.name === "b" || key.name === "B") {
      toggleViewMode();
      return;
    }

    if (focus === "recent") {
      if (key.name === "up" || key.name === "k") {
        setSelectedIndex((i) => Math.max(0, i - 1));
      } else if (key.name === "down" || key.name === "j") {
        setSelectedIndex((i) => Math.min(recentFiles.length - 1, i + 1));
      } else if (key.name === "return" || key.name === "enter") {
        handleSelectRecent();
      } else if (key.name === "tab") {
        setFocus("path");
      } else if (key.name === "escape") {
        onBack();
      } else if (key.name === "s" || key.name === "S") {
        onSettings();
      }
    } else if (focus === "path") {
      if (key.name === "return" || key.name === "enter") {
        handleSubmitPath();
      } else if (key.name === "tab") {
        setFocus("url");
      } else if (key.name === "escape") {
        setFocus("recent");
      } else if (key.name === "backspace") {
        setPathInput((p) => p.slice(0, -1));
      } else if (key.sequence && key.sequence.length > 0 && !key.ctrl && !key.meta) {
        setPathInput((p) => p + key.sequence);
      }
    } else if (focus === "url") {
      if (key.name === "return" || key.name === "enter") {
        handleSubmitUrl();
      } else if (key.name === "tab") {
        setFocus("recent");
      } else if (key.name === "escape") {
        setFocus("recent");
      } else if (key.name === "backspace") {
        setUrlInput((u) => u.slice(0, -1));
      } else if (key.sequence && key.sequence.length > 0 && !key.ctrl && !key.meta) {
        setUrlInput((u) => u + key.sequence);
      }
    }
  });

  if (viewMode === "browser") {
    return (
      <box
        title="Browse Files"
        style={{
          border: true,
          width: "100%",
          height: "100%",
          flexDirection: "column",
          padding: 1,
        }}
      >
        <box style={{ flexDirection: "row", justifyContent: "space-between", marginBottom: 1 }}>
          <text fg="#0EA5E9">
            <b>Browse Files</b>
          </text>
          <text fg="#6B7280">[B] Recent Files | [S] Settings</text>
        </box>

        <FileBrowser
          filter="*.mp4,*.mkv,*.avi,*.mov,*.mp3,*.wav,*.flac"
          onSelect={onSelectFile}
          onCancel={() => {
            setViewMode("recent");
            setFocus("recent");
          }}
          focused={focus === "browser"}
        />
      </box>
    );
  }

  return (
    <box
      title="Select Input"
      style={{
        border: true,
        width: "100%",
        height: "100%",
        flexDirection: "column",
        padding: 1,
      }}
    >
      <box style={{ flexDirection: "row", justifyContent: "space-between", marginBottom: 1 }}>
        <text fg="#0EA5E9">
          <b>Select Input File or URL</b>
        </text>
        <text fg="#6B7280">[B] Browse Files</text>
      </box>

      <box
        style={{
          border: true,
          flexGrow: 1,
          flexDirection: "column",
          padding: 1,
        }}
      >
        <text fg="#9CA3AF" style={{ marginBottom: 1 }}>
          Recent Files {focus === "recent" ? "(active)" : ""}
        </text>

        {loading && <text fg="#6B7280">Loading...</text>}
        {error && <text fg="#EF4444">{error}</text>}

        {!loading && !error && recentFiles.length === 0 && (
          <text fg="#6B7280">No recent files - press [B] to browse</text>
        )}

        {!loading && !error && recentFiles.map((file, idx) => {
          const fileName = file.path.split("/").pop() ?? file.path;
          return (
            <text
              key={file.path}
              fg={idx === selectedIndex && focus === "recent" ? "#10B981" : "#FFFFFF"}
              bg={idx === selectedIndex && focus === "recent" ? "#1F2937" : undefined}
            >
              {idx === selectedIndex && focus === "recent" ? ">" : " "} {fileName} ({file.size_mb.toFixed(1)} MB)
            </text>
          );
        })}
      </box>

      <box style={{ height: 3, marginTop: 1, flexDirection: "column" }}>
        <box style={{ flexDirection: "row" }}>
          <text fg="#9CA3AF" style={{ width: 12 }}>File Path:</text>
          <text fg={focus === "path" ? "#10B981" : "#FFFFFF"}>
            {pathInput || (focus === "path" ? "_" : "(Tab to enter path)")}
          </text>
        </box>
      </box>

      <box style={{ height: 3, marginTop: 1, flexDirection: "column" }}>
        <box style={{ flexDirection: "row" }}>
          <text fg="#9CA3AF" style={{ width: 12 }}>URL:</text>
          <text fg={focus === "url" ? "#10B981" : "#FFFFFF"}>
            {urlInput || (focus === "url" ? "_" : "(Tab to enter URL)")}
          </text>
        </box>
      </box>

      <box style={{ height: 3, marginTop: 1, flexDirection: "column" }}>
        <text fg="#9CA3AF" style={{ marginBottom: 0 }}>Providers:</text>
        <ProviderHealth compact />
      </box>

      <box style={{ height: 2, marginTop: 1, flexDirection: "row", gap: 2 }}>
        <text fg="#6B7280">[Tab] Switch</text>
        <text fg="#6B7280">[Enter] Select</text>
        <text fg="#6B7280">[S] Settings</text>
        <text fg="#6B7280">[Esc] Back</text>
      </box>
    </box>
  );
}
