# S-Class Governance Control Plane - VS Code Extension

Official VS Code extension providing live sidebar visibility, FSM lifecycle tracking, evidence gate status, and integrated command execution for S-Class.

## Features

- **Live Activity Bar Sidebar**: Displays the S-Class shield icon in the VS Code activity bar.
- **FSM State & Gates Tree View**: Shows current phase, active goal, epistemic mode (Synthetic vs Reality-Grounded), and the 8-agent cognitive swarm.
- **Real-Time Control Plane Webview**: Responsive dark-themed dashboard that live-tails `.agents/orchestration_state.json` without polling lag.
- **One-Click Commands**:
  - `S-Class: Open Live Watch Terminal` (`sclass /watch`)
  - `S-Class: Show Current Status` (`sclass /status`)
  - `S-Class: Run Goal` (`sclass /goal`)
  - `S-Class: Run Boost` (`sclass /boost`)

## Installation

### From Source
1. Copy or symlink `editors/vscode` to your `~/.vscode/extensions/sclass-governor` directory:
   ```bash
   # Windows PowerShell:
   New-Item -ItemType Junction -Path "$HOME\.vscode\extensions\sclass-governor" -Target "path\to\sclass\editors\vscode"
   
   # Linux / macOS:
   ln -s /path/to/sclass/editors/vscode ~/.vscode/extensions/sclass-governor
   ```
2. Reload VS Code (`Ctrl+Shift+P` -> `Developer: Reload Window`).

### Packaging as VSIX
To compile into a `.vsix` file:
```bash
npx @vscode/vsce package
code --install-extension sclass-governor-1.0.0.vsix
```
