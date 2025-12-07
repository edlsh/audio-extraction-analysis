# Event Model Notes

The CLI no longer emits JSONL event streams. Pipeline events are used internally by the Textual TUI via an in-process queue. External streaming/monitoring surfaces are disabled until a supported interface is reintroduced.

