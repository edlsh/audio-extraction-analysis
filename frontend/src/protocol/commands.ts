/**
 * Command types for frontend-to-backend JSON-RPC requests.
 *
 * These define the RPC methods available for the frontend to call.
 */

import type { LogLevel, Stage, StageStatus } from "./events";

// ============================================================================
// Pipeline Commands
// ============================================================================

export interface PipelineStartParams {
  input_path?: string;
  url?: string;
  output_dir: string;
  quality: "speech" | "music" | "high";
  language: string;
  provider: string;
  analysis_style: "concise" | "full";
  keep_downloaded_videos?: boolean;
}

export interface PipelineStartResult {
  run_id: string;
}

export interface PipelineCancelParams {
  run_id: string;
}

export interface PipelineCancelResult {
  success: boolean;
}

export interface PipelineStatusParams {
  run_id: string;
}

export interface PipelineStatusResult {
  is_running: boolean;
  current_stage?: Stage;
  progress: number;
}

// ============================================================================
// Settings Commands
// ============================================================================

export interface SettingsGetParams {}

export interface SettingsData {
  version: string;
  last_input_dir?: string;
  last_output_dir?: string;
  defaults: {
    quality: string;
    language: string;
    provider: string;
    analysis_style: string;
    keep_downloaded_videos: boolean;
  };
  exports: {
    markdown: boolean;
    html: boolean;
  };
  ui: {
    theme: string;
    verbose_logs: boolean;
    log_panel_height: number;
  };
  api_keys: {
    deepgram?: string;
    elevenlabs?: string;
    gemini?: string;
  };
}

export interface SettingsGetResult {
  settings: SettingsData;
}

export interface SettingsUpdateParams {
  key: string;
  value: unknown;
}

export interface SettingsUpdateResult {
  success: boolean;
}

// ============================================================================
// Recent Files Commands
// ============================================================================

export interface RecentListParams {
  max_entries?: number;
}

export interface RecentFile {
  path: string;
  size_mb: number;
  last_used: string;
}

export interface RecentListResult {
  files: RecentFile[];
}

export interface RecentAddParams {
  path: string;
}

export interface RecentAddResult {
  success: boolean;
}

export interface RecentClearParams {}

export interface RecentClearResult {
  success: boolean;
}

// ============================================================================
// Provider Commands
// ============================================================================

export interface ProvidersHealthParams {}

export interface ProviderHealth {
  name: string;
  available: boolean;
  reason?: string;
}

export interface ProvidersHealthResult {
  providers: ProviderHealth[];
}

// ============================================================================
// Theme Commands
// ============================================================================

export interface ThemesCatalogParams {}

export interface ThemeDefinition {
  name: string;
  dark: boolean;
  primary: string;
  secondary: string;
  accent: string;
  background: string;
  foreground: string;
  surface: string;
  panel: string;
  success: string;
  warning: string;
  error: string;
}

export interface ThemesCatalogResult {
  themes: ThemeDefinition[];
  default_theme: string;
  categories: Record<string, string[]>;
}

// ============================================================================
// System Commands
// ============================================================================

export interface SystemOpenPathParams {
  path: string;
}

export interface SystemOpenPathResult {
  success: boolean;
}

export interface SystemListDirParams {
  path: string;
  filter?: string;
}

export interface DirEntry {
  name: string;
  path: string;
  is_dir: boolean;
  size_bytes?: number;
}

export interface SystemListDirResult {
  entries: DirEntry[];
  parent?: string;
}

export interface SystemPingParams {}

export interface SystemPingResult {
  pong: boolean;
}

// ============================================================================
// JSON-RPC Types
// ============================================================================

export interface JsonRpcRequest<T = unknown> {
  jsonrpc: "2.0";
  id: number | string;
  method: string;
  params: T;
}

export interface JsonRpcResponse<T = unknown> {
  jsonrpc: "2.0";
  id: number | string;
  result?: T;
  error?: JsonRpcError;
}

export interface JsonRpcError {
  code: number;
  message: string;
  data?: unknown;
}

/** Standard JSON-RPC error codes */
export const JsonRpcErrorCodes = {
  PARSE_ERROR: -32700,
  INVALID_REQUEST: -32600,
  METHOD_NOT_FOUND: -32601,
  INVALID_PARAMS: -32602,
  INTERNAL_ERROR: -32603,
  // Custom application error codes (reserved: -32000 to -32099)
  PIPELINE_ERROR: -32000,
  SETTINGS_ERROR: -32001,
  PROVIDER_ERROR: -32002,
  FILE_ERROR: -32003,
} as const;

// ============================================================================
// Method Registry
// ============================================================================

/** All available RPC methods with their param/result types */
export interface RpcMethods {
  "pipeline.start": {
    params: PipelineStartParams;
    result: PipelineStartResult;
  };
  "pipeline.cancel": {
    params: PipelineCancelParams;
    result: PipelineCancelResult;
  };
  "pipeline.status": {
    params: PipelineStatusParams;
    result: PipelineStatusResult;
  };
  "settings.get": {
    params: SettingsGetParams;
    result: SettingsGetResult;
  };
  "settings.update": {
    params: SettingsUpdateParams;
    result: SettingsUpdateResult;
  };
  "recent.list": {
    params: RecentListParams;
    result: RecentListResult;
  };
  "recent.add": {
    params: RecentAddParams;
    result: RecentAddResult;
  };
  "recent.clear": {
    params: RecentClearParams;
    result: RecentClearResult;
  };
  "providers.health": {
    params: ProvidersHealthParams;
    result: ProvidersHealthResult;
  };
  "themes.catalog": {
    params: ThemesCatalogParams;
    result: ThemesCatalogResult;
  };
  "system.openPath": {
    params: SystemOpenPathParams;
    result: SystemOpenPathResult;
  };
  "system.listDir": {
    params: SystemListDirParams;
    result: SystemListDirResult;
  };
  "system.ping": {
    params: SystemPingParams;
    result: SystemPingResult;
  };
}

export type RpcMethod = keyof RpcMethods;
