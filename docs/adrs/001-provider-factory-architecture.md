# ADR 001: Provider Factory Architecture

**Status:** Accepted  
**Date:** 2025-11-11  
**Context:** Technical debt review of 740-line provider factory

## Context and Problem Statement

The `TranscriptionProviderFactory` is a 740-line class that manages multiple transcription service providers. During technical debt review, it was flagged for potential simplification due to its size.

After analysis, we found:
- **37% documentation** (275 lines of comprehensive docstrings)
- **40.5% actual code** (300 lines of implementation)
- **Only 11 methods** (8 public API, 3 private helpers)
- **Well-structured** with single responsibility per method

**Question:** Is this technical debt requiring refactoring, or well-designed code that should be preserved?

## Decision Drivers

1. **Complexity is inherent** - Managing 4 different providers (Deepgram, ElevenLabs, Whisper, Parakeet) with different APIs, constraints, and behaviors
2. **Comprehensive features** - Health checking, auto-selection, file size validation, circuit breaker pattern
3. **Production stability** - Factory is used throughout the codebase and is well-tested
4. **Documentation quality** - Extensive docstrings aid maintainability and onboarding

## Considered Options

### Option 1: Extract Provider Strategy Pattern
**Approach:** Create separate strategy classes for each provider type
- ✅ More modular
- ❌ Adds complexity with multiple files
- ❌ Makes auto-selection logic harder to understand
- ❌ Doesn't reduce overall line count significantly

### Option 2: Split into Multiple Classes
**Approach:** Separate ProviderRegistry, HealthChecker, AutoSelector
- ✅ Smaller individual classes
- ❌ More files to navigate
- ❌ Breaks cohesion - these concerns are tightly related
- ❌ Adds ceremony without clear benefit

### Option 3: Reduce Documentation Verbosity
**Approach:** Trim docstrings to bare essentials
- ✅ Fewer lines
- ❌ Harms maintainability
- ❌ Reduces onboarding quality
- ❌ Doesn't address actual code complexity

### Option 4: Keep Current Design (CHOSEN)
**Approach:** Recognize this as well-designed code, not technical debt
- ✅ Already follows SOLID principles
- ✅ Each method has single responsibility
- ✅ Private helpers keep complexity manageable
- ✅ Comprehensive documentation aids maintenance
- ✅ Production-tested and stable

## Decision

**We will keep the factory as-is and document the architecture.**

The 740-line size is justified by:
1. **Multiple provider support** - 4 different providers with unique characteristics
2. **Intelligent auto-selection** - Complex heuristics for choosing best provider
3. **Production resilience** - Health checking, circuit breakers, retry logic
4. **Comprehensive documentation** - ~37% of lines are helpful docstrings

This is an example of **appropriate complexity** for the problem domain.

## Architecture Overview

```
TranscriptionProviderFactory (Class)
│
├── Provider Management
│   ├── register_provider()          # Registry management
│   ├── get_available_providers()    # List registered
│   └── get_configured_providers()   # List with valid config
│
├── Provider Creation
│   ├── create_provider()            # Main factory method
│   ├── _get_default_configs()       # Internal: config defaults
│   ├── _create_provider_instance()  # Internal: instantiation
│   └── _run_health_check()          # Internal: validation
│
├── Auto-Selection
│   ├── auto_select_provider()       # Intelligent selection
│   └── validate_provider_for_file() # File size validation
│
└── Health Monitoring
    ├── check_provider_health()      # Async health check
    ├── check_provider_health_sync() # Sync wrapper
    └── get_provider_status()        # Complete status
```

### Design Patterns Used

1. **Factory Pattern** - Centralized creation of provider instances
2. **Registry Pattern** - Dynamic provider registration and discovery
3. **Strategy Pattern** (implicit) - Providers implement common interface
4. **Circuit Breaker** - Fault tolerance for provider calls
5. **Template Method** - Health checking and validation workflows

### Auto-Selection Algorithm

The factory's auto-selection logic considers multiple factors:

1. **Configuration** - Filter to providers with valid credentials
2. **Health Status** - Prefer healthy providers (if enabled)
3. **File Size** - Respect provider constraints (e.g., ElevenLabs 50MB limit)
4. **Feature Requirements** - Match requested features (timestamps, diarization, etc.)
5. **Priority Fallback** - Default order: Deepgram > ElevenLabs > Whisper > Parakeet

This complexity is **necessary** for production reliability and cannot be meaningfully reduced.

## Consequences

### Positive
- ✅ **Maintainability preserved** - Clear structure and comprehensive docs
- ✅ **Production stability** - No changes to tested, working code
- ✅ **Onboarding friendly** - New developers can understand the system
- ✅ **Technical debt clarified** - Size doesn't imply debt

### Negative
- ❌ **Large file remains** - 740 lines in single file (but well-organized)
- ❌ **No quick wins** - Could not identify easy simplifications

### Mitigation
- Create this ADR to document architecture decisions
- Add code map/navigation guide for developers
- Consider IDE folding to manage visual complexity

## Metrics

| Metric | Value | Assessment |
|--------|-------|------------|
| Total lines | 740 | High but justified |
| Documentation | 37% | Excellent |
| Methods | 11 | Reasonable |
| Public API | 8 methods | Clean interface |
| Cyclomatic complexity | Low-Medium | Acceptable |
| Test coverage | High | Well-tested |

## Related Decisions

- ADR 002: Validation Layer Consolidation (completed)
- ADR 003: Configuration Management (in src/config/__init__.py)

## References

- Factory Pattern: https://refactoring.guru/design-patterns/factory-method
- Circuit Breaker Pattern: https://martinfowler.com/bliki/CircuitBreaker.html
- Provider implementations: src/providers/{deepgram,elevenlabs,whisper,parakeet}.py

## Review Cadence

This ADR should be reviewed:
- **When adding new providers** - Assess if pattern still scales
- **After major feature additions** - Check if separation becomes necessary
- **Annually** - Verify design choices remain appropriate

---

**Decision:** Keep factory as-is. Size reflects appropriate complexity, not technical debt.
