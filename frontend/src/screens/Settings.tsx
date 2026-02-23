import { useCallback, useEffect, useState } from "react";
import { useKeyboard } from "@opentui/react";

import { getIpcClient } from "../ipc/client";
import type { SettingsData } from "../protocol/commands";

export interface SettingsScreenProps {
  onBack: () => void;
  onThemes: () => void;
}

type FocusField = "deepgram" | "elevenlabs" | "gemini" | "quality" | "language" | "provider";

const FIELDS: FocusField[] = ["deepgram", "elevenlabs", "gemini", "quality", "language", "provider"];

const QUALITY_OPTIONS = ["speech", "standard", "high", "compressed"];
const LANGUAGE_OPTIONS = ["en", "es", "fr", "de", "auto"];
const PROVIDER_OPTIONS = ["auto", "deepgram", "elevenlabs", "whisper"];

export function SettingsScreen({ onBack, onThemes }: SettingsScreenProps) {
  const [settings, setSettings] = useState<SettingsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [focusIndex, setFocusIndex] = useState(0);
  const [editMode, setEditMode] = useState(false);
  const [inputBuffer, setInputBuffer] = useState("");

  const focusField = FIELDS[focusIndex];

  useEffect(() => {
    const loadSettings = async () => {
      try {
        const client = getIpcClient();
        const result = await client.call("settings.get", {});
        setSettings(result.settings);
        setLoading(false);
      } catch (err) {
        setMessage(`Error: ${err instanceof Error ? err.message : "Failed to load"}`);
        setLoading(false);
      }
    };
    loadSettings();
  }, []);

  const saveKey = useCallback(async (key: string, value: string) => {
    setSaving(true);
    try {
      const client = getIpcClient();
      await client.call("settings.update", { key: `api_keys.${key}`, value });
      setMessage(`Saved ${key} API key`);
      if (settings) {
        setSettings({
          ...settings,
          api_keys: { ...settings.api_keys, [key]: value },
        });
      }
    } catch (err) {
      setMessage(`Error saving: ${err instanceof Error ? err.message : "Unknown"}`);
    }
    setSaving(false);
  }, [settings]);

  const saveDefault = useCallback(async (key: string, value: string) => {
    setSaving(true);
    try {
      const client = getIpcClient();
      await client.call("settings.update", { key: `defaults.${key}`, value });
      setMessage(`Saved ${key} setting`);
      if (settings) {
        setSettings({
          ...settings,
          defaults: { ...settings.defaults, [key]: value },
        });
      }
    } catch (err) {
      setMessage(`Error saving: ${err instanceof Error ? err.message : "Unknown"}`);
    }
    setSaving(false);
  }, [settings]);

  const cycleOption = useCallback((field: FocusField, direction: 1 | -1) => {
    if (!settings) return;
    
    let options: string[];
    let current: string;
    let saveKey: string;
    
    switch (field) {
      case "quality":
        options = QUALITY_OPTIONS;
        current = settings.defaults.quality;
        saveKey = "quality";
        break;
      case "language":
        options = LANGUAGE_OPTIONS;
        current = settings.defaults.language;
        saveKey = "language";
        break;
      case "provider":
        options = PROVIDER_OPTIONS;
        current = settings.defaults.provider;
        saveKey = "provider";
        break;
      default:
        return;
    }
    
    const idx = options.indexOf(current);
    const newIdx = (idx + direction + options.length) % options.length;
    saveDefault(saveKey, options[newIdx]);
  }, [settings, saveDefault]);

  useKeyboard((key) => {
    if (editMode) {
      if (key.name === "escape") {
        setEditMode(false);
        setInputBuffer("");
      } else if (key.name === "return" || key.name === "enter") {
        if (inputBuffer.trim()) {
          saveKey(focusField, inputBuffer.trim());
        }
        setEditMode(false);
        setInputBuffer("");
      } else if (key.name === "backspace") {
        setInputBuffer((b) => b.slice(0, -1));
      } else if (key.sequence && key.sequence.length === 1 && !key.ctrl && !key.meta) {
        setInputBuffer((b) => b + key.sequence);
      }
      return;
    }

    if (key.name === "escape") {
      onBack();
    } else if (key.name === "up" || key.name === "k") {
      setFocusIndex((i) => Math.max(0, i - 1));
    } else if (key.name === "down" || key.name === "j") {
      setFocusIndex((i) => Math.min(FIELDS.length - 1, i + 1));
    } else if (key.name === "return" || key.name === "enter") {
      if (["deepgram", "elevenlabs", "gemini"].includes(focusField)) {
        setEditMode(true);
        setInputBuffer("");
      }
    } else if (key.name === "left" || key.name === "h") {
      if (["quality", "language", "provider"].includes(focusField)) {
        cycleOption(focusField, -1);
      }
    } else if (key.name === "right" || key.name === "l") {
      if (["quality", "language", "provider"].includes(focusField)) {
        cycleOption(focusField, 1);
      }
    } else if (key.name === "t" || key.name === "T") {
      onThemes();
    }
  });

  const getKeyStatus = (provider: string): string => {
    const value = settings?.api_keys?.[provider as keyof typeof settings.api_keys];
    return value ? "Configured" : "Not set";
  };

  const getKeyStatusColor = (provider: string): string => {
    const value = settings?.api_keys?.[provider as keyof typeof settings.api_keys];
    return value ? "#10B981" : "#6B7280";
  };

  const renderField = (field: FocusField, label: string, hint?: string) => {
    const isFocused = focusField === field;
    const isApiKey = ["deepgram", "elevenlabs", "gemini"].includes(field);
    const isOption = ["quality", "language", "provider"].includes(field);

    let value = "";
    if (isApiKey) {
      if (editMode && isFocused) {
        value = inputBuffer + "_";
      } else {
        const stored = settings?.api_keys?.[field as keyof typeof settings.api_keys];
        value = stored ? "••••••••" : "(not set)";
      }
    } else if (isOption && settings) {
      value = settings.defaults[field as keyof typeof settings.defaults] as string;
    }

    return (
      <box key={field} style={{ flexDirection: "row", marginBottom: 1 }}>
        <text
          fg={isFocused ? "#10B981" : "#9CA3AF"}
          style={{ width: 18 }}
        >
          {isFocused ? ">" : " "} {label}:
        </text>
        <text fg={isFocused ? "#FFFFFF" : "#9CA3AF"}>
          {isOption ? `< ${value} >` : value}
        </text>
        {isApiKey && !editMode && (
          <text fg={getKeyStatusColor(field)} style={{ marginLeft: 2 }}>
            [{getKeyStatus(field)}]
          </text>
        )}
        {hint && !isFocused && (
          <text fg="#4B5563" style={{ marginLeft: 2 }}>
            {hint}
          </text>
        )}
      </box>
    );
  };

  return (
    <box
      title="Settings"
      style={{
        border: true,
        width: "100%",
        height: "100%",
        flexDirection: "column",
        padding: 1,
      }}
    >
      <text fg="#0EA5E9" style={{ marginBottom: 2 }}>
        <b>Settings</b>
      </text>

      {loading && <text fg="#6B7280">Loading settings...</text>}

      {!loading && settings && (
        <>
          <box style={{ border: true, padding: 1, marginBottom: 1 }}>
            <text fg="#9CA3AF" style={{ marginBottom: 1 }}>
              API Keys (Enter to edit)
            </text>
            {renderField("deepgram", "Deepgram", "console.deepgram.com")}
            {renderField("elevenlabs", "ElevenLabs", "elevenlabs.io")}
            {renderField("gemini", "Gemini", "aistudio.google.com")}
          </box>

          <box style={{ border: true, padding: 1, marginBottom: 1 }}>
            <text fg="#9CA3AF" style={{ marginBottom: 1 }}>
              Defaults (Left/Right to change)
            </text>
            {renderField("quality", "Quality")}
            {renderField("language", "Language")}
            {renderField("provider", "Provider")}
          </box>
        </>
      )}

      {message && (
        <text fg={message.startsWith("Error") ? "#EF4444" : "#10B981"} style={{ marginTop: 1 }}>
          {message}
        </text>
      )}

      <box style={{ marginTop: "auto", flexDirection: "row", gap: 2 }}>
        <text fg="#6B7280">[Esc] Back</text>
        <text fg="#6B7280">[T] Themes</text>
        <text fg="#6B7280">[Enter] Edit API Key</text>
        <text fg="#6B7280">[←/→] Change Option</text>
      </box>
    </box>
  );
}
