/**
 * Root application component.
 *
 * Manages the screen stack and renders the current screen.
 */

import { useCallback, useEffect, useState } from "react";
import { useKeyboard } from "@opentui/react";

import { getIpcClient } from "../ipc/client";
import { useStore } from "../state/store";
import {
  RunScreen,
  HomeScreen,
  SettingsScreen,
  HelpScreen,
  ThemeSelectorScreen,
} from "../screens";
import { QuickRunModal, ProviderHealth } from "../components";

/** Screen identifiers */
type ScreenId =
  | "welcome"
  | "home"
  | "config"
  | "run"
  | "settings"
  | "help"
  | "theme_selector";

/** Run configuration passed to Run screen */
interface RunConfig {
  inputPath: string | null;
  config: {
    output_dir: string;
    quality?: string;
    language?: string;
    provider?: string;
    analysis_style?: string;
    url?: string;
  };
}

/**
 * Welcome screen - landing page with quick start options.
 */
function WelcomeScreen({
  onStartRun,
  onConfig,
  onHelp,
  onQuit,
}: {
  onStartRun: () => void;
  onConfig: () => void;
  onHelp: () => void;
  onQuit: () => void;
}) {
  useKeyboard((key) => {
    if (key.name === "return" || key.name === "enter") {
      onStartRun();
    } else if (key.name === "c" || key.name === "C") {
      onConfig();
    } else if (key.name === "h" || key.name === "H" || key.sequence === "?") {
      onHelp();
    } else if (key.name === "q" || key.name === "Q") {
      onQuit();
    }
  });

  return (
    <box
      style={{
        width: "100%",
        height: "100%",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: 1,
      }}
    >
      <box
        style={{
          flexDirection: "column",
          alignItems: "center",
          width: 64,
        }}
      >
        <box style={{ flexDirection: "column", alignItems: "center", marginBottom: 1 }}>
          <text fg="#0EA5E9">{"    _   _   _ ____ ___ ___  "}</text>
          <text fg="#0EA5E9">{"   / \\ | | | |  _ \\_ _/ _ \\ "}</text>
          <text fg="#0EA5E9">{"  / _ \\| | | | | | | | | | |"}</text>
          <text fg="#0EA5E9">{" / ___ \\ |_| | |_| | | |_| |"}</text>
          <text fg="#0EA5E9">{"/_/   \\_\\___/|____/___\\___/ "}</text>
        </box>

        <text fg="#F8FAFC">
          <b>Audio Extraction Analysis</b>
        </text>
        <text fg="#64748B" style={{ marginBottom: 2 }}>
          Transform recordings into structured documentation
        </text>

        <box
          style={{
            border: true,
            borderStyle: "rounded",
            padding: 1,
            width: "100%",
            flexDirection: "column",
            marginBottom: 1,
          }}
        >
          <box style={{ flexDirection: "row", marginBottom: 1 }}>
            <box
              style={{
                border: true,
                borderStyle: "rounded",
                padding: 1,
                flexDirection: "column",
                alignItems: "center",
                width: 28,
              }}
            >
              <text fg="#10B981">
                <b>{"[ Enter ]"}</b>
              </text>
              <text fg="#F8FAFC">Quick Start</text>
              <text fg="#64748B">Process a file or URL</text>
            </box>

            <box style={{ width: 2 }} />

            <box
              style={{
                border: true,
                borderStyle: "rounded",
                padding: 1,
                flexDirection: "column",
                alignItems: "center",
                width: 28,
              }}
            >
              <text fg="#0EA5E9">
                <b>{"[   C   ]"}</b>
              </text>
              <text fg="#F8FAFC">Configure</text>
              <text fg="#64748B">Settings & options</text>
            </box>
          </box>

          <box style={{ flexDirection: "row" }}>
            <box
              style={{
                border: true,
                borderStyle: "rounded",
                padding: 1,
                flexDirection: "column",
                alignItems: "center",
                width: 28,
              }}
            >
              <text fg="#F59E0B">
                <b>{"[   H   ]"}</b>
              </text>
              <text fg="#F8FAFC">Help</text>
              <text fg="#64748B">Keyboard shortcuts</text>
            </box>

            <box style={{ width: 2 }} />

            <box
              style={{
                border: true,
                borderStyle: "rounded",
                padding: 1,
                flexDirection: "column",
                alignItems: "center",
                width: 28,
              }}
            >
              <text fg="#6B7280">
                <b>{"[   Q   ]"}</b>
              </text>
              <text fg="#F8FAFC">Quit</text>
              <text fg="#64748B">Exit application</text>
            </box>
          </box>
        </box>

        <box
          style={{
            border: true,
            borderStyle: "rounded",
            padding: 1,
            width: "100%",
            flexDirection: "column",
          }}
        >
          <text fg="#64748B" style={{ marginBottom: 1 }}>
            <b>PROVIDERS</b>
          </text>
          <ProviderHealth compact />
        </box>

        <box style={{ marginTop: 1, flexDirection: "row", gap: 2 }}>
          <text fg="#475569">v1.0</text>
          <text fg="#334155">{"│"}</text>
          <text fg="#475569">Ctrl+C to exit</text>
        </box>
      </box>
    </box>
  );
}

