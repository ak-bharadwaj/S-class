#!/usr/bin/env bash

# S-Class V13 Universal Multi-IDE Plugin & Microkernel Installer for Linux/macOS
# Run: curl -fsSL https://raw.githubusercontent.com/ak-bharadwaj/S-class/master/install.sh | bash

set -e

PLUGIN_ROOT="$HOME/.gemini/config/plugins"
PLUGIN_DIR="$PLUGIN_ROOT/sclass-v5"

# Create plugins directory if it doesn't exist
if [ ! -d "$PLUGIN_ROOT" ]; then
    echo "Creating plugins directory..."
    mkdir -p "$PLUGIN_ROOT"
fi

# Clone or pull updates
if [ -d "$PLUGIN_DIR" ]; then
    echo "Updating S-Class V13 SDK..."
    git -C "$PLUGIN_DIR" pull
else
    echo "Cloning S-Class V13 SDK..."
    git clone https://github.com/ak-bharadwaj/S-class.git "$PLUGIN_DIR"
fi

# Install Python requirements if python3 is available
PYTHON_BIN="python3"
if ! command -v python3 &>/dev/null; then
    PYTHON_BIN="python"
fi

if command -v "$PYTHON_BIN" &>/dev/null; then
    echo "Verifying Python dependencies..."
    "$PYTHON_BIN" -m pip install -q -r "$PLUGIN_DIR/requirements.txt"
fi

# Target workspace detection
TARGET_WS="${1:-$(pwd)}"

# Multi-IDE Detection
DETECTED_IDES=()
[ -d "$TARGET_WS/.cursor" ] && DETECTED_IDES+=("Cursor")
[ -d "$TARGET_WS/.claude" ] && DETECTED_IDES+=("Claude Code")
([ -d "$TARGET_WS/.agents" ] || [ -d "$TARGET_WS/.gemini" ]) && DETECTED_IDES+=("Antigravity / Gemini")
[ -d "$TARGET_WS/.codex" ] && DETECTED_IDES+=("OpenAI Codex CLI")
[ -d "$TARGET_WS/.github" ] && DETECTED_IDES+=("GitHub Copilot")
[ -d "$TARGET_WS/.windsurf" ] && DETECTED_IDES+=("Windsurf")

if [ ${#DETECTED_IDES[@]} -eq 0 ]; then
    DETECTED_IDES=("Universal (Cursor, Claude Code, Antigravity, Codex CLI)")
fi

# Run sclass init to deploy runner, register MCP configs, and project rules
if command -v "$PYTHON_BIN" &>/dev/null; then
    echo "Registering hooks, MCP server configs, and governance rules in $TARGET_WS..."
    "$PYTHON_BIN" "$PLUGIN_DIR/sclass_cli.py" init -w "$TARGET_WS"
fi

echo "=========================================================="
echo "⚡ S-Class V13 Universal Installation & Integration Complete!"
echo "Active Plugin Path: $PLUGIN_DIR"
echo "Active Workspace:   $TARGET_WS"
echo "Target IDEs:        ${DETECTED_IDES[*]}"
echo "Cataloged Skills:   118 (Domain Primitives, Behavior Graph, Spec Synthesis, ADR Architecture Debate)"
echo "Cross-Platform:     Blocking Hooks, MCP Plugin Configs, Rule Parity (.cursorrules, CLAUDE.md, .claude/rules)"
echo "Commands:           /goal, /boost, /learn, /grill, /doubt, /inquire"
echo "=========================================================="
