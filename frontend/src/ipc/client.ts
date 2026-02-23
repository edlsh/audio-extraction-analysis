/**
 * JSON-RPC 2.0 client for communicating with the Python backend over stdio.
 */

import type {
  JsonRpcRequest,
  JsonRpcResponse,
  JsonRpcError,
  RpcMethods,
  RpcMethod,
} from "../protocol/commands";
import type { Event, EventNotification } from "../protocol/events";

/** Client configuration */
export interface IpcClientConfig {
  /** Path to the Python backend executable */
  backendCommand: string;
  /** Arguments to pass to the backend */
  backendArgs: string[];
  /** Working directory for the backend process */
  cwd: string;
  /** Request timeout in milliseconds */
  timeout: number;
  /** Enable debug logging */
  debug: boolean;
}

const DEFAULT_CONFIG: IpcClientConfig = {
  backendCommand: "python",
  backendArgs: ["-m", "src.ui.opentui_backend"],
  cwd: "..",
  timeout: 30000,
  debug: false,
};

/** Pending request tracking */
interface PendingRequest<T> {
  resolve: (result: T) => void;
  reject: (error: Error) => void;
  timeout: ReturnType<typeof setTimeout>;
}

/** Event handler type */
export type EventHandler = (event: Event) => void;

/**
 * IPC client for JSON-RPC 2.0 communication with the Python backend.
 */
export class IpcClient {
  private config: IpcClientConfig;
  private process: ReturnType<typeof Bun.spawn> | null = null;
  private nextId = 1;
  private pendingRequests = new Map<number | string, PendingRequest<unknown>>();
  private eventHandlers = new Set<EventHandler>();
  private buffer = "";
  private connected = false;

  constructor(config: Partial<IpcClientConfig> = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config };
  }

  /**
   * Start the backend process and establish connection.
   */
  async connect(): Promise<void> {
    if (this.connected) {
      throw new Error("Already connected");
    }

    this.log("Starting backend process...");

    this.process = Bun.spawn([this.config.backendCommand, ...this.config.backendArgs], {
      stdin: "pipe",
      stdout: "pipe",
      stderr: "pipe",
      cwd: this.config.cwd,
    });

    // Read stdout for responses and notifications
    this.readStdout();

    // Read stderr for debug logs
    this.readStderr();

    this.connected = true;
    this.log("Backend connected");
  }

  /**
   * Disconnect from the backend.
   */
  async disconnect(): Promise<void> {
    if (!this.connected) {
      return;
    }

    this.log("Disconnecting...");

    // Cancel all pending requests
    for (const [id, pending] of this.pendingRequests) {
      clearTimeout(pending.timeout);
      pending.reject(new Error("Client disconnected"));
    }
    this.pendingRequests.clear();

    // Kill the backend process
    if (this.process) {
      this.process.kill();
      this.process = null;
    }

    this.connected = false;
    this.log("Disconnected");
  }

  /**
   * Check if connected to the backend.
   */
  isConnected(): boolean {
    return this.connected;
  }

  /**
   * Send a typed RPC request and wait for the response.
   */
  async call<M extends RpcMethod>(
    method: M,
    params: RpcMethods[M]["params"]
  ): Promise<RpcMethods[M]["result"]> {
    if (!this.connected || !this.process) {
      throw new Error("Not connected to backend");
    }

    const id = this.nextId++;
    const request: JsonRpcRequest = {
      jsonrpc: "2.0",
      id,
      method,
      params,
    };

    return new Promise((resolve, reject) => {
      // Set up timeout
      const timeout = setTimeout(() => {
        this.pendingRequests.delete(id);
        reject(new Error(`Request timeout: ${method}`));
      }, this.config.timeout);

      // Track pending request
      this.pendingRequests.set(id, {
        resolve: resolve as (result: unknown) => void,
        reject,
        timeout,
      });

      // Send request
      this.sendMessage(request);
    });
  }

  /**
   * Register an event handler.
   */
  onEvent(handler: EventHandler): () => void {
    this.eventHandlers.add(handler);
    return () => {
      this.eventHandlers.delete(handler);
    };
  }

  private sendMessage(message: JsonRpcRequest): void {
    const stdin = this.process?.stdin;
    if (!stdin || typeof stdin === "number") {
      throw new Error("No stdin available");
    }

    const json = JSON.stringify(message);
    this.log(`-> ${json}`);

    stdin.write(json + "\n");
  }

  private async readStdout(): Promise<void> {
    const stdout = this.process?.stdout;
    if (!stdout || typeof stdout === "number") {
      return;
    }

    const reader = stdout.getReader();
    const decoder = new TextDecoder();

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          break;
        }

        this.buffer += decoder.decode(value, { stream: true });
        this.processBuffer();
      }
    } catch (error) {
      this.log(`Stdout read error: ${error}`);
    }
  }

  private async readStderr(): Promise<void> {
    const stderr = this.process?.stderr;
    if (!stderr || typeof stderr === "number") {
      return;
    }

    const reader = stderr.getReader();
    const decoder = new TextDecoder();

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          break;
        }

        const text = decoder.decode(value, { stream: true });
        if (this.config.debug) {
          console.error(`[backend] ${text}`);
        }
      }
    } catch (error) {
      this.log(`Stderr read error: ${error}`);
    }
  }

  /**
   * Process buffered input, extracting complete JSON lines.
   */
  private processBuffer(): void {
    const lines = this.buffer.split("\n");
    this.buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (line.trim()) {
        this.handleMessage(line);
      }
    }
  }

  /**
   * Handle a received JSON-RPC message.
   */
  private handleMessage(json: string): void {
    this.log(`<- ${json}`);

    try {
      const message = JSON.parse(json);

      // Check if it's a notification (no id)
      if (message.method && !("id" in message)) {
        this.handleNotification(message);
        return;
      }

      // It's a response
      this.handleResponse(message as JsonRpcResponse);
    } catch (error) {
      this.log(`Failed to parse message: ${error}`);
    }
  }

  /**
   * Handle a JSON-RPC notification.
   */
  private handleNotification(message: { method: string; params?: unknown }): void {
    if (message.method === "event" && message.params) {
      const event = message.params as Event;
      for (const handler of this.eventHandlers) {
        try {
          handler(event);
        } catch (error) {
          this.log(`Event handler error: ${error}`);
        }
      }
    }
  }

  /**
   * Handle a JSON-RPC response.
   */
  private handleResponse(response: JsonRpcResponse): void {
    const pending = this.pendingRequests.get(response.id);
    if (!pending) {
      this.log(`Received response for unknown request: ${response.id}`);
      return;
    }

    this.pendingRequests.delete(response.id);
    clearTimeout(pending.timeout);

    if (response.error) {
      pending.reject(new JsonRpcClientError(response.error));
    } else {
      pending.resolve(response.result);
    }
  }

  /**
   * Log a debug message.
   */
  private log(message: string): void {
    if (this.config.debug) {
      console.log(`[IpcClient] ${message}`);
    }
  }
}

/**
 * Error class for JSON-RPC errors.
 */
export class JsonRpcClientError extends Error {
  code: number;
  data?: unknown;

  constructor(error: JsonRpcError) {
    super(error.message);
    this.name = "JsonRpcClientError";
    this.code = error.code;
    this.data = error.data;
  }
}

/**
 * Create a singleton IPC client instance.
 */
let clientInstance: IpcClient | null = null;

export function getIpcClient(): IpcClient {
  if (!clientInstance) {
    clientInstance = new IpcClient({
      debug: process.env.DEBUG === "true",
    });
  }
  return clientInstance;
}
