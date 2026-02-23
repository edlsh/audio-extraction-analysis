import { afterEach, describe, expect, it } from "bun:test";

import {
  resolveDefaultBackendCommand,
  resolveDefaultBackendCwd,
} from "./client";

const ORIGINAL_ENV = { ...process.env };

afterEach(() => {
  process.env = { ...ORIGINAL_ENV };
});

describe("resolveDefaultBackendCommand", () => {
  it("prefers AUDIO_ANALYSIS_PYTHON when set", () => {
    process.env.AUDIO_ANALYSIS_PYTHON = "/custom/python";
    process.env.PYTHON = "/fallback/python";

    expect(resolveDefaultBackendCommand()).toBe("/custom/python");
  });

  it("falls back to PYTHON env var", () => {
    delete process.env.AUDIO_ANALYSIS_PYTHON;
    process.env.PYTHON = "/usr/bin/python3";

    expect(resolveDefaultBackendCommand()).toBe("/usr/bin/python3");
  });

  it("defaults to python3", () => {
    delete process.env.AUDIO_ANALYSIS_PYTHON;
    delete process.env.PYTHON;

    expect(resolveDefaultBackendCommand()).toBe("python3");
  });
});

describe("resolveDefaultBackendCwd", () => {
  it("uses PROJECT_ROOT when present", () => {
    process.env.PROJECT_ROOT = "/tmp/project-root";
    expect(resolveDefaultBackendCwd()).toBe("/tmp/project-root");
  });

  it("falls back to parent directory", () => {
    delete process.env.PROJECT_ROOT;
    expect(resolveDefaultBackendCwd()).toBe("..");
  });
});
