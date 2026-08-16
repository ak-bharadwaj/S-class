#!/usr/bin/env python3
"""
S-Class EOS - Gate 1.6B LLM Model Provider Interface
(benchmark/v0/engineering/llm_provider.py)

Provides a unified interface for executing prompts against live LLM model providers
(Gemini, OpenAI, Anthropic, or OpenAI-compatible custom endpoints) for B1, B2, and B3 baselines.

Captures complete provenance:
- Model version / provider
- Prompt & system prompt
- Raw response text
- Token counts (input / output)
- Latency (seconds)
- Estimated cost (USD)
- Timestamp & System Metadata
"""

import os
import sys
import time
import json
import urllib.request
import urllib.parse
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

class ProviderAPIKeyMissingError(Exception):
    """Raised when no valid API key or endpoint is configured for real execution."""
    pass

@dataclass
class LLMProviderConfig:
    provider_type: str = "auto"  # auto, gemini, openai, anthropic, custom_http, mock_test
    model_name: str = "gemini-2.5-flash"
    temperature: float = 0.2
    max_tokens: int = 4096
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    timeout_sec: int = 60

@dataclass
class LLMResponse:
    text: str
    model_name: str
    provider_type: str
    prompt_tokens: int
    completion_tokens: int
    latency_sec: float
    cost_usd: float
    timestamp: str
    raw_metadata: Dict[str, Any] = field(default_factory=dict)
    is_mock: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class LLMProvider:
    def __init__(self, config: Optional[LLMProviderConfig] = None, allow_mock_fallback: bool = False):
        self.config = config or LLMProviderConfig()
        self.allow_mock_fallback = allow_mock_fallback
        self._resolve_credentials()

    def _resolve_credentials(self):
        # Infer provider from environment if auto
        if self.config.provider_type == "auto":
            if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
                self.config.provider_type = "gemini"
                self.config.api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
                if not self.config.model_name or "gemini" not in self.config.model_name:
                    self.config.model_name = os.environ.get("LLM_MODEL", "gemini-2.5-flash")
            elif os.environ.get("OPENAI_API_KEY"):
                self.config.provider_type = "openai"
                self.config.api_key = os.environ.get("OPENAI_API_KEY")
                if not self.config.model_name or "gemini" in self.config.model_name:
                    self.config.model_name = os.environ.get("LLM_MODEL", "gpt-4o-mini")
            elif os.environ.get("ANTHROPIC_API_KEY"):
                self.config.provider_type = "anthropic"
                self.config.api_key = os.environ.get("ANTHROPIC_API_KEY")
                if not self.config.model_name or "gemini" in self.config.model_name:
                    self.config.model_name = os.environ.get("LLM_MODEL", "claude-3-5-haiku-20241022")
            elif os.environ.get("LLM_API_BASE_URL"):
                self.config.provider_type = "custom_http"
                self.config.base_url = os.environ.get("LLM_API_BASE_URL")
                self.config.api_key = os.environ.get("LLM_API_KEY", "dummy")
                self.config.model_name = os.environ.get("LLM_MODEL", "local-model")
            elif self.allow_mock_fallback:
                self.config.provider_type = "mock_test"
            else:
                raise ProviderAPIKeyMissingError(
                    "No valid LLM API key (GEMINI_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY) "
                    "or endpoint (LLM_API_BASE_URL) found in environment. "
                    "Genuine agent benchmark execution requires live provider credentials."
                )

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> LLMResponse:
        start_time = time.time()
        timestamp_str = datetime.now(timezone.utc).isoformat()

        if self.config.provider_type == "mock_test":
            if not self.allow_mock_fallback:
                raise ProviderAPIKeyMissingError("Mock test provider invoked when allow_mock_fallback is False.")
            # Explicit test harness driver response
            mock_text = "# Mock Test Provider Response\ndef target_function(): pass\n"
            return LLMResponse(
                text=mock_text,
                model_name="mock-test-harness",
                provider_type="mock_test",
                prompt_tokens=len(prompt.split()),
                completion_tokens=len(mock_text.split()),
                latency_sec=round(time.time() - start_time, 4),
                cost_usd=0.0,
                timestamp=timestamp_str,
                raw_metadata={"mock": True},
                is_mock=True
            )

        if self.config.provider_type == "gemini":
            return self._call_gemini_api(prompt, system_prompt, start_time, timestamp_str)
        elif self.config.provider_type == "openai" or self.config.provider_type == "custom_http":
            return self._call_openai_api(prompt, system_prompt, start_time, timestamp_str)
        elif self.config.provider_type == "anthropic":
            return self._call_anthropic_api(prompt, system_prompt, start_time, timestamp_str)
        else:
            raise ValueError(f"Unsupported provider type: {self.config.provider_type}")

    def _call_gemini_api(self, prompt: str, system_prompt: Optional[str], start_time: float, timestamp_str: str) -> LLMResponse:
        api_key = self.config.api_key
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.config.model_name}:generateContent?key={api_key}"
        
        contents = []
        if system_prompt:
            contents.append({"role": "user", "parts": [{"text": f"System Context:\n{system_prompt}"}]})
            contents.append({"role": "model", "parts": [{"text": "Understood. Proceeding with system guidelines."}]})
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": self.config.temperature,
                "maxOutputTokens": self.config.max_tokens
            }
        }
        
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        
        with urllib.request.urlopen(req, timeout=self.config.timeout_sec) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        usage = data.get("usageMetadata", {})
        prompt_tokens = usage.get("promptTokenCount", len(prompt.split()))
        completion_tokens = usage.get("candidatesTokenCount", len(text.split()))
        latency = round(time.time() - start_time, 4)
        
        # Estimate cost ($0.075 / 1M prompt, $0.30 / 1M completion for flash)
        cost = (prompt_tokens * 0.000000075) + (completion_tokens * 0.00000030)
        
        return LLMResponse(
            text=text,
            model_name=self.config.model_name,
            provider_type="gemini",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_sec=latency,
            cost_usd=round(cost, 6),
            timestamp=timestamp_str,
            raw_metadata={"usage": usage},
            is_mock=False
        )

    def _call_openai_api(self, prompt: str, system_prompt: Optional[str], start_time: float, timestamp_str: str) -> LLMResponse:
        base_url = self.config.base_url or "https://api.openai.com/v1"
        url = f"{base_url.rstrip('/')}/chat/completions"
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.config.model_name,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}"
        }
        
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
        with urllib.request.urlopen(req, timeout=self.config.timeout_sec) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            
        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", len(prompt.split()))
        completion_tokens = usage.get("completion_tokens", len(text.split()))
        latency = round(time.time() - start_time, 4)
        cost = (prompt_tokens * 0.00000015) + (completion_tokens * 0.00000060)
        
        return LLMResponse(
            text=text,
            model_name=self.config.model_name,
            provider_type=self.config.provider_type,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_sec=latency,
            cost_usd=round(cost, 6),
            timestamp=timestamp_str,
            raw_metadata={"usage": usage},
            is_mock=False
        )

    def _call_anthropic_api(self, prompt: str, system_prompt: Optional[str], start_time: float, timestamp_str: str) -> LLMResponse:
        url = "https://api.anthropic.com/v1/messages"
        payload = {
            "model": self.config.model_name,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "messages": [{"role": "user", "content": prompt}]
        }
        if system_prompt:
            payload["system"] = system_prompt
            
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.config.api_key,
            "anthropic-version": "2023-06-01"
        }
        
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
        with urllib.request.urlopen(req, timeout=self.config.timeout_sec) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            
        text = data["content"][0]["text"]
        usage = data.get("usage", {})
        prompt_tokens = usage.get("input_tokens", len(prompt.split()))
        completion_tokens = usage.get("output_tokens", len(text.split()))
        latency = round(time.time() - start_time, 4)
        cost = (prompt_tokens * 0.00000080) + (completion_tokens * 0.00000400)
        
        return LLMResponse(
            text=text,
            model_name=self.config.model_name,
            provider_type="anthropic",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_sec=latency,
            cost_usd=round(cost, 6),
            timestamp=timestamp_str,
            raw_metadata={"usage": usage},
            is_mock=False
        )
