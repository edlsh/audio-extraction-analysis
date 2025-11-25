#!/bin/bash
# Local E2E Test Execution Script
# 
# This script provides quick access to the E2E test suite for local development.
# It serves as a wrapper around the comprehensive test runner.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
E2E_RUNNER="$PROJECT_ROOT/tests/e2e/run_e2e_tests.py"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
TEST_SUITE="all"
VERBOSE=false
COVERAGE=false
GENERATE_DATA=false
FAIL_FAST=false

# Print usage information
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Quick E2E test execution for local development"
    echo ""
    echo "OPTIONS:"
    echo "  -s, --suite SUITE     Test suite to run (all|unit|integration|cli|provider|performance|security)"
    echo "  -v, --verbose         Enable verbose output"
    echo "  -c, --coverage        Generate coverage reports"
    echo "  -g, --generate-data   Generate fresh test data"
    echo "  -f, --fail-fast       Stop on first critical failure"
    echo "  -q, --quick           Quick test (unit + integration only)"
    echo "  -h, --help            Show this help message"
    echo ""
    echo "EXAMPLES:"
    echo "  $0                    # Run all tests"
    echo "  $0 -q                 # Quick test (unit + integration)"
    echo "  $0 -s cli -v          # Run CLI tests with verbose output"
    echo "  $0 -s performance -g  # Run performance tests with fresh data"
    echo "  $0 -c -f              # Run all tests with coverage, fail fast"
    echo ""
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -s|--suite)
            TEST_SUITE="$2"
            shift 2
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -c|--coverage)
            COVERAGE=true
            shift
            ;;
        -g|--generate-data)
            GENERATE_DATA=true
            shift
            ;;
        -f|--fail-fast)
            FAIL_FAST=true
            shift
            ;;
        -q|--quick)
            TEST_SUITE="unit"
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo -e "${RED}Error: Unknown option $1${NC}" >&2
            usage
            exit 1
            ;;
    esac
done

# Validate test suite
valid_suites="all unit integration cli provider performance security"
if [[ ! " $valid_suites " =~ " $TEST_SUITE " ]]; then
    echo -e "${RED}Error: Invalid test suite '$TEST_SUITE'${NC}" >&2
    echo "Valid suites: $valid_suites" >&2
    exit 1
fi

# Print configuration
echo -e "${BLUE}=== Local E2E Test Execution ===${NC}"
echo "Project Root: $PROJECT_ROOT"
echo "Test Suite: $TEST_SUITE"
echo "Verbose: $VERBOSE"
echo "Coverage: $COVERAGE"
echo "Generate Data: $GENERATE_DATA"
echo "Fail Fast: $FAIL_FAST"
echo ""

# Check prerequisites
echo -e "${BLUE}Checking prerequisites...${NC}"

# Check if we're in a virtual environment
if [[ -z "${VIRTUAL_ENV:-}" ]]; then
    echo -e "${YELLOW}Warning: Not in a virtual environment. Consider activating one.${NC}"
fi

# Check if E2E runner exists
if [[ ! -f "$E2E_RUNNER" ]]; then
    echo -e "${RED}Error: E2E test runner not found at $E2E_RUNNER${NC}" >&2
    exit 1
fi

# Check if pytest is available
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}Error: pytest not found. Please install test dependencies:${NC}" >&2
    echo "uv sync --dev" >&2
    exit 1
fi

# Check if FFmpeg is available (for media file generation)
if ! command -v ffmpeg &> /dev/null; then
    echo -e "${YELLOW}Warning: FFmpeg not found. Test media generation will be skipped.${NC}"
fi

echo -e "${GREEN}Prerequisites check passed.${NC}"
echo ""

# Build command arguments
ARGS=("--suite" "$TEST_SUITE")

if [[ "$VERBOSE" == "true" ]]; then
    ARGS+=("--verbose")
fi

if [[ "$COVERAGE" == "true" ]]; then
    ARGS+=("--coverage")
fi

if [[ "$GENERATE_DATA" == "true" ]]; then
    ARGS+=("--generate-test-data")
fi

if [[ "$FAIL_FAST" == "true" ]]; then
    ARGS+=("--fail-fast")
fi

# Set output directory for local runs
OUTPUT_DIR="$PROJECT_ROOT/test_results_local"
ARGS+=("--output-dir" "$OUTPUT_DIR")

# Execute the test runner
echo -e "${BLUE}Starting test execution...${NC}"
echo "Command: python $E2E_RUNNER ${ARGS[*]}"
echo ""

cd "$PROJECT_ROOT"

# Run the tests
if python "$E2E_RUNNER" "${ARGS[@]}"; then
    echo ""
    echo -e "${GREEN}=== Test Execution Completed Successfully ===${NC}"
    echo "Results available in: $OUTPUT_DIR"
    
    # Show quick summary if available
    if [[ -f "$OUTPUT_DIR/e2e_test_report.txt" ]]; then
        echo ""
        echo -e "${BLUE}Quick Summary:${NC}"
        grep -E "(Overall Result|Total Tests|Passed|Failed)" "$OUTPUT_DIR/e2e_test_report.txt" || true
    fi
    
    # Show coverage summary if available
    if [[ "$COVERAGE" == "true" && -f "$OUTPUT_DIR/unit_coverage.json" ]]; then
        echo ""
        echo -e "${BLUE}Coverage Summary:${NC}"
        python -c "
import json
try:
    with open('$OUTPUT_DIR/unit_coverage.json') as f:
        data = json.load(f)
    total = data.get('totals', {})
    print(f\"Lines: {total.get('percent_covered', 0):.1f}% covered\")
    print(f\"Missing: {total.get('missing_lines', 0)} lines\")
except:
    print('Coverage data not available')
"
    fi
    
else
    echo ""
    echo -e "${RED}=== Test Execution Failed ===${NC}"
    echo "Check the logs in: $OUTPUT_DIR"
    
    # Show error summary if available
    if [[ -f "$OUTPUT_DIR/e2e_test_report.txt" ]]; then
        echo ""
        echo -e "${RED}Error Summary:${NC}"
        grep -A 5 -B 5 "FAILED" "$OUTPUT_DIR/e2e_test_report.txt" || true
    fi
    
    exit 1
fi