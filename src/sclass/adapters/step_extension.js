/**
 * Authentic Step-Code Extension: Tool Call Lifecycle Interceptor (H1 Mandate 3).
 * 
 * Implements Step-Code's real extension tool lifecycle hook `pi.on("tool_call")`.
 * 
 * Interception pipeline:
 * 1. Capture exact tool name and arguments.
 * 2. Construct canonical S-Class ActionRequest.
 * 3. Bind exact action parameters and execution context.
 * 4. Invoke S-Class dual-layer authorization.
 * 5. Reject execution on any bridge failure or authorization denial.
 * 6. Return Step-Code native blocking decision to abort tool execution if denied.
 */

'use strict';

function registerSClassExtension(pi, sclassClient) {
  if (!pi || typeof pi.on !== 'function') {
    throw new Error('Invalid Step-Code plugin interface (pi): expected event emitter');
  }

  pi.on('tool_call', async (event) => {
    const toolName = event.tool || event.name || 'unknown_tool';
    const toolArgs = event.args || event.parameters || {};
    const target = event.target || toolArgs.target || toolArgs.path || toolArgs.file || '';
    const sessionId = event.sessionId || event.session_id || 'default_session';
    const workspaceDir = event.workspace_dir || event.cwd || process.cwd();

    // Construct canonical S-Class action request envelope
    const actionRequest = {
      actor: event.actor || 'step-code-agent',
      capability: event.capability || 'terminal.execute',
      action: toolName,
      target: target,
      parameters: toolArgs,
      workspace: workspaceDir,
      session_id: sessionId,
      timestamp: new Date().toISOString()
    };

    if (!sclassClient) {
      // Bridge unavailable: fail closed immediately
      return {
        block: true,
        reason: 'S-Class authorization bridge is unavailable. Failing closed.'
      };
    }

    try {
      const decision = await sclassClient.authorizeToolCall(actionRequest);
      if (!decision || !decision.allowed) {
        return {
          block: true,
          reason: decision ? decision.reason : 'Denied by S-Class dual-layer policy'
        };
      }
      return {
        block: false,
        decision_id: decision.decision_id,
        action_hash: decision.action_hash
      };
    } catch (err) {
      // Bridge error: fail closed
      return {
        block: true,
        reason: `S-Class authorization bridge error: ${err.message}. Failing closed.`
      };
    }
  });
}

module.exports = {
  registerSClassExtension
};
