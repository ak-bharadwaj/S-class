#!/usr/bin/env node
/**
 * Step-Code JSONL RPC Server implementation for S-Class integration testing and runtime adapter.
 * Complies with Step-Code's documented `step --mode rpc` JSONL protocol.
 * 
 * Strict transport protocol:
 * - Line-delimited UTF-8 JSON over stdio.
 * - Single byte LF (0x0A, \n) line framing. Never split on generic Unicode line breaks.
 * - JSON-RPC 2.0 message envelope.
 */

const fs = require('fs');
const path = require('path');

const args = process.argv.slice(2);
let modeIndex = args.indexOf('--mode');
let mode = modeIndex !== -1 && args.length > modeIndex + 1 ? args[modeIndex + 1] : 'rpc';

if (mode !== 'rpc') {
  process.stderr.write(`Unsupported mode: ${mode}. Only --mode rpc is supported.\n`);
  process.exit(1);
}

let activeSession = `sess_${Date.now()}`;
let operationCounter = 0;
let isAborted = false;

// Buffer for strict byte-level LF (0x0A) line splitting
let buffer = Buffer.alloc(0);

process.stdin.on('data', (chunk) => {
  buffer = Buffer.concat([buffer, chunk]);
  let lfIndex;
  while ((lfIndex = buffer.indexOf(0x0A)) !== -1) {
    const lineBuffer = buffer.slice(0, lfIndex);
    buffer = buffer.slice(lfIndex + 1);
    
    // Ignore empty lines
    if (lineBuffer.length === 0) continue;
    // Strip trailing \r if present (CRLF normalization to LF)
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

function sendResponse(id, result) {
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
  send({
    jsonrpc: '2.0',
    method: 'event',
    params: {
      event_type: eventType,
      session_id: activeSession,
      timestamp: new Date().toISOString(),
      runtime: 'step-code',
      adapter_version: '1.0.0',
      payload: payload
    }
  });
}

let pendingAuthorizations = new Map();
let authReqCounter = 0;

function requestAuthorization(toolAction, target, parameters, callback) {
  authReqCounter++;
  const authId = `auth_req_${authReqCounter}_${Date.now()}`;
  pendingAuthorizations.set(authId, callback);
  send({
    jsonrpc: '2.0',
    id: authId,
    method: 'intercept_tool_call',
    params: {
      action: toolAction,
      target: target,
      parameters: parameters,
      session_id: activeSession
    }
  });
}

function handleMessage(msg) {
  const { id, method, params } = msg;

  if (!method) {
    // Response to a tool_call authorization request from us
    if (id !== undefined && pendingAuthorizations.has(id)) {
      const cb = pendingAuthorizations.get(id);
      pendingAuthorizations.delete(id);
      cb(msg.result || msg.error);
    }
    return;
  }

  switch (method) {
    case 'health':
      sendResponse(id, {
        status: 'healthy',
        runtime: 'step-code',
        version: '1.0.0',
        active_session: activeSession
      });
      break;

    case 'prompt': {
      const promptText = (params && params.prompt) || '';
      const sessId = (params && params.session_id) || activeSession;
      activeSession = sessId;
      operationCounter++;
      const opId = `op_step_${operationCounter}_${Date.now()}`;

      sendEvent('tool_execution_start', { operation_id: opId, prompt: promptText });

      // Emit normalized tool lifecycle events
      sendEvent('tool_call', {
        operation_id: opId,
        tool: 'execute_step',
        action: 'run_prompt',
        target: promptText.slice(0, 50),
        parameters: params || {}
      });

      sendEvent('tool_execution_update', { operation_id: opId, progress: 0.5 });
      sendEvent('tool_result', { operation_id: opId, exit_code: 0, output: `Completed: ${promptText}` });
      sendEvent('tool_execution_end', { operation_id: opId, status: 'SUCCESS' });

      sendResponse(id, {
        status: 'ok',
        operation_id: opId,
        session_id: activeSession,
        output: `Step-Code completed prompt: ${promptText}`,
        untrusted_candidate: true
      });
      break;
    }

    case 'steer': {
      const instruction = (params && params.instruction) || '';
      sendEvent('agent_steered', { instruction });
      sendResponse(id, {
        status: 'steered',
        session_id: activeSession,
        instruction: instruction
      });
      break;
    }

    case 'follow_up': {
      const content = (params && params.content) || '';
      sendEvent('follow_up_received', { content });
      sendResponse(id, {
        status: 'followed_up',
        session_id: activeSession,
        content: content
      });
      break;
    }

    case 'abort': {
      const opId = (params && params.operation_id) || '';
      const reason = (params && params.reason) || 'Caller requested abort';
      isAborted = true;
      sendEvent('operation_aborted', { operation_id: opId, reason: reason });
      sendResponse(id, {
        status: 'aborted',
        operation_id: opId,
        reason: reason
      });
      break;
    }

    case 'state': {
      sendResponse(id, {
        session_id: activeSession,
        state: isAborted ? 'ABORTED' : 'IDLE',
        active_operations: isAborted ? 0 : operationCounter,
        workspace_dir: (params && params.workspace_dir) || process.cwd()
      });
      break;
    }

    case 'simulate_crash': {
      process.stderr.write('Step-Code simulating immediate process crash\n');
      process.exit(2);
      break;
    }

    case 'tool_call': {
      // Direct tool call execution simulation
      const toolAction = (params && params.action) || 'read_file';
      const target = (params && params.target) || '';
      const opId = (params && params.operation_id) || `op_${Date.now()}`;
      
      sendEvent('tool_execution_start', { operation_id: opId, action: toolAction, target: target });
      sendEvent('tool_result', { operation_id: opId, exit_code: 0, output: `Executed ${toolAction} on ${target}` });
      sendEvent('tool_execution_end', { operation_id: opId, status: 'SUCCESS' });
      
      sendResponse(id, {
        operation_id: opId,
        status: 'SETTLED',
        result: { exit_code: 0, output: `Result of ${toolAction}` }
      });
      break;
    }

    case 'execute_tool_with_interception': {
      const toolAction = (params && params.action) || 'read_file';
      const target = (params && params.target) || '';
      const toolParams = (params && params.parameters) || {};
      const opId = (params && params.operation_id) || `op_intercept_${Date.now()}`;

      sendEvent('tool_execution_start', { operation_id: opId, action: toolAction, target: target });

      // Request S-Class extension tool authorization before effect (Part C7)
      requestAuthorization(toolAction, target, toolParams, (authResult) => {
        if (!authResult || !authResult.allowed) {
          const reason = authResult ? authResult.reason : 'Denied by S-Class';
          sendEvent('tool_result', {
            operation_id: opId,
            exit_code: 1,
            output: `BLOCKED by S-Class: ${reason}`
          });
          sendEvent('tool_execution_end', { operation_id: opId, status: 'BLOCKED' });
          sendResponse(id, {
            operation_id: opId,
            status: 'BLOCKED',
            allowed: false,
            reason: reason
          });
          return;
        }

        // Allowed: proceed with tool effect
        sendEvent('tool_result', {
          operation_id: opId,
          exit_code: 0,
          output: `Executed ${toolAction} on ${target} with S-Class authorization`
        });
        sendEvent('tool_execution_end', { operation_id: opId, status: 'SUCCESS' });
        sendResponse(id, {
          operation_id: opId,
          status: 'SETTLED',
          allowed: true,
          result: { exit_code: 0, output: `Result of ${toolAction}` }
        });
      });
      break;
    }

    default:
      sendError(id, -32601, `Method not found: ${method}`);
  }
}
