# HTML Dashboard Strategy

## Goals

- Provide an accessible, single-page summary of pipeline results (metadata,
  transcript highlights, analytics) for stakeholders who prefer a visual
  overview over raw Markdown files.
- Keep generation optional behind the `--html-dashboard` flag surfaced through
  the CLI (and wizard) so existing workflows remain unchanged.
- Ensure assets remain fully static so they can be shared via email or hosted
  from object storage without a backend.

## Architecture

1. **Template Engine** – Use Jinja2 templates located under
   `src/formatters/html/`. Provide a base layout that includes inline CSS for
   dark/light friendly rendering and additional partials for timeline/metrics
   sections.
2. **Rendering Service** – Add a `HtmlDashboardRenderer` helper in the same
   package responsible for:
   - Loading templates with a sandboxed environment (autoescaping, limited
     filters).
   - Normalising pipeline data (e.g., durations, provider metadata,
     Markdown hyperlinks) into a template context.
   - Writing the final HTML file to `<output_dir>/dashboard/index.html`.
3. **Data Sources** – Reuse existing structures from the pipeline:
   - `TranscriptionResult` (chapters, speakers, summary, topics, sentiment).
   - Stage timings from `process_pipeline` results (`stage_results`).
   - File manifest from `_handle_process_success` for download links.
4. **Integration Points** – Extend `_handle_process_success` so that when
   `args.html_dashboard` is truthy it calls the renderer with the gathered
   context. Ensure errors surface a warning but do not abort the pipeline.

## Output

- Directory: `<output_dir>/html-dashboard/` containing `index.html` plus a
  lightweight `assets/` folder for CSS (generated alongside the template).
- Link the generated HTML from wizard summary and CLI logs for discoverability.

## Follow-up Validation

- Unit tests covering context shaping and template rendering with a small
  synthetic result payload.
- Snapshot/E2E tests comparing the HTML output against fixture golden files,
  ignoring timestamps via normalisation helpers.
- Documentation updates: screenshots embedded into `docs/EXAMPLES.md` and
  CLI usage instructions referencing the new flag.
