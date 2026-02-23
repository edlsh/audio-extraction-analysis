import { useKeyboard } from "@opentui/react";

export interface HelpScreenProps {
  onBack: () => void;
}

interface ShortcutSection {
  title: string;
  shortcuts: Array<{ key: string; description: string }>;
}

const SHORTCUTS: ShortcutSection[] = [
  {
    title: "Global",
    shortcuts: [
      { key: "Ctrl+C", description: "Quit application" },
      { key: "Esc", description: "Go back / Cancel" },
      { key: "?", description: "Show this help" },
    ],
  },
  {
    title: "Welcome Screen",
    shortcuts: [
      { key: "Enter", description: "Quick start - select a file" },
      { key: "C", description: "Open configuration" },
      { key: "Q", description: "Quit" },
    ],
  },
  {
    title: "Home Screen",
    shortcuts: [
      { key: "j/k or ↑/↓", description: "Navigate recent files" },
      { key: "Enter", description: "Select file" },
      { key: "Tab", description: "Switch between sections" },
      { key: "S", description: "Open settings" },
    ],
  },
  {
    title: "Config Screen",
    shortcuts: [
      { key: "Enter", description: "Start pipeline" },
      { key: "Esc", description: "Go back" },
    ],
  },
  {
    title: "Run Screen",
    shortcuts: [
      { key: "C", description: "Cancel pipeline" },
      { key: "O", description: "Open output folder (when complete)" },
      { key: "Esc", description: "Go back (if not running)" },
    ],
  },
  {
    title: "Settings Screen",
    shortcuts: [
      { key: "j/k or ↑/↓", description: "Navigate fields" },
      { key: "Enter", description: "Edit API key" },
      { key: "←/→", description: "Change option value" },
      { key: "T", description: "Open theme selector" },
    ],
  },
];

export function HelpScreen({ onBack }: HelpScreenProps) {
  useKeyboard((key) => {
    if (key.name === "escape" || key.name === "q" || key.name === "Q") {
      onBack();
    }
  });

  return (
    <box
      title="Help"
      style={{
        border: true,
        width: "100%",
        height: "100%",
        flexDirection: "column",
        padding: 1,
      }}
    >
      <text fg="#0EA5E9" style={{ marginBottom: 2 }}>
        <b>Keyboard Shortcuts</b>
      </text>

      <scrollbox style={{ flexGrow: 1 }}>
        {SHORTCUTS.map((section) => (
          <box key={section.title} style={{ marginBottom: 2 }}>
            <text fg="#F59E0B" style={{ marginBottom: 1 }}>
              <b>{section.title}</b>
            </text>
            {section.shortcuts.map((shortcut) => (
              <box key={shortcut.key} style={{ flexDirection: "row" }}>
                <text fg="#10B981" style={{ width: 20 }}>
                  {shortcut.key}
                </text>
                <text fg="#9CA3AF">{shortcut.description}</text>
              </box>
            ))}
          </box>
        ))}
      </scrollbox>

      <box style={{ marginTop: 1 }}>
        <text fg="#6B7280">[Esc] or [Q] Close help</text>
      </box>
    </box>
  );
}
