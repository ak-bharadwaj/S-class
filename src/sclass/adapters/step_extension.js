/**
 * Authentic Step-Code Extension: Tool Call & Tool Result Lifecycle Interceptor.
 * Implements Step-Code's real extension hooks:
 * 1. `pi.on("tool_call")` - Pre-execution authorization gate (Directive Section 8)
 * 2. `pi.on("tool_result")` - Post-execution settlement interception (Directive Section 9)
 * 
 * Tool Call Interception Pipeline:
 * 1. Capture exact tool name and arguments.
 * 2. Construct canonical S-Class ActionRequest envelope.
 * 3. Invoke S-Class dual-layer authorization (Policy + Runtime Permission).
 * 4. Fail closed on bridge failure or authorization denial.
 * 5. Return native blocking decision to Step-Code engine.
 * 
 * Tool Result Interception Pipeline:
 * 1. Capture: tool_call_id, operation_id, tool_name, arguments_hash, workspace,
 *    runtime_identity, start_time, end_time, exit_code, stdout_hash, stderr_hash, result_hash.
 * 2. Classify: runtime result -> UNTRUSTED CANDIDATE.
 * 3. Forward to independent observation and evidence receipt pipeline.
 * 4. Strictly prevent runtime result from directly becoming verified truth.
 */

'use strict';

const crypto = require('crypto');

function sha256Hex(data) {
  if (data === null || data === undefined) return '';
  const text = typeof data === 'string' ? data : JSON.stringify(data);
  return crypto.createHash('sha256').update(text, 'utf8').digest('hex');
}

function registerSClassExtension(pi, sclassClient) {
  if (!pi || typeof pi.on !== 'function') {
    throw new Error('Invalid Step-Code plugin interface (pi): expected event emitter');
  }

  // Pre-execution tool call interception
  pi.on('tool_call', async (event) => {
    const toolName = event.toolName || event.tool || event.name || 'unknown_tool';
    const toolArgs = event.input || event.args || event.parameters || {};
    const target = event.target || toolArgs.target || toolArgs.path || toolArgs.file || '';
    const sessionId = event.sessionId || event.session_id || 'default_session';
    const workspaceDir = event.workspace_dir || event.cwd || process.cwd();
    const operationId = event.operationId || event.operation_id || `op_${crypto.randomBytes(6).toString('hex')}`;

    // Construct canonical S-Class action request envelope
    const actionRequest = {
      actor: event.actor || 'step-code-agent',
      capability: event.capability || 'terminal.execute',
      action: toolName,
      target: target,
      parameters: toolArgs,
      workspace: workspaceDir,
      session_id: sessionId,
      operation_id: operationId,
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
        action_hash: decision.action_hash,
        operation_id: operationId
      };
    } catch (err) {
      // Bridge error: fail closed
      return {
        block: true,
        reason: `S-Class authorization bridge error: ${err.message}. Failing closed.`
      };
    }
  });

  // Post-execution tool result interception (Directive Section 9)
  pi.on('tool_result', async (event) => {
    const toolCallId = event.toolCallId || event.call_id || event.id || `call_${crypto.randomBytes(6).toString('hex')}`;
    const operationId = event.operationId || event.operation_id || '';
    const toolName = event.toolName || event.tool || event.name || 'unknown_tool';
    const toolArgs = event.input || event.args || event.parameters || {};
    const workspaceDir = event.workspace_dir || event.cwd || process.cwd();
    const runtimeIdentity = event.runtimeIdentity || 'step-code';
    const startTime = event.startTime || event.start_time || new Date().toISOString();
    const endTime = event.endTime || event.end_time || new Date().toISOString();
    const exitCode = typeof event.exitCode === 'number' ? event.exitCode : (event.status === 'error' ? 1 : 0);
    const stdout = event.stdout || (typeof event.output === 'string' ? event.output : '');
    const stderr = event.stderr || (event.error ? String(event.error) : '');
    const rawResult = event.result !== undefined ? event.result : event.output;

    const resultRecord = {
      tool_call_id: toolCallId,
      operation_id: operationId,
      tool_name: toolName,
      arguments_hash: sha256Hex(toolArgs),
      workspace: workspaceDir,
      runtime_identity: runtimeIdentity,
      start_time: startTime,
      end_time: endTime,
      exit_code: exitCode,
      stdout_hash: sha256Hex(stdout),
      stderr_hash: sha256Hex(stderr),
      result_hash: sha256Hex(rawResult),
      untrusted_candidate: true, // Untrusted candidate evidence signal (Law L1 & L2)
      classification: 'UNTRUSTED_CANDIDATE',
      timestamp: new Date().toISOString()
    };

    if (sclassClient && typeof sclassClient.recordToolResult === 'function') {
      try {
        await sclassClient.recordToolResult(resultRecord);
      } catch (err) {
        // Log telemetry error but do not mask the runtime event
        if (typeof console !== 'undefined' && console.warn) {
          console.warn(`Failed to forward tool result to S-Class observer: ${err.message}`);
        }
      }
    }

    return resultRecord;
  });
}

module.exports = {
  registerSClassExtension,
  sha256Hex
};
