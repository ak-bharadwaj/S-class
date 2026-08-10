#!/usr/bin/env bash

# S-Class V12.1 SDK Installer for Linux/macOS
# Run: curl -fsSL https://raw.githubusercontent.com/ak-bharadwaj/S-class/master/install.sh | bash

PLUGIN_ROOT="$HOME/.gemini/config/plugins"
PLUGIN_DIR="$PLUGIN_ROOT/sclass-v5"

# Create plugins directory if it doesn't exist
if [ ! -d "$PLUGIN_ROOT" ]; then
    echo "Creating plugins directory..."
    mkdir -p "$PLUGIN_ROOT"
fi

# Clone or pull updates
if [ -d "$PLUGIN_DIR" ]; then
    echo "Updating S-Class V12.1 SDK..."
    git -C "$PLUGIN_DIR" pull
else
    echo "Cloning S-Class V12.1 SDK..."
    git clone https://github.com/ak-bharadwaj/S-class.git "$PLUGIN_DIR"
fi

echo "S-Class V12.1 installation complete! Plugin active at $PLUGIN_DIR"
