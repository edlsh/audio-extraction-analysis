import { useEffect, useState } from "react";

import { getIpcClient } from "../ipc/client";

export interface StatusBarProps {
  theme?: string;
  verbose?: boolean;
}

type ConnectionStatus = "connected" | "disconnected" | "connecting";

const STATUS_COLORS: Record<ConnectionStatus, string> = {
  connected: "#10B981",
  disconnected: "#EF4444",
  connecting: "#F59E0B",
};

const STATUS_ICONS: Record<ConnectionStatus, string> = {
  connected: "\u25CF",
  disconnected: "\u25CB",
  connecting: "\u25D4",
};

export function StatusBar({ theme = "dark", verbose = false }: StatusBarProps) {
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>("connecting");
  const [lastPing, setLastPing] = useState<number | null>(null);

  useEffect(() => {
    let mounted = true;
    let interval: ReturnType<typeof setInterval>;

    const checkConnection = async () => {
      try {
        const client = getIpcClient();
        const start = Date.now();
        await client.call("system.ping", {});
        const elapsed = Date.now() - start;

        if (mounted) {
          setConnectionStatus("connected");
          setLastPing(elapsed);
        }
      } catch {
        if (mounted) {
          setConnectionStatus("disconnected");
          setLastPing(null);
        }
      }
    };

    checkConnection();
    interval = setInterval(checkConnection, 10000);

    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  const statusColor = STATUS_COLORS[connectionStatus];
  const statusIcon = STATUS_ICONS[connectionStatus];
  const statusLabel =
    connectionStatus === "connected"
      ? verbose && lastPing !== null
        ? `Connected (${lastPing}ms)`
        : "Connected"
      : connectionStatus === "connecting"
        ? "Connecting..."
        : "Disconnected";

  const themeIcon = theme === "dark" ? "\u263E" : "\u2600";

  return (
    <box
      style={{
        height: 1,
        width: "100%",
        flexDirection: "row",
        justifyContent: "space-between",
        paddingLeft: 1,
        paddingRight: 1,
        backgroundColor: "#1E293B",
      }}
    >
      <box style={{ flexDirection: "row", gap: 1 }}>
        <text fg={statusColor}>
          {statusIcon}
        </text>
        <text fg="#94A3B8">
          {statusLabel}
        </text>
      </box>

      <text fg="#475569">
        Audio Extraction Analysis
      </text>

      <box style={{ flexDirection: "row", gap: 2 }}>
        <text fg="#64748B">
          {themeIcon} {theme}
        </text>
        <text fg="#475569">|</text>
        <text fg="#64748B">
          [D] Theme
        </text>
        <text fg="#475569">|</text>
        <text fg="#64748B">
          [?] Help
        </text>
      </box>
    </box>
  );
}
