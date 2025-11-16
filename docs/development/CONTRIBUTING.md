# Contributing to Audio Extraction Analysis

Thank you for your interest in contributing to the Audio Extraction Analysis project! This guide will help you get started with development.

## 📋 Table of Contents

- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Project Structure](#project-structure)
- [Testing](#testing)
- [Code Quality](#code-quality)
- [Submitting Changes](#submitting-changes)

## 🚀 Getting Started

### Prerequisites

- Python 3.8 or higher
- FFmpeg installed on your system
- Git for version control
- Graphite (`gt`) CLI for stacked PRs (optional but recommended)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/edlsh/audio-extraction-analysis.git
cd audio-extraction-analysis
```

2. Install the package in editable mode with development dependencies:
```bash
uv sync --dev
```

3. Install pre-commit hooks:
```bash
pre-commit install
```

4. (Optional) Initialize Graphite for stacked PRs:
```bash
gt init
```

## 🔄 Development Workflow

This project uses **stacked PRs** via Graphite (`gt`) for efficient code review. See the [AGENTS.md](../../AGENTS.md) file for detailed workflow instructions.

### Quick Workflow

1. **Create a feature branch**:
```bash
gt create -m "feat: your feature description"
```

2. **Make your changes and test**:
```bash
pytest
black src/ tests/
ruff check src tests
```

3. **Submit your changes**:
```bash
gt submit --no-interactive
```

### Commit Message Format

Follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` New feature
- `fix:` Bug fix
- `refactor:` Code refactoring
- `test:` Adding or updating tests
- `docs:` Documentation changes
- `ci:` CI/CD changes
- `chore:` Maintenance tasks

## 📂 Project Structure

```
audio-extraction-analysis/
├── benchmarks/          # Performance benchmarks
├── docs/                # Documentation
│   ├── development/     # Development guides (you are here)
│   ├── architecture/    # Architecture decisions
│   └── api/             # API documentation
├── examples/            # Usage examples
├── scripts/             # Development/CI scripts
├── src/                 # Main package source
│   ├── analysis/        # Transcript analysis
│   ├── cache/           # Caching infrastructure
│   ├── config/          # Configuration management
│   ├── formatters/      # Output formatters
│   ├── models/          # Data models
│   ├── pipeline/        # Processing pipelines
│   ├── providers/       # Transcription providers
│   ├── services/        # Core business logic
│   ├── ui/              # User interface components
│   └── utils/           # Utilities
├── tests/               # All tests
│   ├── benchmarks/      # Benchmark tests
│   ├── cache/           # Cache tests
│   ├── e2e/             # End-to-end tests
│   ├── integration/     # Integration tests
│   ├── security/        # Security tests
│   ├── unit/            # Unit tests
│   └── verification/    # Verification scripts
└── tools/               # Development tools

RUNTIME (gitignored):
├── cache/               # Runtime cache directory
├── logs/                # Application logs
├── output/              # CLI output
└── reports/             # Test reports
```

See component-specific `AGENTS.md` files in each directory for detailed guidance.

## 🧪 Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html --cov-report=term

# Run specific test categories
pytest tests/unit/
pytest tests/integration/
pytest tests/e2e/

# Run security tests
pytest tests/security/
```

### Test Organization

- **Unit tests** (`tests/unit/`): Test individual functions/classes
- **Integration tests** (`tests/integration/`): Test component interactions
- **E2E tests** (`tests/e2e/`): Test complete workflows
- **Security tests** (`tests/security/`): Security-specific tests
- **Benchmark tests** (`tests/benchmarks/`): Performance benchmarks

## ✅ Code Quality

### Pre-commit Checks

The project uses pre-commit hooks to ensure code quality:

```bash
# Run all pre-commit hooks manually
pre-commit run --all-files
```

### Static Analysis

```bash
# Run the full static analysis suite
./scripts/run_static_checks.sh
```

This includes:
- **Black**: Code formatting
- **Ruff**: Linting
- **Bandit**: Security analysis
- **pip-audit**: Dependency security
- **detect-secrets**: Secret scanning
- **import-linter**: Architecture validation

### Code Style

- **Line length**: 100 characters (Black)
- **Type hints**: Required everywhere
- **Imports**: Absolute imports only (`from src.module import ...`)
- **Async**: Async-first design

## 📝 Submitting Changes

### Before Submitting

Ensure your changes pass all checks:

```bash
# One-command pre-PR check
black src/ tests/ && ruff check src tests && pytest --cov=src && ./scripts/run_static_checks.sh
```

### Definition of Done

- ✅ All tests pass
- ✅ Code formatted with Black
- ✅ Linting passes (Ruff)
- ✅ Static checks pass
- ✅ No security issues
- ✅ Import architecture intact
- ✅ Coverage maintained (>80%)
- ✅ Documentation updated

### Pull Request Guidelines

1. **Use descriptive titles** following conventional commit format
2. **Describe your changes** clearly in the PR description
3. **Reference issues** if applicable
4. **Keep PRs focused** - one feature/fix per PR (or use stacked PRs)
5. **Update documentation** if needed
6. **Add tests** for new functionality

## 🔒 Security

- **Never commit secrets** - use `.env` file for API keys
- **Validate file paths** - use utilities from `src.utils.paths`
- **Sanitize inputs** - never execute unsanitized user input
- Review security patterns in `tests/security/`

## 📚 Additional Resources

- [Main README](../../README.md) - Project overview and quick start
- [AGENTS.md](../../AGENTS.md) - Detailed development guidelines for AI agents
- [Production Guide](../../README-PRODUCTION.md) - Deployment instructions
- [HTML Dashboard](../HTML_DASHBOARD.md) - Dashboard feature documentation

## 🤝 Getting Help

- Check existing [GitHub Issues](https://github.com/edlsh/audio-extraction-analysis/issues)
- Review component-specific AGENTS.md files
- Ask questions in pull request discussions

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](../../LICENSE) file for details.
