#!/bin/bash
# Test execution script with different profiles and enhanced CI support

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
PROFILE="default"
VERBOSE=""
COVERAGE=""
FAIL_FAST=""
PARALLEL=""
TIMEOUT="300"

# Function to print colored messages
print_status() {
    echo -e "${2}${1}${NC}"
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --profile)
            PROFILE="$2"
            shift 2
            ;;
        --verbose|-v)
            VERBOSE="-v"
            shift
            ;;
        --coverage)
            COVERAGE="--cov=src --cov-report=xml --cov-report=html --cov-report=term-missing"
            shift
            ;;
        --fail-fast)
            FAIL_FAST="--maxfail=1"
            shift
            ;;
        --parallel)
            PARALLEL="-n auto"
            shift
            ;;
        --timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --profile PROFILE   Test profile to run (default, fast, integration, e2e, benchmark, network, all)"
            echo "  --verbose, -v       Verbose output"
            echo "  --coverage          Generate coverage report"
            echo "  --help, -h          Show this help message"
            echo ""
            echo "Profiles:"
            echo "  default      Unit tests and basic integration (CI safe)"
            echo "  fast         Only fast unit tests (<1s each)"
            echo "  integration  Integration tests with FFmpeg"
            echo "  e2e          End-to-end CLI/TUI tests"
            echo "  benchmark    Performance benchmarks"
            echo "  network      Tests requiring network access"
            echo "  all          Complete test suite"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# CI environment detection
if [[ -n "${CI:-}" ]] || [[ -n "${GITHUB_ACTIONS:-}" ]]; then
    print_status "Running in CI environment" "$BLUE"
    export AUDIO_TEST_MODE=1
    export FORCE_MOCK_PROVIDERS=true
    
    # Always use coverage in CI
    if [[ -z "$COVERAGE" ]]; then
        COVERAGE="--cov=src --cov-report=xml --cov-report=term"
    fi
fi

# Ensure pytest is available
if ! command -v pytest &> /dev/null; then
    print_status "Error: pytest not found. Installing test dependencies..." "$YELLOW"
    uv sync --dev
fi

# Create directories for test outputs
mkdir -p reports/junit
mkdir -p reports/coverage
mkdir -p test-output

# Set common pytest options
PYTEST_OPTS="--timeout=$TIMEOUT --junit-xml=reports/junit/test-results.xml"
PYTEST_OPTS="$PYTEST_OPTS $VERBOSE $COVERAGE $FAIL_FAST $PARALLEL"

print_status "Running test profile: $PROFILE" "$GREEN"

# Track exit code
exit_code=0

case $PROFILE in
    default)
        echo "Running default tests (no markers)..."
        # This respects the pyproject.toml default markers
        pytest $PYTEST_OPTS || exit_code=$?
        ;;
    
    fast)
        echo "Running fast unit tests only..."
        pytest -m "not slow and not e2e and not integration and not benchmark and not network" $PYTEST_OPTS || exit_code=$?
        ;;
    
    integration)
        echo "Running integration tests..."
        pytest -m "integration" $PYTEST_OPTS || exit_code=$?
        ;;
    
    e2e)
        echo "Running end-to-end tests..."
        export RUN_E2E=1
        pytest -m "e2e" $PYTEST_OPTS || exit_code=$?
        ;;
    
    benchmark)
        echo "Running benchmark tests..."
        pytest -m "benchmark" $PYTEST_OPTS || exit_code=$?
        ;;
    
    network)
        echo "Running network-dependent tests..."
        pytest -m "network" $PYTEST_OPTS || exit_code=$?
        ;;
    
    all)
        echo "Running complete test suite..."
        export RUN_ALL_TESTS=1
        # Override the default marker exclusions
        pytest --ignore-config -m "" $PYTEST_OPTS || exit_code=$?
        ;;
    
    *)
        print_status "Unknown profile: $PROFILE" "$RED"
        echo "Available profiles: default, fast, integration, e2e, benchmark, network, all"
        exit 1
        ;;
esac

# Generate coverage report summary
if [[ -n "$COVERAGE" ]] && [[ -f "coverage.xml" ]]; then
    print_status "\nCoverage Summary:" "$BLUE"
    python -c "
import xml.etree.ElementTree as ET
tree = ET.parse('coverage.xml')
root = tree.getroot()
line_rate = float(root.get('line-rate', 0))
branch_rate = float(root.get('branch-rate', 0))
print(f'  Line Coverage: {line_rate*100:.2f}%')
print(f'  Branch Coverage: {branch_rate*100:.2f}%')
" 2>/dev/null || true
fi

# Open coverage report if on macOS and not in CI
if [[ "$OSTYPE" == "darwin"* ]] && [[ -z "${CI:-}" ]] && [[ -f "htmlcov/index.html" ]]; then
    print_status "Opening coverage report..." "$BLUE"
    open htmlcov/index.html
fi

# Print test results location
if [[ -f "reports/junit/test-results.xml" ]]; then
    print_status "\nTest results saved to: reports/junit/test-results.xml" "$BLUE"
fi

# Check exit code
if [[ $exit_code -eq 0 ]]; then
    print_status "✅ Tests passed!" "$GREEN"
else
    print_status "❌ Tests failed with exit code: $exit_code" "$RED"
fi

exit $exit_code