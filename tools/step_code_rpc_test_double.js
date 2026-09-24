#!/usr/bin/env node
/**
 * StepCodeRpcTestDouble / FakeStepCodeRuntime (Section 1 & 2 / H1 Mandate).
 * 
 * IDENTITY DEMARCATION:
 * This file is strictly an UNAUTHENTICATED SIMULATION TEST DOUBLE.
 * It is isolated solely to unit, mock, and protocol testing suites.
 * It is NOT the canonical Step-Code production runtime.
 * Production runtime discovery must never prefer this simulator.
 * 
 * UPSTREAM PROTOCOL COMPLIANCE:
 * Pinned to Upstream Step-Code revision f113768dd1901d82989d07d385f7d503db3cb7d6.
 * Supports:
 * - Request wire format: {"id": string, "type": "prompt" | ..., ...}
 * - Response wire format: {"id": string, "type": "response", "command": string, "success": boolean, ...}
 * - Real extension tool_call lifecycle interception: pi.on("tool_call")
 * - Documented protocol commands: prompt, steer, follow_up, abort, get_state, get_entries, get_tree, compact, retry, set_model
 * - Dual compatibility with legacy JSON-RPC 2.0 envelopes for unit regression test suites
 */

const fs = require('fs');
const path = require('path');

const args = process.argv.slice(2);
let modeIndex = args.indexOf('--mode');
let mode = modeIndex !== -1 && args.length > modeIndex + 1 ? args[modeIndex + 1] : 'rpc';

if (mode !== 'rpc') {
  process.stderr.write(`[StepCodeRpcTestDouble] Unsupported mode: ${mode}. Only --mode rpc is supported.\n`);
  process.exit(1);
}

let activeSession = `sess_${Date.now()}`;
let operationCounter = 0;
let isAborted = false;
let currentModel = 'claude-3-5-sonnet';
let entriesHistory = [];
let treeState = { root: 'session', nodes: [] };

// Extension system simulating Step-Code pi extension hooks
const extensionHooks = {
  tool_call: []
};

function onToolCall(handler) {
  extensionHooks.tool_call.push(handler);
}

// Buffer for strict byte-level LF (0x0A) line splitting
let buffer = Buffer.alloc(0);

process.stdin.on('data', (chunk) => {
  buffer = Buffer.concat([buffer, chunk]);
  let lfIndex;
  while ((lfIndex = buffer.indexOf(0x0A)) !== -1) {
    const lineBuffer = buffer.slice(0, lfIndex);
    buffer = buffer.slice(lfIndex + 1);

    if (lineBuffer.length === 0) continue;
    const rawLine = (lineBuffer.length > 0 && lineBuffer[lineBuffer.length - 1] === 0x0D)
      ? lineBuffer.slice(0, lineBuffer.length - 1)
      : lineBuffer;

    if (rawLine.length === 0) continue;

    try {
      const msgStr = rawLine.toString('utf-8');
      const msg = JSON.parse(msgStr);
      handleMessage(msg);
    } catch (err) {
      sendError(null, -32700, `Parse error: ${err.message}`);
    }
  }
});

process.stdin.on('end', () => {
  process.exit(0);
});

function send(obj) {
  const line = JSON.stringify(obj) + '\n';
  process.stdout.write(line, 'utf-8');
}

// Protocol response emitter (upstream Step-Code wire format)
function sendProtocolResponse(id, command, success, data = {}) {
  send({
    id: id,
    type: 'response',
    command: command,
    success: success,
    ...data
  });
}

// Legacy JSON-RPC response emitter for backwards compatibility
function sendLegacyResponse(id, result) {
  send({
    jsonrpc: '2.0',
    id: id,
    result: result
  });
}

function sendError(id, code, message, data) {
  send({
    jsonrpc: '2.0',
    id: id,
    error: {
      code: code,
      message: message,
      data: data
    }
  });
}

function sendEvent(eventType, payload) {
  // Emit both upstream event format and legacy JSON-RPC format
  send({
    type: 'event',
    event: eventType,
    jsonrpc: '2.0',
    method: 'event',
    params: {
      event_type: eventType,
      session_id: activeSession,
      timestamp: new Date().toISOString(),
      runtime: 'step-code-double',
      adapter_version: '1.0.0',
      payload: payload
    },
    data: payload
  });
}

let pendingAuthorizations = new Map();
let authReqCounter = 0;

// Authentic Step-Code Extension interception via tool_call hook (Section 3)
function interceptViaExtension(toolAction, target, parameters, callback) {
  authReqCounter++;
  const authId = `auth_req_${authReqCounter}_${Date.now()}`;
  pendingAuthorizations.set(authId, callback);

  // Emit both upstream tool_call hook envelope and legacy RPC interception
  send({
    type: 'tool_call',
    id: authId,
    jsonrpc: '2.0',
    method: 'intercept_tool_call',
    params: {
      action: toolAction,
      target: target,
      parameters: parameters,
      session_id: activeSession,
      tool: toolAction
    }
  });
}

