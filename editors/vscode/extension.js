/**
 * S-Class VS Code Extension Integration.
 * 
 * Thin client routing editor interactions to the S-Class control plane
 * via the Python CLI or stdio Model Context Protocol (MCP) server.
 */

const vscode = require('vscode');
const { exec } = require('child_process');
const path = require('path');

function activate(context) {
    const outputChannel = vscode.window.createOutputChannel('S-Class');

    // Command: Audit Hash Chain
    const auditCmd = vscode.commands.registerCommand('sclass.auditChain', () => {
        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (!workspaceFolders) {
            vscode.window.showErrorMessage('No workspace open');
            return;
        }
        const root = workspaceFolders[0].uri.fsPath;
        outputChannel.appendLine('[S-Class] Running cryptographic hash chain audit...');

        exec('python tools/cli/sclass.py audit', { cwd: root }, (err, stdout, stderr) => {
            if (err) {
                vscode.window.showErrorMessage(`S-Class Audit Failed: ${stderr || stdout}`);
                outputChannel.appendLine(`[Audit Error] ${stderr || stdout}`);
            } else {
                vscode.window.showInformationMessage(`S-Class Chain Audit: ${stdout.trim()}`);
                outputChannel.appendLine(`[Audit OK] ${stdout.trim()}`);
            }
        });
    });

    // Command: Run Doctor
    const doctorCmd = vscode.commands.registerCommand('sclass.runDoctor', () => {
        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (!workspaceFolders) return;
        const root = workspaceFolders[0].uri.fsPath;
        outputChannel.appendLine('[S-Class] Running diagnostic health check...');

        exec('python tools/diagnostics/doctor.py', { cwd: root }, (err, stdout, stderr) => {
            outputChannel.appendLine(stdout);
            if (err) {
                vscode.window.showWarningMessage('S-Class Doctor detected health warnings. Check output.');
            } else {
                vscode.window.showInformationMessage('S-Class Doctor: All systems healthy.');
            }
        });
    });

    context.subscriptions.push(auditCmd, doctorCmd);
    outputChannel.appendLine('S-Class Governance Extension activated.');
}

function deactivate() {}

module.exports = {
    activate,
    deactivate
};
