/**
 * OpenTUI frontend entry point.
 *
 * This is the main entry point for the OpenTUI-based terminal UI.
 * It initializes the renderer, connects to the Python backend, and
 * renders the root application component.
 */

import { createCliRenderer } from "@opentui/core";
import { createRoot } from "@opentui/react";

import { getIpcClient } from "../ipc/client";
import { App } from "./App";

async function main() {
  // Initialize the IPC client
  const client = getIpcClient();

  try {
    // Connect to the Python backend
    console.log("Connecting to backend...");
    await client.connect();
    console.log("Backend connected!");

    // Create the OpenTUI renderer
    const renderer = await createCliRenderer({
      exitOnCtrlC: false,
      consoleOptions: {
        // Debug console at bottom of screen
        sizePercent: 0,
      },
    });

    // Create React root and render
    const root = createRoot(renderer);
    root.render(<App />);

    // Handle cleanup on exit
    process.on("SIGINT", async () => {
      await client.disconnect();
      process.exit(0);
    });

    process.on("SIGTERM", async () => {
      await client.disconnect();
      process.exit(0);
    });
  } catch (error) {
    console.error("Failed to start:", error);
    await client.disconnect();
    process.exit(1);
  }
}

main();
