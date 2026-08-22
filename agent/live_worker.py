"""
S-Class EOS V11.2 - D7 Live Model Worker Adapter (Bridge 2).
Adapts live multi-provider LLM inference (LLMProvider) to the D7 AgentWorkerProtocol.
Parses model responses into authenticated, hash-chained AgentMessage envelopes.
"""

from __future__ import annotations
import json
import re
import uuid
from typing import Any, Dict, List, Mapping, Optional, Sequence

from agent.models import (
    AgentSessionContext,
    AgentTurnResponse,
    AgentToolCall,
    AgentTurnStatus,
    AgentMessage,
    create_agent_message,
)
from agent.protocol import AgentWorkerProtocol
from benchmark.v0.engineering.llm_provider import LLMProvider, LLMProviderConfig, LLMResponse


class LiveModelWorker(AgentWorkerProtocol):
    """Concrete AgentWorkerProtocol adapter wrapping LLMProvider for real-model execution."""

    def __init__(
        self,
        provider: Optional[LLMProvider] = None,
        worker_id: Optional[str] = None,
        default_target_file: str = "target_module.py",
    ):
        self._provider = provider or LLMProvider(LLMProviderConfig(provider_type="mock_test"))
        self._worker_id = worker_id or f"live-worker-{self._provider.config.provider_type}"
        self._default_target_file = default_target_file

    @property
    def worker_id(self) -> str:
        return self._worker_id

    @property
    def provider(self) -> LLMProvider:
        return self._provider

    def _build_system_prompt(self, context: AgentSessionContext) -> str:
        """Constructs a strict system prompt guiding the model to emit structured S-Class tool calls."""
        lines = [
            "You are an S-Class Governed Cognitive Agent interacting with a formal authority verification kernel.",
            f"Active Task ID: {context.task_id}",
            f"Authoritative Source SHA: {context.source_sha}",
            f"Granted Capabilities: {', '.join(context.granted_capabilities)}",
            "",
            "You have access to the following governed proposal tools:",
            "1. `propose_test_run`: Propose executing a test file in an isolated workspace.",
            "   Arguments: {\"obligation_id\": str, \"target_test\": str, \"purpose\": str, \"parameters\": dict}",
            "2. `propose_code_patch`: Propose applying code modifications to a target file.",
            "   Arguments: {\"obligation_id\": str, \"target_file\": str, \"code_content\": str, \"purpose\": str}",
            "3. `inspect_file`: Read a file from the repository.",
            "   Arguments: {\"file_path\": str}",
            "4. `list_files`: List files in a repository directory.",
            "   Arguments: {\"directory_path\": str}",
            "",
            "RESPONSE FORMAT:",
            "To invoke a tool, output a JSON block wrapped in ```json ... ``` with fields:",
            "```json",
            "{",
            '  "thought": "Your step-by-step reasoning",',
            '  "tool": "propose_test_run" | "propose_code_patch" | "inspect_file" | "list_files",',
            '  "args": { ... arguments matching tool schema ... },',
            '  "status": "CONTINUE" | "COMPLETED"',
            "}",
            "```",
            "Alternatively, if writing complete python code for the target module, you may output a ```python ... ``` code fence."
        ]
        return "\n".join(lines)

    def _build_user_prompt(self, context: AgentSessionContext, history: Sequence[AgentMessage]) -> str:
        """Constructs the multi-turn conversational prompt from session context and message history."""
        lines = [
            f"Objective: {context.objective}",
            f"Current Turn: {context.turn_index} / {context.max_turns}",
            f"Budget Remaining: {context.remaining_budget_units:.2f} units",
            "",
            "Frontier Obligations:",
        ]
        for detail in context.frontier_details:
            obl_id = detail.get("obligation_id", "UNKNOWN")
            title = detail.get("title", "")
            cat = detail.get("category", "CORRECTNESS_FUNCTIONAL")
            lines.append(f"- [{obl_id}] ({cat}): {title}")

        if context.verification_feedback:
            lines.append("\nVerification Feedback / Failure Diagnostics:")
            for fb in context.verification_feedback:
                if isinstance(fb, dict):
                    lines.append(f"- {fb.get('feedback', fb)}")
                else:
                    lines.append(f"- {fb}")

        if history:
            lines.append("\nPrior Turn History:")
            for msg in history:
                payload = msg.payload
                thought = payload.get("thought", "")
                tool_calls = payload.get("tool_calls", [])
                lines.append(f"Turn {msg.sequence} (Worker: {msg.worker_id}):")
                if thought:
                    lines.append(f"  Thought: {thought}")
                for tc in tool_calls:
                    lines.append(f"  Tool Call: {tc.get('tool')} with args: {tc.get('args')}")

        lines.append("\nAnalyze the current state and provide your next reasoning step and tool call:")
        return "\n".join(lines)

    def _parse_model_response(self, text: str, context: AgentSessionContext) -> Dict[str, Any]:
        """Parses model text into structured tool calls and status payload."""
        thought = ""
        tool_calls: List[Dict[str, Any]] = []
        status = "CONTINUE"

        ALLOWED_TOOLS = {"propose_test_run", "propose_code_patch", "inspect_file", "list_files"}

        # 1. Attempt JSON block extraction
        json_blocks = re.findall(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
        for jb in json_blocks:
            try:
                data = json.loads(jb)
                if isinstance(data, dict):
                    thought = data.get("thought", thought)
                    if "status" in data and data["status"] in ("CONTINUE", "COMPLETED", "PAUSE_FOR_DISPATCH", "FAILED", "WORKER_TIMEOUT"):
                        status = data["status"]
                    if "tool" in data:
                        tool_name = str(data["tool"]).strip()
                        raw_args = data.get("args", {})
                        if not isinstance(raw_args, dict):
                            thought += f" [Rejected: Tool arguments for '{tool_name}' must be a dictionary]"
                            continue

                        # Strict tool name validation
                        if tool_name not in ALLOWED_TOOLS:
                            thought += f" [Rejected: Tool '{tool_name}' is not in allowed tool registry {sorted(ALLOWED_TOOLS)}]"
                            continue

                        # Strict argument schema validation
                        is_valid = True
                        if tool_name == "propose_test_run":
                            if not raw_args.get("target_test") or not isinstance(raw_args.get("target_test"), str):
                                thought += " [Rejected: 'target_test' is required and must be a non-empty string]"
                                is_valid = False
                        elif tool_name == "propose_code_patch":
                            if not raw_args.get("code_content") or not isinstance(raw_args.get("code_content"), str):
                                thought += " [Rejected: 'code_content' is required and must be a non-empty string]"
                                is_valid = False
                        elif tool_name == "inspect_file":
                            if not raw_args.get("file_path") or not isinstance(raw_args.get("file_path"), str):
                                thought += " [Rejected: 'file_path' is required and must be a non-empty string]"
                                is_valid = False
                        elif tool_name == "list_files":
                            if "directory_path" in raw_args and not isinstance(raw_args.get("directory_path"), str):
                                thought += " [Rejected: 'directory_path' must be a string]"
                                is_valid = False

                        if is_valid:
                            tool_calls.append({
                                "call_id": f"CALL-{uuid.uuid4().hex[:6].upper()}",
                                "tool": tool_name,
                                "args": raw_args,
                            })
            except Exception as ex:
                thought += f" [JSON parse error: {ex}]"

        # 2. If no tool found, attempt Python code fence extraction
        if not tool_calls:
            py_blocks = re.findall(r"```python\s*(.*?)\s*```", text, re.DOTALL)
            if py_blocks:
                first_obl_id = (
                    context.frontier_obligation_ids[0]
                    if context.frontier_obligation_ids
                    else "OBL-DEFAULT-1"
                )
                code_content = py_blocks[0]
                thought = text[:text.find("```python")].strip() or "Proposing code implementation"
                tool_calls.append({
                    "call_id": f"CALL-{uuid.uuid4().hex[:6].upper()}",
                    "tool": "propose_code_patch",
                    "args": {
                        "obligation_id": first_obl_id,
                        "target_file": self._default_target_file,
                        "code_content": code_content,
                        "purpose": "Apply synthesized model patch",
                    },
                })
            else:
                if not thought:
                    thought = text.strip()
                if "done" in text.lower() or "completed" in text.lower() or "all tests pass" in text.lower():
                    status = "COMPLETED"

        return {
            "thought": thought,
            "status": status,
            "tool_calls": tool_calls,
        }

    def generate_inbound_message(
        self,
        context: AgentSessionContext,
        sequence: int,
        previous_digest: str,
        history: Sequence[AgentMessage],
    ) -> AgentMessage:
        """Executes one cognitive turn via LLMProvider and emits an authentic AgentMessage envelope."""
        system_prompt = self._build_system_prompt(context)
        user_prompt = self._build_user_prompt(context, history)

        try:
            llm_resp: LLMResponse = self._provider.generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
            )
            parsed = self._parse_model_response(llm_resp.text, context)
            cost_usd = getattr(llm_resp, "cost_usd", 0.0)
        except TimeoutError as te:
            parsed = {
                "thought": f"Model timeout error: {te}",
                "status": "WORKER_TIMEOUT",
                "tool_calls": [],
            }
            cost_usd = 0.0
        except Exception as exc:
            parsed = {
                "thought": f"Model inference error: {exc}",
                "status": "FAILED",
                "tool_calls": [],
            }
            cost_usd = 0.0

        payload = {
            "thought": parsed["thought"],
            "status": parsed["status"],
            "advisory_cost_usd": cost_usd,
            "tool_calls": parsed["tool_calls"],
        }

        return create_agent_message(
            session_id=context.session_id,
            worker_id=self._worker_id,
            sequence=sequence,
            message_type="AGENT_TURN",
            payload=payload,
            previous_digest=previous_digest,
        )
