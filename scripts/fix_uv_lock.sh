#!/usr/bin/env bash
# Script to fix UV lockfile issues and ensure consistency

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== UV Lockfile Fix Script ===${NC}"

# Function to check if command exists
command_exists() {
    command -v "$1" &> /dev/null
}

# Function to print status
print_status() {
    echo -e "${2}${1}${NC}"
}

# Check if uv is installed
if ! command_exists uv; then
    print_status "Error: uv is not installed. Please install it first:" "$RED"
    echo "curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Get current uv version
UV_VERSION=$(uv --version | cut -d' ' -f2)
print_status "Current UV version: $UV_VERSION" "$GREEN"

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    print_status "Error: pyproject.toml not found. Please run from project root." "$RED"
    exit 1
fi

# Step 1: Clean cache
print_status "\n1. Cleaning UV cache..." "$YELLOW"
uv cache prune --ci || true

# Step 2: Remove old lock file
if [ -f "uv.lock" ]; then
    print_status "2. Backing up existing uv.lock..." "$YELLOW"
    cp uv.lock uv.lock.backup.$(date +%Y%m%d_%H%M%S)
    rm uv.lock
    print_status "   Old lock file backed up and removed" "$GREEN"
else
    print_status "2. No existing uv.lock found" "$YELLOW"
fi

# Step 3: Update UV to latest version
print_status "\n3. Updating UV to latest version..." "$YELLOW"
uv self update || print_status "   Could not update UV (may need sudo)" "$YELLOW"

# Step 4: Generate fresh lock file
print_status "\n4. Generating fresh lock file..." "$YELLOW"
uv lock --verbose

# Step 5: Verify lock file
print_status "\n5. Verifying lock file..." "$YELLOW"
if uv sync --locked --dry-run; then
    print_status "   Lock file verified successfully!" "$GREEN"
else
    print_status "   Warning: Lock file verification failed" "$RED"
    print_status "   Trying to sync without --locked flag..." "$YELLOW"
    uv sync
fi

# Step 6: Check Python version consistency
print_status "\n6. Checking Python version..." "$YELLOW"
PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
print_status "   System Python: $PYTHON_VERSION" "$BLUE"

# Extract requires-python from pyproject.toml
if grep -q "requires-python" pyproject.toml; then
    REQUIRES_PYTHON=$(grep "requires-python" pyproject.toml | cut -d'"' -f2)
    print_status "   Project requires: Python $REQUIRES_PYTHON" "$BLUE"
fi

# Step 7: Install dependencies with all extras
print_status "\n7. Installing dependencies with all extras..." "$YELLOW"
uv sync --locked --all-extras --dev

# Step 8: Verify installation
print_status "\n8. Verifying installation..." "$YELLOW"
if uv pip list | grep -q deepgram-sdk; then
    print_status "   Core dependencies installed successfully" "$GREEN"
else
    print_status "   Warning: Some dependencies may not be installed" "$YELLOW"
fi

# Step 9: Generate pip freeze for comparison
print_status "\n9. Generating pip freeze output..." "$YELLOW"
uv pip freeze > requirements.freeze.txt
print_status "   Frozen requirements saved to requirements.freeze.txt" "$GREEN"

# Step 10: Git status check
print_status "\n10. Checking git status..." "$YELLOW"
if [ -d ".git" ]; then
    if git diff --quiet uv.lock 2>/dev/null; then
        print_status "    No changes to uv.lock" "$GREEN"
    else
        print_status "    uv.lock has been modified" "$YELLOW"
        print_status "    Please commit the updated lock file" "$YELLOW"
    fi
else
    print_status "    Not a git repository" "$YELLOW"
fi

print_status "\n=== UV Lockfile Fix Complete ===" "$GREEN"
print_status "\nNext steps:" "$BLUE"
echo "1. Test the installation: uv run pytest tests/unit -v"
echo "2. Commit the updated uv.lock file: git add uv.lock && git commit -m 'fix: update uv.lock'"
echo "3. Push to trigger CI: git push"

# Provide CI-specific recommendations
print_status "\nFor GitHub Actions:" "$BLUE"
echo "- Ensure workflows use: astral-sh/setup-uv@v3 or later"
echo "- Pin UV version: version: '$UV_VERSION'"
echo "- Use: uv sync --locked --all-extras --dev"
echo "- Enable caching: enable-cache: true"

print_status "\nScript completed successfully!" "$GREEN"
