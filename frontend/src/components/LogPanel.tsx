/**
 * Log panel component - scrollable, filterable log viewer.
 *
 * Features:
 * - Auto-scroll to latest log
 * - Filter by level (all, debug, info, warning, error)
 * - Color-coded log levels
 * - Timestamps
 *
 * Port of src/ui/tui/widgets/log_panel.py
 */

import { useState, useCallback, useEffect, useRef } from "react";
import { useKeyboard } from "@opentui/react";

import type { LogItem, LogEntry, TruncationMarker } from "../protocol/state";
import type { LogLevel } from "../protocol/events";

/** Log level colors */
const LEVEL_COLORS: Record<LogLevel, string> = {
  DEBUG: "#6B7280",   // gray
  INFO: "#FFFFFF",    // white
  WARNING: "#F59E0B", // yellow
  ERROR: "#EF4444",   // red
};

/** Log level filtering order */
const LEVEL_ORDER: LogLevel[] = ["DEBUG", "INFO", "WARNING", "ERROR"];

export interface LogPanelProps {
  logs: LogItem[];
  /** Maximum logs to display */
  maxDisplay?: number;
}

/**
 * Check if item is a truncation marker.
 */
function isTruncationMarker(item: LogItem): item is TruncationMarker {
  return "truncated" in item && item.truncated === true;
}

/**
 * Format timestamp for display (HH:MM:SS).
 */
function formatTimestamp(ts: number): string {
  const date = new Date(ts * 1000);
  return date.toLocaleTimeString("en-US", {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

/**
 * Log panel component.
 */
export function LogPanel({ logs, maxDisplay = 100 }: LogPanelProps) {
  const [filterLevel, setFilterLevel] = useState<LogLevel>("DEBUG");
  const [autoScroll, setAutoScroll] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchMode, setSearchMode] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Filter logs based on level and search query
  const filteredLogs = logs.filter((item) => {
    if (isTruncationMarker(item)) return true;

    const entry = item as LogEntry;
    const levelIndex = LEVEL_ORDER.indexOf(entry.level);
    const filterIndex = LEVEL_ORDER.indexOf(filterLevel);
    const levelMatch = levelIndex >= filterIndex;

    if (!levelMatch) return false;

    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      return entry.message.toLowerCase().includes(query) ||
             entry.logger.toLowerCase().includes(query);
    }

    return true;
  });

  // Get last N logs for display
  const displayLogs = filteredLogs.slice(-maxDisplay);

  // Auto-scroll effect
  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [displayLogs.length, autoScroll]);

  const cycleFilterLevel = useCallback((direction: 1 | -1) => {
    setFilterLevel((current) => {
      const idx = LEVEL_ORDER.indexOf(current);
      const newIdx = (idx + direction + LEVEL_ORDER.length) % LEVEL_ORDER.length;
      return LEVEL_ORDER[newIdx];
    });
  }, []);

  const toggleAutoScroll = useCallback(() => {
    setAutoScroll((current) => !current);
  }, []);

  useKeyboard((key) => {
    if (searchMode) {
      if (key.name === "escape") {
        setSearchMode(false);
        setSearchQuery("");
      } else if (key.name === "return" || key.name === "enter") {
        setSearchMode(false);
      } else if (key.name === "backspace") {
        setSearchQuery((q) => q.slice(0, -1));
      } else if (key.sequence && key.sequence.length === 1 && !key.ctrl && !key.meta) {
        setSearchQuery((q) => q + key.sequence);
      }
      return;
    }

    if (key.name === "g" || key.name === "G") {
      toggleAutoScroll();
    } else if (key.sequence === "/" || key.name === "f" || key.name === "F") {
      setSearchMode(true);
    } else if (key.name === "d" || key.name === "D") {
      setFilterLevel("DEBUG");
    } else if (key.name === "i" || key.name === "I") {
      setFilterLevel("INFO");
    } else if (key.name === "w" || key.name === "W") {
      setFilterLevel("WARNING");
    } else if (key.name === "e" || key.name === "E") {
      setFilterLevel("ERROR");
    } else if (key.name === "left") {
      cycleFilterLevel(-1);
    } else if (key.name === "right") {
      cycleFilterLevel(1);
    }
  });

  return (
    <box style={{ flexDirection: "column", height: "100%", width: "100%" }}>
      <box
        style={{
          flexDirection: "row",
          height: 1,
          gap: 2,
          marginBottom: 1,
          paddingLeft: 1,
        }}
      >
        {searchMode ? (
          <>
            <text fg="#0EA5E9">Search:</text>
            <text fg="#FFFFFF">{searchQuery}_</text>
            <text fg="#6B7280">[Enter] Done [Esc] Clear</text>
          </>
        ) : (
          <>
            <text fg="#6B7280">Filter:</text>
            {LEVEL_ORDER.map((level) => (
              <text
                key={level}
                fg={filterLevel === level ? LEVEL_COLORS[level] : "#4B5563"}
              >
                {filterLevel === level ? <b>[{level[0]}]{level.slice(1).toLowerCase()}</b> : `[${level[0]}]${level.slice(1).toLowerCase()}`}
              </text>
            ))}
            <text
              fg={autoScroll ? "#10B981" : "#6B7280"}
              style={{ marginLeft: 2 }}
            >
              [G] {autoScroll ? "ON" : "OFF"}
            </text>
            <text fg="#6B7280">[/] Search</text>
            {searchQuery && (
              <text fg="#0EA5E9">"{searchQuery}"</text>
            )}
          </>
        )}
      </box>

      {/* Log entries */}
      <scrollbox
        ref={scrollRef as any}
        style={{
          flexGrow: 1,
          flexDirection: "column",
          paddingLeft: 1,
        }}
      >
        {displayLogs.length === 0 ? (
          <text fg="#6B7280">No logs to display</text>
        ) : (
          displayLogs.map((item, index) => {
            if (isTruncationMarker(item)) {
              return (
                <box key={`truncation-${index}`} style={{ flexDirection: "row" }}>
                  <text fg="#6B7280">--:--:--</text>
                  <text fg="#F59E0B" style={{ marginLeft: 1 }}>
                    SKIP
                  </text>
                  <text fg="#6B7280" style={{ marginLeft: 1 }}>
                    ... {item.count} entries truncated ...
                  </text>
                </box>
              );
            }

            const entry = item as LogEntry;
            return (
              <box key={`log-${index}`} style={{ flexDirection: "row" }}>
                <text fg="#6B7280" style={{ width: 10 }}>
                  {formatTimestamp(entry.timestamp)}
                </text>
                <text fg={LEVEL_COLORS[entry.level]} style={{ width: 8 }}>
                  {entry.level.padEnd(7)}
                </text>
                <text fg="#FFFFFF">
                  {entry.message.length > 120
                    ? entry.message.slice(0, 117) + "..."
                    : entry.message}
                </text>
              </box>
            );
          })
        )}
      </scrollbox>
    </box>
  );
}
