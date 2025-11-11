# Architecture Decision Records (ADRs)

This directory contains Architecture Decision Records (ADRs) documenting significant architectural and design decisions made in the audio-extraction-analysis project.

## What is an ADR?

An Architecture Decision Record (ADR) captures an important architectural decision made along with its context and consequences. ADRs help teams:
- Understand why decisions were made
- Onboard new team members
- Avoid revisiting settled decisions
- Learn from past choices

## Format

Each ADR follows this structure:
- **Status**: Proposed, Accepted, Deprecated, Superseded
- **Date**: When the decision was made
- **Context**: Problem statement and background
- **Decision**: What was decided and why
- **Consequences**: Positive and negative outcomes

## Active ADRs

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| [001](001-provider-factory-architecture.md) | Provider Factory Architecture | Accepted | 2025-11-11 |

## Creating New ADRs

1. Create a new file: `NNN-short-title.md` (e.g., `002-caching-strategy.md`)
2. Use the existing ADRs as templates
3. Update this index
4. Commit with message: `docs: Add ADR NNN - Short Title`

## ADR Lifecycle

- **Proposed** → Under discussion
- **Accepted** → Implemented and active
- **Deprecated** → No longer recommended
- **Superseded** → Replaced by a newer ADR

## References

- ADR process: https://adr.github.io/
- ADR tools: https://github.com/npryce/adr-tools
