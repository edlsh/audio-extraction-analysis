/**
 * Provider health indicator component.
 *
 * Shows which transcription providers are available with status icons.
 * Fetches health data from backend on mount.
 */

import { useEffect, useState } from "react";

import { getIpcClient } from "../ipc/client";
import type { ProviderHealth as ProviderHealthData } from "../protocol/commands";

export interface ProviderHealthProps {
  /** Compact mode - single line */
  compact?: boolean;
  /** Show only available providers */
  availableOnly?: boolean;
}

/** Status indicators */
const STATUS_ICONS = {
  available: "\u2713", // checkmark
  unavailable: "\u2717", // x mark
  loading: "\u2026", // ellipsis
};

/** Provider display names */
const PROVIDER_NAMES: Record<string, string> = {
  deepgram: "Deepgram",
  elevenlabs: "ElevenLabs",
  whisper: "Whisper",
  parakeet: "Parakeet",
};

/**
 * Provider health indicator.
 */
export function ProviderHealth({ compact = false, availableOnly = false }: ProviderHealthProps) {
  const [providers, setProviders] = useState<ProviderHealthData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchHealth = async () => {
      try {
        const client = getIpcClient();
        const result = await client.call("providers.health", {});
        setProviders(result.providers);
        setLoading(false);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to fetch");
        setLoading(false);
      }
    };
    fetchHealth();
  }, []);

  if (loading) {
    return (
      <box style={{ flexDirection: compact ? "row" : "column", gap: compact ? 2 : 0 }}>
        <text fg="#6B7280">
          {STATUS_ICONS.loading} Loading providers...
        </text>
      </box>
    );
  }

  if (error) {
    return (
      <box style={{ flexDirection: compact ? "row" : "column", gap: compact ? 2 : 0 }}>
        <text fg="#EF4444">
          {STATUS_ICONS.unavailable} {error}
        </text>
      </box>
    );
  }

  const displayProviders = availableOnly
    ? providers.filter((p) => p.available)
    : providers;

  if (displayProviders.length === 0) {
    return (
      <text fg="#6B7280">No providers available</text>
    );
  }

  if (compact) {
    // Single line: Deepgram ✓  ElevenLabs ✓  Whisper ✗
    return (
      <box style={{ flexDirection: "row", gap: 2 }}>
        {displayProviders.map((provider) => {
          const name = PROVIDER_NAMES[provider.name] ?? provider.name;
          const icon = provider.available ? STATUS_ICONS.available : STATUS_ICONS.unavailable;
          const color = provider.available ? "#10B981" : "#6B7280";

          return (
            <text key={provider.name} fg={color}>
              {name} {icon}
            </text>
          );
        })}
      </box>
    );
  }

  // Vertical list with details
  return (
    <box style={{ flexDirection: "column", gap: 0 }}>
      {displayProviders.map((provider) => {
        const name = PROVIDER_NAMES[provider.name] ?? provider.name;
        const icon = provider.available ? STATUS_ICONS.available : STATUS_ICONS.unavailable;
        const color = provider.available ? "#10B981" : "#EF4444";
        const statusText = provider.available ? "Ready" : provider.reason ?? "Unavailable";

        return (
          <box key={provider.name} style={{ flexDirection: "row" }}>
            <text fg={color} style={{ width: 3 }}>
              {icon}
            </text>
            <text fg="#FFFFFF" style={{ width: 12 }}>
              {name}
            </text>
            <text fg="#6B7280">
              {statusText}
            </text>
          </box>
        );
      })}
    </box>
  );
}