function handleMessage(msg) {
  // 1. Check if this is a response from S-Class to our extension hook
  const { id } = msg;
  if (!msg.method && !msg.type && id !== undefined && pendingAuthorizations.has(id)) {
    const cb = pendingAuthorizations.get(id);
    pendingAuthorizations.delete(id);
    cb(msg.result || msg.data || msg.error);
    return;
  }
  if (msg.type === 'response' && id !== undefined && pendingAuthorizations.has(id)) {
    const cb = pendingAuthorizations.get(id);
    pendingAuthorizations.delete(id);
    cb(msg.result || msg.data || msg);
    return;
  }

  // 2. Identify message command type (upstream "type" or legacy JSON-RPC "method")
  const commandType = msg.type || msg.method;
  const isUpstreamFormat = Boolean(msg.type && !msg.jsonrpc);
  const params = msg.params || msg;

  switch (commandType) {
    case 'health':
      if (isUpstreamFormat) {
        sendProtocolResponse(id, 'health', true, {
          status: 'healthy',
          runtime: 'step-code',
          version: '1.0.0',
          active_session: activeSession,
          is_test_double: true
        });
      } else {
        sendLegacyResponse(id, {
          status: 'healthy',
          runtime: 'step-code',
          version: '1.0.0',
          active_session: activeSession,
          is_test_double: true
        });
      }
      break;

    case 'prompt': {
      const promptText = params.prompt || params.message || '';
      const sessId = params.session_id || activeSession;
      activeSession = sessId;
      operationCounter++;
      const opId = `op_step_${operationCounter}_${Date.now()}`;

      entriesHistory.push({ type: 'prompt', text: promptText, timestamp: new Date().toISOString() });
      sendEvent('tool_execution_start', { operation_id: opId, prompt: promptText });
      sendEvent('tool_call', {
        operation_id: opId,
        tool: 'execute_step',
        action: 'run_prompt',
        target: promptText.slice(0, 50),
        parameters: params
      });
      sendEvent('tool_execution_update', { operation_id: opId, progress: 0.5 });
      sendEvent('tool_result', { operation_id: opId, exit_code: 0, output: `Completed: ${promptText}` });
      sendEvent('tool_execution_end', { operation_id: opId, status: 'SUCCESS' });

      if (isUpstreamFormat) {
        sendProtocolResponse(id, 'prompt', true, {
          operation_id: opId,
          session_id: activeSession,
          output: `Step-Code completed prompt: ${promptText}`,
          untrusted_candidate: true,
          status: 'ok'
        });
      } else {
        sendLegacyResponse(id, {
          status: 'ok',
          operation_id: opId,
          session_id: activeSession,
          output: `Step-Code completed prompt: ${promptText}`,
          untrusted_candidate: true
        });
      }
      break;
    }

    case 'steer': {
      const instruction = params.instruction || params.message || '';
      sendEvent('agent_steered', { instruction });
      if (isUpstreamFormat) {
        sendProtocolResponse(id, 'steer', true, {
          status: 'steered',
          session_id: activeSession,
          instruction: instruction
        });
      } else {
        sendLegacyResponse(id, {
          status: 'steered',
          session_id: activeSession,
          instruction: instruction
        });
      }
      break;
    }

    case 'follow_up': {
      const content = params.content || params.message || '';
      sendEvent('follow_up_received', { content });
      if (isUpstreamFormat) {
        sendProtocolResponse(id, 'follow_up', true, {
          status: 'followed_up',
          session_id: activeSession,
          content: content
        });
      } else {
        sendLegacyResponse(id, {
          status: 'followed_up',
          session_id: activeSession,
          content: content
        });
      }
      break;
    }

    case 'abort': {
      const opId = params.operation_id || '';
      const reason = params.reason || 'Caller requested abort';
      isAborted = true;
      sendEvent('operation_aborted', { operation_id: opId, reason: reason });
      if (isUpstreamFormat) {
        sendProtocolResponse(id, 'abort', true, {
          status: 'aborted',
          operation_id: opId,
          reason: reason
        });
      } else {
        sendLegacyResponse(id, {
          status: 'aborted',
          operation_id: opId,
          reason: reason
        });
      }
      break;
    }

    case 'get_state':
    case 'state': {
      const stateObj = {
        session_id: activeSession,
        state: isAborted ? 'ABORTED' : 'IDLE',
        active_operations: isAborted ? 0 : operationCounter,
        workspace_dir: params.workspace_dir || process.cwd(),
        model: currentModel
      };
      if (isUpstreamFormat) {
        sendProtocolResponse(id, 'get_state', true, stateObj);
      } else {
        sendLegacyResponse(id, stateObj);
      }
      break;
    }

    case 'get_entries': {
      if (isUpstreamFormat) {
        sendProtocolResponse(id, 'get_entries', true, { entries: entriesHistory });
      } else {
        sendLegacyResponse(id, { entries: entriesHistory });
      }
      break;
    }

    case 'get_tree': {
      if (isUpstreamFormat) {
        sendProtocolResponse(id, 'get_tree', true, { tree: treeState });
      } else {
        sendLegacyResponse(id, { tree: treeState });
      }
      break;
    }

    case 'compact': {
      entriesHistory = entriesHistory.slice(-5);
      if (isUpstreamFormat) {
        sendProtocolResponse(id, 'compact', true, { status: 'compacted', entries_count: entriesHistory.length });
      } else {
        sendLegacyResponse(id, { status: 'compacted', entries_count: entriesHistory.length });
      }
      break;
    }

    case 'retry': {
      if (isUpstreamFormat) {
        sendProtocolResponse(id, 'retry', true, { status: 'retried', session_id: activeSession });
      } else {
        sendLegacyResponse(id, { status: 'retried', session_id: activeSession });
      }
      break;
    }

    case 'set_model': {
      currentModel = params.model || currentModel;
      if (isUpstreamFormat) {
        sendProtocolResponse(id, 'set_model', true, { model: currentModel });
      } else {
        sendLegacyResponse(id, { model: currentModel });
      }
      break;
    }

    case 'simulate_crash': {
      process.stderr.write('Step-Code Test Double simulating immediate process crash\n');
      process.exit(2);
      break;
    }

    case 'tool_call': {
      const toolAction = params.action || params.tool || 'read_file';
      const target = params.target || '';
      const opId = params.operation_id || `op_${Date.now()}`;

      sendEvent('tool_execution_start', { operation_id: opId, action: toolAction, target: target });
      sendEvent('tool_result', { operation_id: opId, exit_code: 0, output: `Executed ${toolAction} on ${target}` });
      sendEvent('tool_execution_end', { operation_id: opId, status: 'SUCCESS' });

      const resObj = {
        operation_id: opId,
        status: 'SETTLED',
        result: { exit_code: 0, output: `Result of ${toolAction}` }
      };
      if (isUpstreamFormat) {
        sendProtocolResponse(id, 'tool_call', true, resObj);
      } else {
        sendLegacyResponse(id, resObj);
      }
      break;
    }

    case 'execute_tool_with_interception': {
      const toolAction = params.action || params.tool || 'read_file';
      const target = params.target || '';
      const toolParams = params.parameters || {};
      const opId = params.operation_id || `op_intercept_${Date.now()}`;

      sendEvent('tool_execution_start', { operation_id: opId, action: toolAction, target: target });

      interceptViaExtension(toolAction, target, toolParams, (authResult) => {
        if (!authResult || !authResult.allowed) {
          const reason = authResult ? authResult.reason : 'Denied by S-Class';
          sendEvent('tool_result', {
            operation_id: opId,
            exit_code: 1,
            output: `BLOCKED by S-Class: ${reason}`
          });
          sendEvent('tool_execution_end', { operation_id: opId, status: 'BLOCKED' });
          if (isUpstreamFormat) {
            sendProtocolResponse(id, 'execute_tool_with_interception', false, {
              operation_id: opId,
              status: 'BLOCKED',
              allowed: false,
              reason: reason
            });
          } else {
            sendLegacyResponse(id, {
              operation_id: opId,
              status: 'BLOCKED',
              allowed: false,
              reason: reason
            });
          }
          return;
        }

        // Allowed: proceed with tool effect
        sendEvent('tool_result', {
          operation_id: opId,
          exit_code: 0,
          output: `Executed ${toolAction} on ${target} with S-Class authorization`
        });
        sendEvent('tool_execution_end', { operation_id: opId, status: 'SUCCESS' });
        if (isUpstreamFormat) {
          sendProtocolResponse(id, 'execute_tool_with_interception', true, {
            operation_id: opId,
            status: 'SETTLED',
            allowed: true,
            result: { exit_code: 0, output: `Result of ${toolAction}` }
          });
        } else {
          sendLegacyResponse(id, {
            operation_id: opId,
            status: 'SETTLED',
            allowed: true,
            result: { exit_code: 0, output: `Result of ${toolAction}` }
          });
        }
      });
      break;
    }

    default:
      sendError(id, -32601, `Method not found: ${commandType}`);
  }
}