/**
 * Simple config screen for demo - collects input path and output dir.
 */
function ConfigScreen({
  onBack,
  onStartRun,
}: {
  onBack: () => void;
  onStartRun: (config: RunConfig) => void;
}) {
  const state = useStore();

  const handleStart = useCallback(() => {
    const url = state.pendingRunConfig?.url as string | undefined;
    onStartRun({
      inputPath: state.inputPath,
      config: {
        output_dir: state.outputDir ?? "/tmp/output",
        quality: state.quality,
        language: state.language,
        provider: state.provider,
        analysis_style: state.analysisStyle,
        url,
      },
    });
  }, [state, onStartRun]);

  useKeyboard((key) => {
    if (key.name === "return" || key.name === "enter") {
      handleStart();
    } else if (key.name === "escape") {
      onBack();
    }
  });

  return (
    <box
      title="Configure Pipeline"
      style={{
        border: true,
        width: "100%",
        height: "100%",
        flexDirection: "column",
        padding: 2,
      }}
    >
      <text fg="#0EA5E9" style={{ marginBottom: 2 }}>
        <b>Pipeline Configuration</b>
      </text>

      <box style={{ flexDirection: "column", gap: 1, marginBottom: 2 }}>
        <box style={{ flexDirection: "row" }}>
          <text fg="#9CA3AF" style={{ width: 15 }}>Input:</text>
          <text fg="#FFFFFF">
            {state.inputPath ?? (state.pendingRunConfig?.url as string) ?? "(none selected)"}
          </text>
        </box>

        <box style={{ flexDirection: "row" }}>
          <text fg="#9CA3AF" style={{ width: 15 }}>Output Dir:</text>
          <text fg="#FFFFFF">{state.outputDir ?? "/tmp/output"}</text>
        </box>

        <box style={{ flexDirection: "row" }}>
          <text fg="#9CA3AF" style={{ width: 15 }}>Quality:</text>
          <text fg="#FFFFFF">{state.quality}</text>
        </box>

        <box style={{ flexDirection: "row" }}>
          <text fg="#9CA3AF" style={{ width: 15 }}>Language:</text>
          <text fg="#FFFFFF">{state.language}</text>
        </box>

        <box style={{ flexDirection: "row" }}>
          <text fg="#9CA3AF" style={{ width: 15 }}>Provider:</text>
          <text fg="#FFFFFF">{state.provider}</text>
        </box>

        <box style={{ flexDirection: "row" }}>
          <text fg="#9CA3AF" style={{ width: 15 }}>Analysis:</text>
          <text fg="#FFFFFF">{state.analysisStyle}</text>
        </box>
      </box>

      <box style={{ flexDirection: "row", gap: 3, marginTop: 2 }}>
        <text fg="#10B981">
          [Enter] Start Pipeline
        </text>

        <text fg="#6B7280">
          [Esc] Back
        </text>
      </box>
    </box>
  );
}

/**
 * Root application component.
 */
