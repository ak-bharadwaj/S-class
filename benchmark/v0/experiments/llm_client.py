#!/usr/bin/env python3
"""
S-Class EOS - Gate 1.2 Provider-Neutral LLM Client & Provenance Recorder
(benchmark/v0/experiments/llm_client.py)

Responsibilities:
- Provider-neutral LLM execution (Google Gemini, OpenAI, Anthropic, Ollama).
- Zero silent mocks / simulated fallbacks: Fails immediately if credentials or models are unavailable.
- Automatic backoff on 429 rate-limits: Gracefully handles free-tier RPM limits without aborting.
- Full provenance recording: Captures model version, git commit, temperature, latency, token usage, prompts, and raw outputs.
"""

import os
import sys
import json
import time
import subprocess
import warnings
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple

RUNNER_VERSION = "2.0.0-gate1.2-provenance"

def get_git_commit() -> str:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True
        )
        return res.stdout.strip()
    except Exception:
        return "UNKNOWN_COMMIT"

def load_dotenv_fallback():
    env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env"))
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'").strip('"')
                    if k not in os.environ:
                        os.environ[k] = v

load_dotenv_fallback()

class LLMProvenanceClient:
    """
    Provider-neutral LLM execution client with immutable provenance recording.
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096
    ):
        self.git_commit = get_git_commit()
        self.temperature = temperature
        self.max_tokens = max_tokens

        # Resolve Provider & API Key
        self.provider = (provider or os.environ.get("MODEL_PROVIDER") or "").lower()
        self.api_key = api_key or os.environ.get("API_KEY")

        if not self.provider:
            if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
                self.provider = "gemini"
            elif os.environ.get("OPENAI_API_KEY"):
                self.provider = "openai"
            elif os.environ.get("ANTHROPIC_API_KEY"):
                self.provider = "anthropic"
            else:
                self.provider = "gemini"

        if self.provider in ["gemini", "google"]:
            self.provider = "gemini"
            self.api_key = self.api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
            self.model_name = model_name or os.environ.get("MODEL_NAME") or "gemini-flash-lite-latest"
        elif self.provider == "openai":
            self.api_key = self.api_key or os.environ.get("OPENAI_API_KEY")
            self.model_name = model_name or os.environ.get("MODEL_NAME") or "gpt-4o-mini"
        elif self.provider == "anthropic":
            self.api_key = self.api_key or os.environ.get("ANTHROPIC_API_KEY")
            self.model_name = model_name or os.environ.get("MODEL_NAME") or "claude-3-5-sonnet-20241022"
        elif self.provider == "ollama":
            self.model_name = model_name or os.environ.get("MODEL_NAME") or "llama3.1"
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")

    def call_model(
        self,
        system_prompt: str,
        user_prompt: str,
        task_id: str,
        experiment_id: str,
        input_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Executes real LLM call, records full provenance, and returns structured result.
        Strictly raises Exception on failure; never generates mock fallback data.
        """
        start_time = time.time()
        start_iso = datetime.now(timezone.utc).isoformat()

        raw_text = ""
        prompt_tokens = 0
        completion_tokens = 0

        max_retries = 5
        base_backoff = 15.0

        for attempt in range(1, max_retries + 1):
            try:
                if self.provider == "gemini":
                    raw_text, prompt_tokens, completion_tokens = self._call_gemini(system_prompt, user_prompt)
                elif self.provider == "openai":
                    raw_text, prompt_tokens, completion_tokens = self._call_openai(system_prompt, user_prompt)
                elif self.provider == "anthropic":
                    raw_text, prompt_tokens, completion_tokens = self._call_anthropic(system_prompt, user_prompt)
                elif self.provider == "ollama":
                    raw_text, prompt_tokens, completion_tokens = self._call_ollama(system_prompt, user_prompt)
                else:
                    raise RuntimeError(f"Unknown provider execution engine: {self.provider}")
                break
            except Exception as e:
                err_str = str(e).lower()
                if ("429" in err_str or "quota" in err_str or "rate" in err_str or "resourceexhausted" in err_str) and attempt < max_retries:
                    wait_sec = base_backoff * attempt
                    print(f"[{task_id}] Rate-limit reached (Attempt {attempt}/{max_retries}). Backing off for {wait_sec}s...")
                    time.sleep(wait_sec)
                else:
                    raise e

        latency_ms = round((time.time() - start_time) * 1000, 2)
        total_tokens = prompt_tokens + completion_tokens

        # Clean JSON markdown fences if present
        cleaned_json = raw_text.strip()
        if cleaned_json.startswith("```"):
            lines = cleaned_json.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned_json = "\n".join(lines).strip()

        try:
            parsed_output = json.loads(cleaned_json)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"Failed to parse valid JSON from model response for task {task_id}:\n"
                f"Raw Response: {raw_text}\nParse Error: {e}"
            )

        provenance_record = {
            "provenance": {
                "experiment_id": experiment_id,
                "task_id": task_id,
                "runner_version": RUNNER_VERSION,
                "git_commit": self.git_commit,
                "timestamp_utc": start_iso,
                "latency_ms": latency_ms,
                "provider": self.provider,
                "model": self.model_name,
                "generation_settings": {
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens
                },
                "token_usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens
                },
                "estimated_cost_usd": self._estimate_cost(prompt_tokens, completion_tokens),
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "input_context": input_context or {}
            },
            "raw_output": raw_text,
            "parsed_output": parsed_output
        }

        return provenance_record

    def _call_gemini(self, system_prompt: str, user_prompt: str) -> Tuple[str, int, int]:
        if not self.api_key:
            raise RuntimeError(
                "GEMINI_API_KEY or GOOGLE_API_KEY environment variable is missing. "
                "Execution aborted to prevent unverified mock fallback."
            )
        
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            import google.generativeai as genai
            
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=system_prompt,
                generation_config={
                    "temperature": self.temperature,
                    "max_output_tokens": self.max_tokens,
                    "response_mime_type": "application/json"
                }
            )
            response = model.generate_content(user_prompt)
            raw_text = response.text or ""
            
            usage = getattr(response, "usage_metadata", None)
            p_tokens = getattr(usage, "prompt_token_count", 0) if usage else len(user_prompt.split())
            c_tokens = getattr(usage, "candidates_token_count", 0) if usage else len(raw_text.split())
            return raw_text, p_tokens, c_tokens

    def _call_openai(self, system_prompt: str, user_prompt: str) -> Tuple[str, int, int]:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is missing. Execution aborted.")
        import urllib.request
        url = "https://api.openai.com/v1/chat/completions"
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "response_format": {"type": "json_object"}
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        choices = data.get("choices", [])
        raw_text = choices[0].get("message", {}).get("content", "") if choices else ""
        usage = data.get("usage", {})
        return raw_text, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)

    def _call_anthropic(self, system_prompt: str, user_prompt: str) -> Tuple[str, int, int]:
        if not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is missing. Execution aborted.")
        import urllib.request
        url = "https://api.anthropic.com/v1/messages"
        payload = {
            "model": self.model_name,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        content = data.get("content", [])
        raw_text = content[0].get("text", "") if content else ""
        usage = data.get("usage", {})
        return raw_text, usage.get("input_tokens", 0), usage.get("output_tokens", 0)

    def _call_ollama(self, system_prompt: str, user_prompt: str) -> Tuple[str, int, int]:
        import urllib.request
        url = "http://localhost:11434/api/chat"
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "options": {"temperature": self.temperature},
            "stream": False,
            "format": "json"
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        raw_text = data.get("message", {}).get("content", "")
        return raw_text, data.get("prompt_eval_count", 0), data.get("eval_count", 0)

    def _estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        if "gemini-flash" in self.model_name:
            return round((prompt_tokens * 0.075 + completion_tokens * 0.30) / 1_000_000, 6)
        elif "gpt-4o-mini" in self.model_name:
            return round((prompt_tokens * 0.15 + completion_tokens * 0.60) / 1_000_000, 6)
        elif "claude-3-5-sonnet" in self.model_name:
            return round((prompt_tokens * 3.00 + completion_tokens * 15.00) / 1_000_000, 6)
        return 0.0
