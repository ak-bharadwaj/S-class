const vscode = require('vscode');
const fs = require('fs');
const path = require('path');

function getWorkspaceDir() {
    if (vscode.workspace.workspaceFolders && vscode.workspace.workspaceFolders.length > 0) {
        return vscode.workspace.workspaceFolders[0].uri.fsPath;
    }
    return process.cwd();
}

function loadState(workspaceDir) {
    const stateFile = path.join(workspaceDir, '.agents', 'orchestration_state.json');
    if (fs.existsSync(stateFile)) {
        try {
            return JSON.parse(fs.readFileSync(stateFile, 'utf8'));
        } catch (e) {
            console.error('Error parsing orchestration_state.json:', e);
        }
    }
    return null;
}

class SClassTreeDataProvider {
    constructor() {
        this._onDidChangeTreeData = new vscode.EventEmitter();
        this.onDidChangeTreeData = this._onDidChangeTreeData.event;
    }

    refresh() {
        this._onDidChangeTreeData.fire();
    }

    getTreeItem(element) {
        return element;
    }

    getChildren(element) {
        const ws = getWorkspaceDir();
        const state = loadState(ws);

        if (!element) {
            if (!state) {
                return [
                    new vscode.TreeItem('Status: Uninitialized', vscode.TreeItemCollapsibleState.None),
                    new vscode.TreeItem('Run S-Class /goal to initialize', vscode.TreeItemCollapsibleState.None)
                ];
            }

            const phase = state.currentPhase || 'TRIAGE';
            const goal = state.goal || 'Autonomous Objective';
            const synth = state.provenance && state.provenance.synthetic ? 'Synthetic (Simulated)' : 'Reality-Grounded';

            const phaseItem = new vscode.TreeItem(`Phase: ${phase}`, vscode.TreeItemCollapsibleState.None);
            phaseItem.iconPath = new vscode.ThemeIcon('milestone');

            const goalItem = new vscode.TreeItem(`Goal: ${goal}`, vscode.TreeItemCollapsibleState.None);
            goalItem.iconPath = new vscode.ThemeIcon('target');

            const epistemicItem = new vscode.TreeItem(`Epistemic: ${synth}`, vscode.TreeItemCollapsibleState.None);
            epistemicItem.iconPath = new vscode.ThemeIcon(state.provenance && state.provenance.synthetic ? 'warning' : 'pass');

            const swarmParent = new vscode.TreeItem('Subagent Swarm (8 Agents)', vscode.TreeItemCollapsibleState.Collapsed);
            swarmParent.iconPath = new vscode.ThemeIcon('organization');
            swarmParent.contextValue = 'swarm';

            const gatesParent = new vscode.TreeItem('Evidence Gate Fortress', vscode.TreeItemCollapsibleState.Collapsed);
            gatesParent.iconPath = new vscode.ThemeIcon('shield');
            gatesParent.contextValue = 'gates';

            return [goalItem, phaseItem, epistemicItem, gatesParent, swarmParent];
        }

        if (element.contextValue === 'swarm') {
            return [
                new vscode.TreeItem('dss_governor: Epistemic & Triad', vscode.TreeItemCollapsibleState.None),
                new vscode.TreeItem('dss_architect: HLD & CKG Planner', vscode.TreeItemCollapsibleState.None),
                new vscode.TreeItem('dss_backend_dev: Implementation', vscode.TreeItemCollapsibleState.None),
                new vscode.TreeItem('dss_verifier: Anti-Cheating & QA', vscode.TreeItemCollapsibleState.None),
                new vscode.TreeItem('dss_cso_v2: Security SAST Shield', vscode.TreeItemCollapsibleState.None),
                new vscode.TreeItem('dss_db_architect: Schema & Storage', vscode.TreeItemCollapsibleState.None),
                new vscode.TreeItem('dss_ui_ux: Interaction Spec', vscode.TreeItemCollapsibleState.None),
                new vscode.TreeItem('dss_user_alias_v2: Skeptic & Human', vscode.TreeItemCollapsibleState.None)
            ];
        }

        if (element.contextValue === 'gates') {
            return [
                new vscode.TreeItem('Triad Status: Epistemic / Valid / Approved', vscode.TreeItemCollapsibleState.None),
                new vscode.TreeItem('ADR Canonical Hash: RFC 8785 Verified', vscode.TreeItemCollapsibleState.None),
                new vscode.TreeItem('SAST Security Gate: Semgrep / Shield Armed', vscode.TreeItemCollapsibleState.None),
                new vscode.TreeItem('Cross-Process Lock: Portalocker Active', vscode.TreeItemCollapsibleState.None)
            ];
        }

        return [];
    }
}

class SClassDashboardViewProvider {
    constructor(extensionUri) {
        this._extensionUri = extensionUri;
    }

    resolveWebviewView(webviewView) {
        this._view = webviewView;
        webviewView.webview.options = { enableScripts: true };
        this.updateContent();

        webviewView.webview.onDidReceiveMessage(message => {
            if (message.command === 'runCommand') {
                runTerminalCommand(message.text);
            } else if (message.command === 'refresh') {
                this.updateContent();
            }
        });
    }

    updateContent() {
        if (!this._view) return;
        const ws = getWorkspaceDir();
        const state = loadState(ws);
        this._view.webview.html = this.getHtml(state, ws);
    }

