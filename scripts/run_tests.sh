#!/bin/bash
# Test execution script with different profiles

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
PROFILE="default"
VERBOSE=""
COVERAGE=""

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
            COVERAGE="--cov=src --cov-report=term-missing"
            shift
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

echo -e "${GREEN}Running test profile: $PROFILE${NC}"

case $PROFILE in
    default)
        echo "Running default tests (no markers)..."
        # This respects the pyproject.toml default markers
        pytest $VERBOSE $COVERAGE
        ;;
    
    fast)
        echo "Running fast unit tests only..."
        pytest -m "not slow and not e2e and not integration and not benchmark and not network" $VERBOSE $COVERAGE
        ;;
    
    integration)
        echo "Running integration tests..."
        pytest -m "integration" $VERBOSE $COVERAGE
        ;;
    
    e2e)
        echo "Running end-to-end tests..."
        export RUN_E2E=1
        pytest -m "e2e" $VERBOSE $COVERAGE
        ;;
    
    benchmark)
        echo "Running benchmark tests..."
        pytest -m "benchmark" $VERBOSE $COVERAGE
        ;;
    
    network)
        echo "Running network-dependent tests..."
        pytest -m "network" $VERBOSE $COVERAGE
        ;;
    
    all)
        echo "Running complete test suite..."
        export RUN_ALL_TESTS=1
        # Override the default marker exclusions
        pytest --ignore-config -m "" $VERBOSE $COVERAGE
        ;;
    
    *)
        echo -e "${RED}Unknown profile: $PROFILE${NC}"
        echo "Available profiles: default, fast, integration, e2e, benchmark, network, all"
        exit 1
        ;;
esac

# Check exit code
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Tests passed!${NC}"
else
    echo -e "${RED}✗ Tests failed!${NC}"
    exit 1
fi