#!/usr/bin/env bash

# S-Class SDK Installer for Linux/macOS
# Run: curl -fsSL https://raw.githubusercontent.com/ak-bharadwaj/sclass-v5/master/install.sh | bash

PLUGIN_ROOT="$HOME/.gemini/config/plugins"
PLUGIN_DIR="$PLUGIN_ROOT/sclass-v5"

# Create plugins directory if it doesn't exist
if [ ! -d "$PLUGIN_ROOT" ]; then
    echo "Creating plugins directory..."
    mkdir -p "$PLUGIN_ROOT"
fi

# Clone or pull updates
if [ -d "$PLUGIN_DIR" ]; then
    echo "S-Class SDK already installed. Updating..."
    cd "$PLUGIN_DIR" || exit
    git pull
else
    echo "Cloning S-Class SDK..."
    git clone https://github.com/ak-bharadwaj/sclass-v5.git "$PLUGIN_DIR"
fi

echo "Installation complete! Inherit this workflow by adding 'pipeline: sclass-v5' to your CLAUDE.md workspace config."
