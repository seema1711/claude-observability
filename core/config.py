import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent  # project root
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "observability.db"

MODEL_PRICING = {
    "claude-opus-4-7":   {"input": 15.0,  "output": 75.0},
    "claude-opus-4-5":   {"input": 15.0,  "output": 75.0},
    "claude-sonnet-4-6": {"input": 3.0,   "output": 15.0},
    "claude-haiku-4-5":  {"input": 0.25,  "output": 1.25},
    "claude-opus":       {"input": 15.0,  "output": 75.0},
    "claude-sonnet":     {"input": 3.0,   "output": 15.0},
    "claude-haiku":      {"input": 0.25,  "output": 1.25},
    "default":           {"input": 3.0,   "output": 15.0},
}

DASHBOARD_PORT = int(os.environ.get("OBSERVABILITY_DASHBOARD_PORT", 7891))
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

PROMPT_CATEGORIES = [
    "code", "debugging", "explanation", "writing",
    "analysis", "question", "creative", "refactoring", "other",
]

VERBOSITY_PATTERNS = [
    (r"\bI would like you to\b", "Remove 'I would like you to'", 5),
    (r"\bI would like to\b",     "Remove 'I would like to'", 4),
    (r"\bCould you please\b",    "Replace 'Could you please' with a direct verb", 3),
    (r"\bCould you also\b",      "Replace 'Could you also' with a direct verb", 3),
    (r"\bWould you mind\b",      "Replace 'Would you mind' with a direct verb", 3),
    (r"\bI want you to\b",       "Remove 'I want you to'", 4),
    (r"\bYour task is to\b",     "Remove 'Your task is to'", 4),
    (r"\bPlease note that\b",    "Remove 'Please note that'", 3),
    (r"\bIt is important to note\b", "Remove 'It is important to note'", 5),
    (r"\bAs an AI\b",            "Avoid 'As an AI' (wastes tokens)", 3),
    (r"\bI hope this (helps|finds you well)\b", "Remove filler phrase", 5),
    (r"\bThank you (in advance|for your help|so much)\b", "Remove filler phrase", 5),
    (r"\bthank you\b",           "Remove 'thank you' (not needed for LLMs)", 3),
    (r"\bCan you help me\b",     "Remove 'Can you help me'", 4),
    (r"\bhelp me to\b",          "Simplify 'help me to' → direct verb", 3),
    (r"\bI need you to\b",       "Remove 'I need you to'", 4),
    (r"\bPlease\b",              "Remove 'Please' (not needed for LLMs)", 1),
    (r"\bkindly\b",              "Remove 'kindly' (filler word)", 2),
    (r"\band also\b",            "Remove 'and also' — redundant conjunction", 2),
    (r"\btoo please\b",          "Remove trailing 'too please' filler", 3),
    (r"\bso much\b",             "Remove 'so much' filler", 2),
]
