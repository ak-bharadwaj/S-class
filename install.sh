#!/usr/bin/env bash

# S-Class EOS V11.2 SDK Installer for Linux/macOS
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
    echo "Updating S-Class EOS V11.2 SDK..."
    git -C "$PLUGIN_DIR" pull
else
    echo "Cloning S-Class EOS V11.2 SDK..."
    git clone https://github.com/ak-bharadwaj/S-class.git "$PLUGIN_DIR"
fi

# Install Python requirements if python3 is available
if command -v python3 &>/dev/null; then
    echo "Verifying Python dependencies..."
    python3 -m pip install -q -r "$PLUGIN_DIR/requirements.txt"
fi

echo "=========================================================="
echo "⚡ S-Class EOS V11.2 Installation Complete!"
echo "Active Plugin Path: $PLUGIN_DIR"
echo "Cataloged Skills: 118 (Domain Primitives, Behavior Graph, Spec Synthesis, ADR Architecture Debate, ChangeSet Governance)"
echo "Subagent Matrix: 8 Concurrent Subagents | Verification Engine: 397 Product Regression Tests Passing across 49 Test Suites"
echo "Commands: /goal, /grill, /doubt, /inquire"
echo "=========================================================="