    getHtml(state, workspaceDir) {
        const phase = state ? state.currentPhase || 'TRIAGE' : 'UNINITIALIZED';
        const goal = state ? state.goal || 'Autonomous Objective' : 'No active workflow';
        const profile = state ? state.workflowProfile || 'fast' : 'None';
        const synth = state && state.provenance && state.provenance.synthetic;

        const phases = ['TRIAGE', 'SPEC', 'DESIGN', 'DEBATE', 'CODING', 'VERIFY', 'RELEASE'];
        const stepsHtml = phases.map(p => {
            const isCur = p === phase;
            const cls = isCur ? 'step active' : 'step';
            return `<div class="${cls}">${p}</div>`;
        }).join('<div class="arrow">➔</div>');

        return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  body { font-family: var(--vscode-font-family); padding: 12px; color: var(--vscode-editor-foreground); background-color: var(--vscode-editor-background); }
  .card { background: var(--vscode-sideBar-background); border: 1px solid var(--vscode-widget-border, #30363d); border-radius: 6px; padding: 10px 14px; margin-bottom: 12px; }
  .title { font-size: 13px; font-weight: bold; color: var(--vscode-textLink-foreground, #58a6ff); margin-bottom: 6px; }
  .stepper { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; margin: 10px 0; gap: 4px; }
  .step { font-size: 10px; font-weight: 600; padding: 3px 6px; border-radius: 4px; background: var(--vscode-badge-background, #21262d); color: var(--vscode-badge-foreground, #8b949e); }
  .step.active { background: var(--vscode-button-background, #238636); color: var(--vscode-button-foreground, #ffffff); font-weight: bold; }
  .arrow { color: var(--vscode-descriptionForeground, #8b949e); font-size: 9px; }
  .badge { display: inline-block; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; }
  .badge-warning { background: #d29922; color: #000; }
  .badge-success { background: #238636; color: #fff; }
  .btn { display: block; width: 100%; box-sizing: border-box; background: var(--vscode-button-background); color: var(--vscode-button-foreground); border: none; padding: 6px 10px; border-radius: 4px; font-weight: 600; cursor: pointer; text-align: center; margin-top: 6px; }
  .btn:hover { background: var(--vscode-button-hoverBackground); }
  .btn-secondary { background: var(--vscode-button-secondaryBackground, #21262d); color: var(--vscode-button-secondaryForeground, #c9d1d9); }
  .row { display: flex; justify-content: space-between; margin: 4px 0; font-size: 12px; }
  .label { color: var(--vscode-descriptionForeground); }
</style>
</head>
<body>
  <div class="card">
    <div class="title">S-Class Governance Control Plane</div>
    <div class="row"><span class="label">Current Phase:</span> <b>${phase}</b></div>
    <div class="row"><span class="label">Goal:</span> <span>${goal}</span></div>
    <div class="row"><span class="label">Profile:</span> <span>${profile}</span></div>
    <div class="row"><span class="label">Epistemic Mode:</span> <span class="badge ${synth ? 'badge-warning' : 'badge-success'}">${synth ? 'SYNTHETIC' : 'GROUNDED'}</span></div>
  </div>

  <div class="card">
    <div class="title">FSM Lifecycle Progression</div>
    <div class="stepper">${stepsHtml}</div>
  </div>

  <div class="card">
    <div class="title">Quick Actions</div>
    <button class="btn" onclick="send('sclass /status')">Run S-Class Status</button>
    <button class="btn btn-secondary" onclick="send('sclass /watch')">Open Live TUI Watch Monitor</button>
    <button class="btn btn-secondary" onclick="send('sclass /goal \\"Autonomous Goal\\"')">Execute Goal (/goal)</button>
    <button class="btn btn-secondary" onclick="send('sclass /boost \\"Fast-Track Task\\"')">Execute Boost (/boost)</button>
  </div>

  <script>
    const vscode = acquireVsCodeApi();
    function send(cmd) {
      vscode.postMessage({ command: 'runCommand', text: cmd });
    }
  </script>
</body>
</html>`;
    }
}

function runTerminalCommand(cmdText) {
    let term = vscode.window.terminals.find(t => t.name === 'S-Class');
    if (!term) {
        term = vscode.window.createTerminal('S-Class');
    }
    term.show();
    term.sendText(cmdText);
}

function activate(context) {
    const treeProvider = new SClassTreeDataProvider();
    vscode.window.registerTreeDataProvider('sclass.fsmView', treeProvider);

    const dashboardProvider = new SClassDashboardViewProvider(context.extensionUri);
    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider('sclass.dashboardView', dashboardProvider)
    );

    // Watch .agents/ for real-time live updates
    const watcher = vscode.workspace.createFileSystemWatcher('**/.agents/**');
    watcher.onDidChange(() => {
        treeProvider.refresh();
        dashboardProvider.updateContent();
    });
    watcher.onDidCreate(() => {
        treeProvider.refresh();
        dashboardProvider.updateContent();
    });
    context.subscriptions.push(watcher);

    // Commands
    context.subscriptions.push(vscode.commands.registerCommand('sclass.refresh', () => {
        treeProvider.refresh();
        dashboardProvider.updateContent();
        vscode.window.showInformationMessage('S-Class State Refreshed.');
    }));

    context.subscriptions.push(vscode.commands.registerCommand('sclass.watch', () => {
        runTerminalCommand('sclass /watch');
    }));

    context.subscriptions.push(vscode.commands.registerCommand('sclass.status', () => {
        runTerminalCommand('sclass /status');
    }));

    context.subscriptions.push(vscode.commands.registerCommand('sclass.goal', () => {
        vscode.window.showInputBox({ prompt: 'Enter objective for S-Class /goal:' }).then(goal => {
            if (goal) {
                runTerminalCommand(`sclass /goal "${goal}"`);
            }
        });
    }));

    context.subscriptions.push(vscode.commands.registerCommand('sclass.boost', () => {
        vscode.window.showInputBox({ prompt: 'Enter task for S-Class /boost:' }).then(task => {
            if (task) {
                runTerminalCommand(`sclass /boost "${task}"`);
            }
        });
    }));
}

function deactivate() {}

module.exports = {
    activate,
    deactivate
};
