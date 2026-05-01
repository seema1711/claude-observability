"""Rule-based prompt analyzer — no API calls required."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from config import VERBOSITY_PATTERNS
from tracker import estimate_tokens

Category = Literal["code", "debugging", "explanation", "writing",
                   "analysis", "question", "creative", "refactoring", "other"]

CATEGORY_SIGNALS: list[tuple[list[str], str]] = [
    (["debug", "error", "exception", "traceback", "fix", "broken", "issue", "bug"], "debugging"),
    (["refactor", "clean up", "restructure", "reorganize", "improve code"], "refactoring"),
    (["write", "draft", "compose", "email", "blog", "article", "essay"], "writing"),
    (["explain", "what is", "how does", "describe", "clarify"], "explanation"),
    (["analyze", "review", "compare", "evaluate", "assess", "audit"], "analysis"),
    (["function", "class", "method", "implement", "code", "script",
      "python", "javascript", "typescript", "sql", "bash", "rust"], "code"),
    (["story", "poem", "creative", "imagine", "fiction"], "creative"),
    (["?", "how", "what", "why", "when", "where", "who"], "question"),
]


@dataclass
class Suggestion:
    type: str          # verbosity | structure | caching | redundancy | system_prompt
    message: str
    token_savings: int = 0
    priority: str = "low"   # low | medium | high


@dataclass
class PromptAnalysis:
    token_count: int
    category: Category
    optimization_score: int       # 0-100 (higher = already well-optimized)
    suggestions: list[Suggestion] = field(default_factory=list)

    @property
    def total_potential_savings(self) -> int:
        return sum(s.token_savings for s in self.suggestions)

    def to_dict(self) -> dict:
        return {
            "token_count": self.token_count,
            "category": self.category,
            "optimization_score": self.optimization_score,
            "suggestions": [
                {"type": s.type, "message": s.message,
                 "token_savings": s.token_savings, "priority": s.priority}
                for s in self.suggestions
            ],
            "total_potential_savings": self.total_potential_savings,
        }


def analyze(prompt: str) -> PromptAnalysis:
    token_count = estimate_tokens(prompt)
    category = _classify(prompt)
    suggestions: list[Suggestion] = []

    suggestions.extend(_check_verbosity(prompt))
    suggestions.extend(_check_structure(prompt, token_count))
    suggestions.extend(_check_caching_opportunity(prompt, token_count))
    suggestions.extend(_check_redundancy(prompt))
    suggestions.extend(_check_system_prompt_candidate(prompt))

    penalty = sum(
        {"low": 2, "medium": 5, "high": 10}.get(s.priority, 2)
        for s in suggestions
    )
    score = max(0, min(100, 100 - penalty))

    return PromptAnalysis(
        token_count=token_count,
        category=category,
        optimization_score=score,
        suggestions=suggestions,
    )


def format_analysis(analysis: PromptAnalysis, prompt_preview_len: int = 60) -> str:
    """Return a rich-formatted string for terminal/UI display."""
    lines = []
    lines.append("─" * 60)
    lines.append("  PROMPT OBSERVABILITY — Real-time Analysis")
    lines.append("─" * 60)
    lines.append(f"  Tokens     : ~{analysis.token_count}")
    lines.append(f"  Category   : {analysis.category}")
    lines.append(f"  Opt. Score : {analysis.optimization_score}/100")

    if analysis.suggestions:
        lines.append(f"  Savings    : ~{analysis.total_potential_savings} tokens possible")
        lines.append("")
        lines.append("  Suggestions:")
        for s in sorted(analysis.suggestions, key=lambda x: x.token_savings, reverse=True):
            icon = {"high": "!", "medium": "~", "low": "·"}.get(s.priority, "·")
            saving_str = f" (saves ~{s.token_savings} tok)" if s.token_savings else ""
            lines.append(f"   [{icon}] {s.message}{saving_str}")
    else:
        lines.append("  Prompt looks well-optimized!")

    lines.append("─" * 60)
    return "\n".join(lines)


# ── Private helpers ────────────────────────────────────────────────────────

def _classify(prompt: str) -> Category:
    lower = prompt.lower()
    scores: dict[str, int] = {}
    for signals, cat in CATEGORY_SIGNALS:
        for sig in signals:
            if sig in lower:
                scores[cat] = scores.get(cat, 0) + 1
    if not scores:
        return "other"
    return max(scores, key=lambda k: scores[k])  # type: ignore[return-value]


def _check_verbosity(prompt: str) -> list[Suggestion]:
    suggestions = []
    for pattern, message, savings in VERBOSITY_PATTERNS:
        matches = re.findall(pattern, prompt, re.IGNORECASE)
        if matches:
            total_savings = savings * len(matches)
            priority = "medium" if total_savings >= 8 else "low"
            suggestions.append(Suggestion(
                type="verbosity",
                message=message,
                token_savings=total_savings,
                priority=priority,
            ))
    return suggestions


def _check_structure(prompt: str, token_count: int) -> list[Suggestion]:
    suggestions = []

    # Wall of text check — paragraph-based or long single-line run-on
    paragraphs = [p.strip() for p in prompt.split("\n\n") if p.strip()]
    long_paragraphs = [p for p in paragraphs if len(p) > 500]
    words = prompt.split()
    is_runon = len(paragraphs) == 1 and len(words) > 60 and prompt.count(".") < 2
    if (long_paragraphs or is_runon) and token_count > 50:
        suggestions.append(Suggestion(
            type="structure",
            message="Break this into shorter, focused sentences or bullet points — one idea per line",
            token_savings=int(token_count * 0.10),
            priority="medium",
        ))

    # Multi-part request check — question marks OR compound conjunctions
    question_marks = prompt.count("?")
    compound_questions = len(re.findall(
        r"\b(and also|and could you|and what|and how|and tell me|and explain)\b",
        prompt, re.IGNORECASE
    ))
    total_questions = question_marks + compound_questions
    if total_questions >= 3:
        suggestions.append(Suggestion(
            type="structure",
            message=f"Prompt asks {total_questions} things at once — split into separate focused prompts for better answers",
            token_savings=0,
            priority="medium",
        ))

    # XML tagging suggestion for complex prompts
    has_sections = any(kw in prompt.lower() for kw in
                       ["context", "background", "instruction", "task", "input", "output"])
    has_xml = bool(re.search(r"<\w+>", prompt))
    if token_count > 300 and has_sections and not has_xml:
        suggestions.append(Suggestion(
            type="structure",
            message="Use XML tags (<context>, <task>, <output_format>) to structure complex prompts — Claude handles these best",
            token_savings=0,
            priority="medium",
        ))

    return suggestions


def _check_caching_opportunity(prompt: str, token_count: int) -> list[Suggestion]:
    suggestions = []

    if token_count > 1024:
        suggestions.append(Suggestion(
            type="caching",
            message=(
                "Prompt exceeds 1024 tokens — ideal for prompt caching. "
                "Move stable context (docs, code, instructions) to a system prompt with cache_control "
                "to save up to 90% on repeated calls."
            ),
            token_savings=int(token_count * 0.6),
            priority="high",
        ))
    elif token_count > 500:
        suggestions.append(Suggestion(
            type="caching",
            message="Prompt >500 tokens — consider extracting static context to a cached system prompt",
            token_savings=int(token_count * 0.3),
            priority="medium",
        ))

    return suggestions


def _check_redundancy(prompt: str) -> list[Suggestion]:
    suggestions = []
    sentences = [s.strip() for s in re.split(r"[.!?]\s+", prompt) if len(s.strip()) > 20]

    # Detect near-duplicate sentences (simple word overlap)
    seen: list[set] = []
    duplicates = 0
    for sent in sentences:
        words = set(sent.lower().split())
        for prev in seen:
            overlap = len(words & prev) / max(len(words | prev), 1)
            if overlap > 0.7:
                duplicates += 1
                break
        seen.append(words)

    if duplicates >= 2:
        suggestions.append(Suggestion(
            type="redundancy",
            message=f"Detected ~{duplicates} near-duplicate sentences — condense repeated instructions",
            token_savings=duplicates * 15,
            priority="medium",
        ))

    return suggestions


def _check_system_prompt_candidate(prompt: str) -> list[Suggestion]:
    suggestions = []
    lower = prompt.lower()

    persona_signals = [
        "you are a", "act as", "your role is", "you will be",
        "respond only", "always respond", "never respond",
    ]
    formatting_signals = [
        "always use markdown", "format your response", "respond in json",
        "use bullet points", "your response should always",
    ]

    has_persona = any(sig in lower for sig in persona_signals)
    has_formatting = any(sig in lower for sig in formatting_signals)

    if has_persona:
        suggestions.append(Suggestion(
            type="system_prompt",
            message="Persona/role definition detected — move this to the system prompt so it's cached across all turns",
            token_savings=30,
            priority="high",
        ))

    if has_formatting:
        suggestions.append(Suggestion(
            type="system_prompt",
            message="Formatting instructions detected — move to system prompt to avoid repeating every turn",
            token_savings=20,
            priority="medium",
        ))

    return suggestions
