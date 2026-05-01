"""Token counting and cost calculation utilities."""
from __future__ import annotations

from config import MODEL_PRICING


def estimate_tokens(text: str) -> int:
    """Fast client-side token estimate (~4 chars per token for English)."""
    if not text:
        return 0
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        return max(1, len(text) // 4)


def count_tokens_api(text: str, model: str = "claude-sonnet-4-6") -> int:
    """Use Anthropic API for exact token count (requires ANTHROPIC_API_KEY)."""
    try:
        import anthropic
        from config import ANTHROPIC_API_KEY
        if not ANTHROPIC_API_KEY:
            return estimate_tokens(text)
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client.beta.messages.count_tokens(
            model=model,
            messages=[{"role": "user", "content": text}],
            betas=["token-counting-2024-11-01"],
        )
        return response.input_tokens
    except Exception:
        return estimate_tokens(text)


def calculate_cost(input_tokens: int, output_tokens: int, model: str) -> float:
    """Return cost in USD given token counts and model name."""
    pricing = _get_pricing(model)
    cost = (input_tokens / 1_000_000) * pricing["input"]
    cost += (output_tokens / 1_000_000) * pricing["output"]
    return round(cost, 8)


def format_cost(cost: float) -> str:
    if cost < 0.001:
        return f"${cost * 1000:.4f}m"  # millicents
    return f"${cost:.4f}"


def format_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


def _get_pricing(model: str) -> dict:
    for key in MODEL_PRICING:
        if key in model.lower():
            return MODEL_PRICING[key]
    return MODEL_PRICING["default"]
