"""
S-Class EOS V11.2 - Schemathesis Isolated Subprocess Worker.
Runs strictly inside a child process to isolate Schemathesis and Hypothesis execution from S-Class memory.
Reads execution payload from stdin and emits normalized JSON to stdout.
"""

import sys
import os
import json
import time
import importlib
from typing import Dict, Any, List, Optional


def main():
    t_start = time.monotonic()
    try:
        raw_input = sys.stdin.read()
        if not raw_input.strip():
            _emit_output(
                status="INPUT_INVALID",
                exit_code=2,
                violations=[],
                stats={"endpoints_tested": 0, "operations_tested": 0, "checks_executed": 0, "violations_count": 0, "duration_sec": 0.0},
                diagnostics=[{"error": "Empty input payload passed to worker."}],
                summary="Worker failed: Empty stdin payload."
            )
            return

        payload = json.loads(raw_input)
    except Exception as e:
        _emit_output(
            status="INPUT_INVALID",
            exit_code=2,
            violations=[],
            stats={"endpoints_tested": 0, "operations_tested": 0, "checks_executed": 0, "violations_count": 0, "duration_sec": 0.0},
            diagnostics=[{"error": f"Invalid JSON payload: {type(e).__name__}: {str(e)}"}],
            summary="Worker failed: Unparseable input payload."
        )
        return

    schema_dict = payload.get("schema_dict")
    base_url = payload.get("base_url")
    app_module_str = payload.get("app_module")
    app_attr_str = payload.get("app_callable")
    max_examples = payload.get("max_examples", 5)

    # 1. Validate Schema
    if not schema_dict or not isinstance(schema_dict, dict) or not isinstance(schema_dict.get("paths"), dict):
        _emit_output(
            status="INPUT_INVALID",
            exit_code=2,
            violations=[],
            stats={"endpoints_tested": 0, "operations_tested": 0, "checks_executed": 0, "violations_count": 0, "duration_sec": 0.0},
            diagnostics=[{"error": "Schema is missing or 'paths' is not a dictionary."}],
            summary="Worker failed: Invalid schema dictionary."
        )
        return

    # 2. Import Schemathesis inside worker process
    try:
        import schemathesis
    except ImportError as e:
        _emit_output(
            status="TOOL_NOT_AVAILABLE",
            exit_code=3,
            violations=[],
            stats={"endpoints_tested": 0, "operations_tested": 0, "checks_executed": 0, "violations_count": 0, "duration_sec": 0.0},
            diagnostics=[{"error": f"Schemathesis import failed: {str(e)}"}],
            summary="Worker failed: Schemathesis package is not installed."
        )
        return

    # 3. Load Target WSGI App if specified
    target_app = None
    if app_module_str and app_attr_str:
        try:
            # Ensure CWD and tests/ are in sys.path
            cwd = os.getcwd()
            if cwd not in sys.path:
                sys.path.insert(0, cwd)
            tests_dir = os.path.join(cwd, "tests")
            if os.path.exists(tests_dir) and tests_dir not in sys.path:
                sys.path.insert(0, tests_dir)

            try:
                mod = importlib.import_module(app_module_str)
            except ModuleNotFoundError:
                if not app_module_str.startswith("tests."):
                    mod = importlib.import_module(f"tests.{app_module_str}")
                else:
                    raise

            target_app = getattr(mod, app_attr_str)
        except Exception as e:
            _emit_output(
                status="TOOL_EXECUTION_FAILED",
                exit_code=1,
                violations=[],
                stats={"endpoints_tested": 0, "operations_tested": 0, "checks_executed": 0, "violations_count": 0, "duration_sec": 0.0},
                diagnostics=[{"error": f"Failed loading target app {app_module_str}:{app_attr_str}: {str(e)}"}],
                summary=f"Worker failed to load target WSGI callable: {str(e)}"
            )
            return

    # 4. Parse Schema
    try:
        if target_app is not None and callable(target_app):
            def wrapped_app(environ, start_response):
                if environ.get("PATH_INFO") == "/__sclass_schema__.json":
                    start_response("200 OK", [("Content-Type", "application/json")])
                    return [json.dumps(schema_dict).encode("utf-8")]
                return target_app(environ, start_response)

            schema = schemathesis.openapi.from_wsgi("/__sclass_schema__.json", app=wrapped_app)
        else:
            schema = schemathesis.openapi.from_dict(schema_dict)
    except Exception as e:
        _emit_output(
            status="INPUT_INVALID",
            exit_code=2,
            violations=[],
            stats={"endpoints_tested": 0, "operations_tested": 0, "checks_executed": 0, "violations_count": 0, "duration_sec": 0.0},
            diagnostics=[{"error": f"Schemathesis failed parsing OpenAPI schema: {str(e)}"}],
            summary=f"Worker failed: Schema parse error: {str(e)}"
        )
        return

    # 5. Discover Operations
    try:
        endpoints = list(schema)
        raw_ops = list(schema.get_all_operations())
        operations = []
        for item in raw_ops:
            op = item.ok() if hasattr(item, "ok") else item
            if op is not None:
                operations.append(op)

        if not operations:
            _emit_output(
                status="INSUFFICIENT_EVIDENCE",
                exit_code=0,
                violations=[],
                stats={"endpoints_tested": len(endpoints), "operations_tested": 0, "checks_executed": 0, "violations_count": 0, "duration_sec": 0.0},
                diagnostics=[{"warning": "Schema contains zero reachable operations."}],
                summary="Worker inconclusive: Zero operations discovered in schema."
            )
            return
    except Exception as e:
        _emit_output(
            status="TOOL_EXECUTION_FAILED",
            exit_code=1,
            violations=[],
            stats={"endpoints_tested": 0, "operations_tested": 0, "checks_executed": 0, "violations_count": 0, "duration_sec": 0.0},
            diagnostics=[{"error": f"Failed inspecting operations: {str(e)}"}],
            summary=f"Worker tool error: {str(e)}"
        )
        return

    # 6. Execute Campaigns across Operations
    violations: List[Dict[str, Any]] = []
    checks_executed = 0
    operations_count = 0

    try:
        for operation in operations:
            operations_count += 1
            path_key = operation.path
            method = operation.method
            strategy = operation.as_strategy()

            for _ in range(max(1, max_examples)):
                checks_executed += 1
                try:
                    case = strategy.example()
                except Exception as e:
                    violations.append({
                        "error_type": type(e).__name__,
                        "message": str(e),
                        "path": path_key,
                        "method": method.upper(),
                        "status_code": None,
                        "curl_command": None,
                        "schema_path": None,
                        "details": {"raw_exception": type(e).__name__}
                    })
                    continue

                curl_cmd = None
                if hasattr(case, "as_curl_command"):
                    try:
                        curl_cmd = case.as_curl_command()
                    except Exception:
                        curl_cmd = None

                # Execute WSGI App
                if target_app is not None and callable(target_app):
                    response = None
                    try:
                        response = case.call()
                        if response.status_code >= 500:
                            violations.append({
                                "error_type": "ServerError",
                                "message": f"Server Error ({response.status_code}) on {method.upper()} {path_key}: {response.text[:200]}",
                                "path": path_key,
                                "method": method.upper(),
                                "status_code": response.status_code,
                                "curl_command": curl_cmd,
                                "schema_path": None,
                                "details": {}
                            })
                        case.validate_response(response)
                    except (Exception, BaseException) as e:
                        _extract_violations_from_exception(e, violations, path_key, method, getattr(response, "status_code", None), curl_cmd)

                # Execute Live Base URL
                elif base_url:
                    response = None
                    try:
                        response = case.call(base_url=base_url)
                        if response.status_code >= 500:
                            violations.append({
                                "error_type": "ServerError",
                                "message": f"Server Error ({response.status_code}) on {method.upper()} {path_key}: {response.text[:200]}",
                                "path": path_key,
                                "method": method.upper(),
                                "status_code": response.status_code,
                                "curl_command": curl_cmd,
                                "schema_path": None,
                                "details": {}
                            })
                        case.validate_response(response)
                    except (Exception, BaseException) as e:
                        _extract_violations_from_exception(e, violations, path_key, method, getattr(response, "status_code", None), curl_cmd)

    except Exception as e:
        _emit_output(
            status="TOOL_EXECUTION_FAILED",
            exit_code=1,
            violations=violations,
            stats={
                "endpoints_tested": len(endpoints),
                "operations_tested": operations_count,
                "checks_executed": checks_executed,
                "violations_count": len(violations),
                "duration_sec": round(time.monotonic() - t_start, 4)
            },
            diagnostics=[{"error": f"Unhandled worker exception: {type(e).__name__}: {str(e)}"}],
            summary=f"Worker tool execution failure: {str(e)}"
        )
        return

    duration = round(time.monotonic() - t_start, 4)
    stats = {
        "endpoints_tested": len(endpoints),
        "operations_tested": operations_count,
        "checks_executed": checks_executed,
        "violations_count": len(violations),
        "duration_sec": duration
    }

    if len(violations) > 0:
        _emit_output(
            status="TARGET_CONTRACT_VIOLATED",
            exit_code=1,
            violations=violations,
            stats=stats,
            diagnostics=[{"violation": v} for v in violations],
            summary=f"Contract violated: {len(violations)} violations across {operations_count} operations."
        )
    elif checks_executed == 0:
        _emit_output(
            status="INSUFFICIENT_EVIDENCE",
            exit_code=0,
            violations=[],
            stats=stats,
            diagnostics=[{"warning": "Zero checks executed."}],
            summary="Worker inconclusive: Zero checks evaluated."
        )
    else:
        _emit_output(
            status="TARGET_CLEAN",
            exit_code=0,
            violations=[],
            stats=stats,
            diagnostics=[],
            summary=f"Target clean: All {checks_executed} checks passed."
        )


