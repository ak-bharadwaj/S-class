"""
S-Class V12: Context Budget & Token Saturation Monitor (context_budget.py)

Offline BPE token tracking via tiktoken. Alerts host AI agents at 75% and 90%
context window saturation to avoid degraded reasoning and context truncation.
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("sclass_context_budget")

try:
    import tiktoken
    _TIKTOKEN_AVAILABLE = True
    _ENCODER = tiktoken.get_encoding("cl100k_base")
except Exception:
    _TIKTOKEN_AVAILABLE = False
    _ENCODER = None


class ContextBudgetMonitor:
    """
    Monitors token consumption and alerts at critical context capacity thresholds.
    """

    DEFAULT_WINDOW = 128000  # 128k standard

    @classmethod
    def count_tokens(cls, text: str) -> int:
        """Counts BPE tokens using tiktoken (cl100k_base) or whitespace fallback."""
        if not text:
            return 0
        if _TIKTOKEN_AVAILABLE and _ENCODER:
            try:
                return len(_ENCODER.encode(text, disallowed_special=()))
            except Exception:
                pass
        # Approx 4 chars per token fallback
        return max(1, len(text) // 4)

    @classmethod
    def evaluate_budget(
        cls,
        current_text_or_tokens: Any = None,
        context_window: int = DEFAULT_WINDOW,
        used_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Evaluates current utilization against window and determines alert status.
        """
        if used_tokens is not None:
            used = used_tokens
        elif isinstance(current_text_or_tokens, int):
            used = current_text_or_tokens
        elif current_text_or_tokens is not None:
            used = cls.count_tokens(str(current_text_or_tokens))
        else:
            used = 0

        utilization = min(1.0, used / max(1, context_window))
        percentage = round(utilization * 100.0, 1)

        alert_level = "NOMINAL"
        recommendation = "Normal execution."

        if utilization >= 0.90:
            alert_level = "CRITICAL"
            recommendation = "CRITICAL: 90% context saturation! Prune conversation history or trigger session handoff immediately."
        elif utilization >= 0.75:
            alert_level = "WARNING"
            recommendation = "WARNING: 75% context threshold reached. Avoid injecting large file dumps; query CKG subgraphs instead."

        return {
            "tokens_used": used,
            "context_window": context_window,
            "utilization_ratio": utilization,
            "utilization_percent": percentage,
            "alert_level": alert_level,
            "recommendation": recommendation,
        }