export function App() {
  const [screenStack, setScreenStack] = useState<ScreenId[]>(["welcome"]);
  const [runConfig, setRunConfig] = useState<RunConfig | null>(null);
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [pendingConfig, setPendingConfig] = useState<RunConfig | null>(null);
  const applyEvent = useStore((state) => state.applyEvent);

  const currentScreen = screenStack[screenStack.length - 1];

  // Subscribe to backend events
  useEffect(() => {
    const client = getIpcClient();

    const unsubscribe = client.onEvent((event) => {
      applyEvent(event);
    });

    return unsubscribe;
  }, [applyEvent]);

  // Navigation functions
  const push = useCallback((screen: ScreenId) => {
    setScreenStack((stack) => [...stack, screen]);
  }, []);

  const pop = useCallback(() => {
    setScreenStack((stack) => {
      if (stack.length > 1) {
        return stack.slice(0, -1);
      }
      return stack;
    });
  }, []);

  const replace = useCallback((screen: ScreenId) => {
    setScreenStack((stack) => [...stack.slice(0, -1), screen]);
  }, []);

  const handleRequestRun = useCallback((config: RunConfig) => {
    setPendingConfig(config);
    setShowConfirmModal(true);
  }, []);

  const handleConfirmRun = useCallback(() => {
    if (pendingConfig) {
      setRunConfig(pendingConfig);
      setShowConfirmModal(false);
      setPendingConfig(null);
      push("run");
    }
  }, [pendingConfig, push]);

  const handleCancelRun = useCallback(() => {
    setShowConfirmModal(false);
    setPendingConfig(null);
  }, []);

  const handleQuickStart = useCallback(() => {
    push("home");
  }, [push]);

  const setInputPath = useStore((s) => s.setInputPath);
  const setPendingRunConfig = useStore((s) => s.setPendingRunConfig);

  const handleSelectFile = useCallback((path: string) => {
    setInputPath(path);
    setPendingRunConfig(null);
    push("config");
  }, [push, setInputPath, setPendingRunConfig]);

  const handleSelectUrl = useCallback((url: string) => {
    setInputPath(null);
    setPendingRunConfig({ url });
    push("config");
  }, [push, setInputPath, setPendingRunConfig]);

  const handleRunComplete = useCallback((outputDir: string) => {
    console.log(`Pipeline complete: ${outputDir}`);
  }, []);

  const handleQuit = useCallback(() => {
    process.exit(0);
  }, []);

  const handleThemeSelect = useCallback(async (themeName: string) => {
    try {
      const client = getIpcClient();
      await client.call("settings.update", { key: "theme", value: themeName });
      pop();
    } catch (err) {
      console.error("Failed to save theme:", err);
      pop();
    }
  }, [pop]);

  // Render current screen
  switch (currentScreen) {
    case "welcome":
      return (
        <WelcomeScreen
          onStartRun={handleQuickStart}
          onConfig={handleQuickStart}
          onHelp={() => push("help")}
          onQuit={handleQuit}
        />
      );

    case "home":
      return (
        <HomeScreen
          onSelectFile={handleSelectFile}
          onSelectUrl={handleSelectUrl}
          onSettings={() => push("settings")}
          onBack={pop}
        />
      );

    case "config":
      return (
        <>
          <ConfigScreen
            onBack={pop}
            onStartRun={handleRequestRun}
          />
          {showConfirmModal && pendingConfig && (
            <QuickRunModal
              inputPath={pendingConfig.inputPath}
              url={pendingConfig.config.url ?? null}
              outputDir={pendingConfig.config.output_dir}
              quality={pendingConfig.config.quality ?? "speech"}
              provider={pendingConfig.config.provider ?? "auto"}
              onConfirm={handleConfirmRun}
              onCancel={handleCancelRun}
            />
          )}
        </>
      );

    case "run":
      if (!runConfig) {
        pop();
        return null;
      }
      return (
        <RunScreen
          inputPath={runConfig.inputPath}
          config={runConfig.config}
          onBack={pop}
          onComplete={handleRunComplete}
        />
      );

    case "settings":
      return (
        <SettingsScreen
          onBack={pop}
          onThemes={() => push("theme_selector")}
        />
      );

    case "help":
      return <HelpScreen onBack={pop} />;

    case "theme_selector":
      return (
        <ThemeSelectorScreen
          onBack={pop}
          onSelect={handleThemeSelect}
        />
      );

    default:
      // Placeholder for unimplemented screens
      return (
        <box
          title={`Screen: ${currentScreen}`}
          style={{
            border: true,
            width: "100%",
            height: "100%",
            flexDirection: "column",
            padding: 2,
          }}
        >
          <text fg="#F59E0B" style={{ marginBottom: 2 }}>
            Screen not implemented: {currentScreen}
          </text>

          <text fg="#6B7280">
            [Esc] Back
          </text>
        </box>
      );
  }
}
