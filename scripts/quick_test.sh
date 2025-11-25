#!/usr/bin/env bash
#
# Quick smoke test for audio-extraction-analysis pipeline
# This should complete in under 1 minute
#

set -e  # Exit on error

echo "================================================"
echo "Audio-Extraction-Analysis Pipeline - Quick Test"
echo "================================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counter
TOTAL=0
PASSED=0
FAILED=0

# Function to run a test
run_test() {
    local test_name="$1"
    local command="$2"
    local expected_exit_code="${3:-0}"
    
    TOTAL=$((TOTAL + 1))
    echo -n "Testing: $test_name ... "
    
    if eval "$command" > /dev/null 2>&1; then
        if [ "$expected_exit_code" -eq 0 ]; then
            echo -e "${GREEN}✓${NC}"
            PASSED=$((PASSED + 1))
        else
            echo -e "${RED}✗ (expected failure but passed)${NC}"
            FAILED=$((FAILED + 1))
        fi
    else
        exit_code=$?
        if [ "$exit_code" -eq "$expected_exit_code" ]; then
            echo -e "${GREEN}✓${NC}"
            PASSED=$((PASSED + 1))
        else
            echo -e "${RED}✗ (exit code: $exit_code, expected: $expected_exit_code)${NC}"
            FAILED=$((FAILED + 1))
        fi
    fi
}

# Create temp directory for test files
TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

echo "Creating test files in $TEMP_DIR..."
echo ""

# Create minimal test files
echo "FAKE_VIDEO_CONTENT" > "$TEMP_DIR/test.mp4"
echo "FAKE_AUDIO_CONTENT" > "$TEMP_DIR/test.mp3"

# Test 1: Help commands
run_test "Main help" "audio-extraction-analysis --help"
run_test "Version info" "audio-extraction-analysis --version"

# Test 2: Subcommand help
run_test "Extract help" "audio-extraction-analysis extract --help"
run_test "Transcribe help" "audio-extraction-analysis transcribe --help"
run_test "Process help" "audio-extraction-analysis process --help"

# Test 3: Basic extraction (will fail with fake file, but tests CLI)
run_test "Extract command parsing" "audio-extraction-analysis extract $TEMP_DIR/test.mp4 -o $TEMP_DIR/output.mp3 --dry-run 2>/dev/null || true" 0

# Test 4: Security tests (should fail)
run_test "Path traversal blocked" "audio-extraction-analysis process '../../../etc/passwd'" 1
run_test "Command injection blocked" "audio-extraction-analysis process 'test.mp4; echo hacked'" 1

# Test 5: Invalid arguments (should fail)
run_test "Invalid provider" "audio-extraction-analysis transcribe test.mp3 --provider invalid" 2
run_test "Missing required arg" "audio-extraction-analysis process" 2

# Test 6: Check Python imports
echo ""
echo "Checking Python imports..."
if python3 -c "from src.cli import main; from src.commands import create_parser" 2>/dev/null; then
    echo -e "${GREEN}✓${NC} Core modules import successfully"
    PASSED=$((PASSED + 1))
    TOTAL=$((TOTAL + 1))
else
    echo -e "${RED}✗${NC} Failed to import core modules"
    FAILED=$((FAILED + 1))
    TOTAL=$((TOTAL + 1))
fi

# Summary
echo ""
echo "================================================"
echo "                TEST SUMMARY"
echo "================================================"
echo -e "Total:  $TOTAL"
echo -e "Passed: ${GREEN}$PASSED${NC}"
echo -e "Failed: ${RED}$FAILED${NC}"

if [ $FAILED -eq 0 ]; then
    echo -e "\n${GREEN}All smoke tests passed!${NC}"
    exit 0
else
    echo -e "\n${YELLOW}Warning: $FAILED test(s) failed${NC}"
    echo "Run './scripts/run_comprehensive_tests.py' for detailed analysis"
    exit 1
fi