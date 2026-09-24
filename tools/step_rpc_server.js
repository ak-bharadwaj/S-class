#!/usr/bin/env node
/**
 * DEPRECATED SIMULATION DOUBLE SHIM.
 * 
 * Notice (H1 Mandate 1.1):
 * This script is an alias for StepCodeRpcTestDouble (tools/step_code_rpc_test_double.js).
 * It is NOT the canonical Step-Code runtime and must never be preferred in production discovery.
 * Canonical execution requires the real Step-Code engine.
 */

require('./step_code_rpc_test_double.js');