def _extract_violations_from_exception(exc, violations_list, path, method, status_code, curl_cmd):
    exceptions_to_process = []
    if hasattr(exc, "exceptions"):
        exceptions_to_process.extend(getattr(exc, "exceptions", []))
    elif hasattr(exc, "__cause__") and exc.__cause__ and hasattr(exc.__cause__, "exceptions"):
        exceptions_to_process.extend(getattr(exc.__cause__, "exceptions", []))
    else:
        exceptions_to_process.append(exc)

    for sub_exc in exceptions_to_process:
        sub_type = type(sub_exc).__name__
        msg = str(sub_exc)
        sub_status_code = getattr(sub_exc, "status_code", None) or status_code
        sub_curl = curl_cmd

        case_obj = getattr(sub_exc, "case", None)
        if case_obj is not None:
            path = path or str(getattr(case_obj, "path", ""))
            method = method or str(getattr(case_obj, "method", ""))
            if not sub_curl and hasattr(case_obj, "as_curl_command"):
                try:
                    sub_curl = case_obj.as_curl_command()
                except Exception:
                    pass

        response_obj = getattr(sub_exc, "response", None)
        if response_obj is not None and hasattr(response_obj, "status_code"):
            sub_status_code = response_obj.status_code

        schema_path = getattr(sub_exc, "schema_path", None)
        if isinstance(schema_path, list):
            schema_path = "/".join(str(p) for p in schema_path)

        violations_list.append({
            "error_type": sub_type,
            "message": msg,
            "path": path or "unknown",
            "method": (method or "unknown").upper(),
            "status_code": sub_status_code,
            "curl_command": sub_curl,
            "schema_path": schema_path,
            "details": {"raw_exception_class": sub_type}
        })


def _emit_output(status: str, exit_code: int, violations: list, stats: dict, diagnostics: list, summary: str):
    output = {
        "status": status,
        "exit_code": exit_code,
        "violations": violations,
        "stats": stats,
        "diagnostics": diagnostics,
        "summary": summary
    }
    sys.stdout.write(json.dumps(output) + "\n")
    sys.stdout.flush()
    sys.exit(0 if status == "TARGET_CLEAN" else (1 if status == "TARGET_CONTRACT_VIOLATED" else exit_code))


if __name__ == "__main__":
    main()
