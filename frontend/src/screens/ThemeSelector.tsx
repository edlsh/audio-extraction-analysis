import { useCallback, useEffect, useState } from "react";
import { useKeyboard } from "@opentui/react";

import { getIpcClient } from "../ipc/client";
import type { ThemeDefinition } from "../protocol/commands";

export interface ThemeSelectorScreenProps {
  onBack: () => void;
  onSelect: (themeName: string) => void;
}

export function ThemeSelectorScreen({ onBack, onSelect }: ThemeSelectorScreenProps) {
  const [themes, setThemes] = useState<ThemeDefinition[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [currentTheme, setCurrentTheme] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadThemes = async () => {
      try {
        const client = getIpcClient();
        const result = await client.call("themes.catalog", {});
        setThemes(result.themes);
        setCurrentTheme(result.default_theme);
        const idx = result.themes.findIndex((t) => t.name === result.default_theme);
        if (idx >= 0) setSelectedIndex(idx);
        setLoading(false);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load themes");
        setLoading(false);
      }
    };
    loadThemes();
  }, []);

  const handleSelect = useCallback(() => {
    if (themes.length > 0 && selectedIndex < themes.length) {
      const theme = themes[selectedIndex];
      onSelect(theme.name);
    }
  }, [themes, selectedIndex, onSelect]);

  useKeyboard((key) => {
    if (key.name === "escape") {
      onBack();
    } else if (key.name === "up" || key.name === "k") {
      setSelectedIndex((i) => Math.max(0, i - 1));
    } else if (key.name === "down" || key.name === "j") {
      setSelectedIndex((i) => Math.min(themes.length - 1, i + 1));
    } else if (key.name === "return" || key.name === "enter") {
      handleSelect();
    }
  });

  const selectedTheme = themes[selectedIndex];

  return (
    <box
      title="Theme Selector"
      style={{
        border: true,
        width: "100%",
        height: "100%",
        flexDirection: "row",
        padding: 1,
      }}
    >
      <box style={{ width: "50%", flexDirection: "column", paddingRight: 1 }}>
        <text fg="#0EA5E9" style={{ marginBottom: 2 }}>
          <b>Select Theme</b>
        </text>

        {loading && <text fg="#6B7280">Loading themes...</text>}
        {error && <text fg="#EF4444">{error}</text>}

        <scrollbox style={{ flexGrow: 1 }}>
          {themes.map((theme, idx) => (
            <text
              key={theme.name}
              fg={idx === selectedIndex ? "#10B981" : theme.name === currentTheme ? "#F59E0B" : "#FFFFFF"}
              bg={idx === selectedIndex ? "#1F2937" : undefined}
            >
              {idx === selectedIndex ? ">" : " "} {theme.name}
              {theme.name === currentTheme ? " (current)" : ""}
              {theme.dark ? " [dark]" : " [light]"}
            </text>
          ))}
        </scrollbox>

        <box style={{ marginTop: 1, flexDirection: "row", gap: 2 }}>
          <text fg="#6B7280">[Enter] Apply</text>
          <text fg="#6B7280">[Esc] Cancel</text>
        </box>
      </box>

      <box
        style={{
          width: "50%",
          border: true,
          flexDirection: "column",
          padding: 1,
        }}
      >
        <text fg="#0EA5E9" style={{ marginBottom: 1 }}>
          <b>Preview</b>
        </text>

        {selectedTheme && (
          <>
            <text fg="#9CA3AF" style={{ marginBottom: 1 }}>
              {selectedTheme.name} ({selectedTheme.dark ? "Dark" : "Light"})
            </text>

            <box style={{ flexDirection: "column", gap: 1 }}>
              <box style={{ flexDirection: "row" }}>
                <text fg="#9CA3AF" style={{ width: 12 }}>Primary:</text>
                <text fg={selectedTheme.primary}>████ {selectedTheme.primary}</text>
              </box>
              <box style={{ flexDirection: "row" }}>
                <text fg="#9CA3AF" style={{ width: 12 }}>Secondary:</text>
                <text fg={selectedTheme.secondary}>████ {selectedTheme.secondary}</text>
              </box>
              <box style={{ flexDirection: "row" }}>
                <text fg="#9CA3AF" style={{ width: 12 }}>Accent:</text>
                <text fg={selectedTheme.accent}>████ {selectedTheme.accent}</text>
              </box>
              <box style={{ flexDirection: "row" }}>
                <text fg="#9CA3AF" style={{ width: 12 }}>Success:</text>
                <text fg={selectedTheme.success}>████ {selectedTheme.success}</text>
              </box>
              <box style={{ flexDirection: "row" }}>
                <text fg="#9CA3AF" style={{ width: 12 }}>Warning:</text>
                <text fg={selectedTheme.warning}>████ {selectedTheme.warning}</text>
              </box>
              <box style={{ flexDirection: "row" }}>
                <text fg="#9CA3AF" style={{ width: 12 }}>Error:</text>
                <text fg={selectedTheme.error}>████ {selectedTheme.error}</text>
              </box>
            </box>
          </>
        )}
      </box>
    </box>
  );
}
